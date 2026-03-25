from __future__ import annotations

import argparse
import copy
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.backtest import (  # noqa: E402
    build_hazard_attribution,
    bootstrap_confidence_intervals,
    brier_score_summary,
    compare_to_paper,
    compute_buy_hold_positions,
    compute_cassandra_signal,
    compute_price_returns,
    compute_vol_target_positions,
    event_window_analysis,
    metrics_table,
    simulate_strategy,
    summarize_strategy,
)
from cassandra_risk.clients import fetch_fred_tb3ms, fetch_spy_prices  # noqa: E402
from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.events import (  # noqa: E402
    aggregate_daily_probabilities,
    build_event_metadata,
    build_event_panel,
    load_curated_shortlist,
    load_polymarket_approved_universe,
    merge_seeds_with_shortlist,
    normalize_proxy_metadata,
    resolve_proxy_aggregation_policy,
)
from cassandra_risk.reporting import render_report  # noqa: E402
from cassandra_risk.utils import ensure_dir, parse_date, write_csv, write_json  # noqa: E402


def series_rows(name: str, result: dict, extra: dict | None = None) -> list[dict]:
    extra = extra or {}
    rows = []
    for idx, day in enumerate(result["dates"]):
        row = {
            "date": day,
            "strategy": name,
            "position": result["positions"][idx],
            "daily_return": result["daily_returns"][idx],
            "equity": result["equity"][idx],
        }
        for key, values in extra.items():
            row[key] = values[idx]
        rows.append(row)
    return rows


def build_daily_risk_free_series(dates: list[str], fred_rows: list[dict], fallback_annual_rate: float) -> list[float]:
    fred_points = sorted(
        ((parse_date(row["date"]), float(row["annual_rate"])) for row in fred_rows),
        key=lambda item: item[0],
    )
    annual_rates: list[float] = []
    current_rate = fallback_annual_rate
    fred_index = 0
    for day_string in dates:
        current_date = parse_date(day_string)
        while fred_index < len(fred_points) and fred_points[fred_index][0] <= current_date:
            current_rate = fred_points[fred_index][1]
            fred_index += 1
        annual_rates.append(current_rate)
    return annual_rates


def configure_version(base_config: dict, version: str) -> dict:
    config = copy.deepcopy(base_config)
    if version == "v1":
        config["cassandra"]["category_lambdas"] = {
            category: (0.0 if category == "None" else 0.10)
            for category in config["cassandra"]["category_lambdas"]
        }
    return config


def risk_free_inputs(
    version: str,
    dates: list[str],
    fred_rows: list[dict],
    fallback_annual_rate: float,
    fred_fetch_succeeded: bool,
) -> tuple[list[float], str]:
    if version == "v1":
        return [0.0] * len(dates), "0% annualized baseline"
    if fred_fetch_succeeded:
        return build_daily_risk_free_series(dates, fred_rows, fallback_annual_rate), "FRED TB3MS"
    return [fallback_annual_rate] * len(dates), "fallback 4.31% annualized"


def build_replication_gaps(shortlist: list[dict], merge_audit_rows: list[dict]) -> list[str]:
    approved_count = len(shortlist)
    replaced = sum(1 for row in merge_audit_rows if row["merge_action"] == "replaced_existing_event")
    retained = sum(1 for row in merge_audit_rows if row["merge_action"] == "manual_retained")
    return [
        (
            f"The curated Manifold shortlist currently contains {approved_count} approved markets and replaces {replaced} "
            "paper/manual event definitions in the backtest event panel."
        ),
        (
            "The shortlist is semi-automatic rather than fully automatic: discovery and scoring are systematic, but approval "
            "still happens through checked-in curated review files."
        ),
        (
            f"{retained} event definitions still come directly from paper/manual seeds because they do not yet have an approved "
            "curated Manifold replacement."
        ),
        (
            "Catalog review decisions remain deterministic and auditable through the curated shortlist and override files, "
            "with no LLM dependency in the selection loop."
        ),
        (
            "The paper's full production event universe remains unpublished, so even the improved public Manifold pipeline "
            "still approximates, rather than exactly reproduces, the live Cassandra framework."
        ),
    ]


def build_version_comparison(version_summaries: dict[str, dict], paper_metrics: dict) -> list[dict]:
    rows = []
    metric_order = [
        "cagr",
        "total_return",
        "volatility",
        "max_drawdown_daily",
        "max_drawdown_monthly",
        "downside_deviation",
        "cvar_95",
        "sharpe",
        "sortino",
        "calmar",
        "avg_position",
        "days_in_90pct_cash",
        "max_consecutive_cash_days",
        "paranoia_tax",
    ]
    mapping = {
        "buy_hold": "buy_and_hold",
        "vol_target": "vol_target",
        "cassandra": "cassandra",
    }
    for strategy, paper_key in mapping.items():
        for metric in metric_order:
            paper_value = paper_metrics[paper_key].get("max_drawdown") if metric == "max_drawdown_monthly" else paper_metrics[paper_key].get(metric)
            if metric == "max_drawdown_daily":
                paper_value = None
            row = {
                "strategy": strategy,
                "metric": metric,
                "v1": version_summaries["v1"][strategy].get(metric),
                "v2": version_summaries["v2"][strategy].get(metric),
                "v3": version_summaries["v3"][strategy].get(metric),
                "paper": paper_value,
            }
            row["v2_minus_v1"] = row["v2"] - row["v1"] if row["v1"] is not None and row["v2"] is not None else None
            row["v3_minus_v2"] = row["v3"] - row["v2"] if row["v2"] is not None and row["v3"] is not None else None
            row["v3_minus_paper"] = row["v3"] - row["paper"] if row["paper"] is not None else None
            rows.append(row)
    return rows


def render_version_markdown(path: Path, rows: list[dict]) -> None:
    percentage_metrics = {
        "cagr",
        "total_return",
        "volatility",
        "max_drawdown_daily",
        "max_drawdown_monthly",
        "downside_deviation",
        "cvar_95",
        "avg_position",
        "paranoia_tax",
    }

    def render(metric: str, value: float | None) -> str:
        if value is None:
            return "n/a"
        if metric in percentage_metrics:
            return f"{value * 100:.2f}%"
        if "days" in metric:
            return str(int(round(value)))
        return f"{value:.3f}"

    with path.open("w", encoding="utf-8") as handle:
        handle.write("| Strategy | Metric | V1 | V2 | V3 | Paper |\n")
        handle.write("| --- | --- | ---: | ---: | ---: | ---: |\n")
        for row in rows:
            handle.write(
                f"| {row['strategy']} | {row['metric']} | {render(row['metric'], row['v1'])} | "
                f"{render(row['metric'], row['v2'])} | {render(row['metric'], row['v3'])} | "
                f"{render(row['metric'], row['paper'])} |\n"
            )


def build_gap_hypotheses(
    v2_summary: dict,
    v3_summary: dict,
    shortlist: list[dict],
    merge_audit_rows: list[dict],
    risk_free_source: str,
) -> list[str]:
    approved_count = len(shortlist)
    retained = sum(1 for row in merge_audit_rows if row["merge_action"] == "manual_retained")
    return [
        (
            f"The current curated shortlist has {approved_count} approved Manifold markets. Hypothesis: the remaining "
            "divergence versus the paper is still dominated by incomplete public event coverage rather than by arithmetic or "
            "risk-free-rate conventions."
        ),
        (
            f"{retained} event definitions are still retained from manual/paper seeds. Hypothesis: these unresolved events are "
            "where the biggest remaining gap in false-positive drag and de-risking behavior still lives."
        ),
        (
            "The shortlist and override workflow should reduce discretionary event selection over time. Hypothesis: as the "
            "catalog grows, Cassandra's exposure path should become more realistic even if headline returns decline."
        ),
        (
            f"Cassandra average position moved from {v2_summary['cassandra']['avg_position'] * 100:.2f}% in V2 to "
            f"{v3_summary['cassandra']['avg_position'] * 100:.2f}% in V3. Hypothesis: the extra Manifold coverage changes the "
            "path, but not enough to close the gap to the paper's 73% average exposure."
        ),
        (
            f"Sortino in V2/V3 uses {risk_free_source}. Hypothesis for any remaining Sortino gap: the paper may still be using "
            "different excess-return timing or monthly aggregation conventions than this daily implementation."
        ),
    ]


def simple_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def phase3_regime_bucket(rsi: float) -> str:
    if rsi < 0.3:
        return "RSI < 0.3 (high hazard)"
    if rsi <= 0.7:
        return "0.3 <= RSI <= 0.7 (transition)"
    return "RSI > 0.7 (low hazard)"


def dominant_component_from_row(row: dict) -> str:
    component_values = {
        "P_hazard": float(row["probability_rsi_drag"]),
        "S_severity": float(row["severity_rsi_drag"]),
        "C_velocity": float(row["velocity_rsi_drag"]),
        "T_persistence": float(row["persistence_rsi_drag"]),
    }
    return max(component_values, key=component_values.get)


def top_low_rsi_days_rows(decomposition_rows: list[dict], attribution_rows: list[dict], limit: int = 20) -> list[dict]:
    dominant_by_date = {
        row["date"]: row for row in attribution_rows if row.get("dominant_event_flag")
    }
    ranked = sorted(decomposition_rows, key=lambda row: (float(row["rsi"]), row["date"]))
    rows = []
    for row in ranked[:limit]:
        dominant = dominant_by_date.get(row["date"], {})
        rows.append(
            {
                "date": row["date"],
                "rsi": float(row["rsi"]),
                "total_hazard": float(row["total_hazard"]),
                "dominant_event_id": row.get("dominant_event_id", ""),
                "dominant_category": row.get("dominant_category", ""),
                "dominant_component": dominant_component_from_row(row),
                "dominant_event_market_id": dominant.get("dominant_event_market_id", ""),
                "dominant_event_question": dominant.get("dominant_event_question", ""),
                "probability_share": float(row["probability_share_of_hazard"]),
                "severity_share": float(row["severity_share_of_hazard"]),
                "velocity_share": float(row["velocity_share_of_hazard"]),
                "persistence_share": float(row["persistence_share_of_hazard"]),
            }
        )
    return rows


def cumulative_hazard_rows(attribution_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    total_hazard = sum(float(row["hazard_contribution"]) for row in attribution_rows)
    by_event: dict[tuple[str, str], dict] = {}
    by_category: dict[str, dict] = {}

    for row in attribution_rows:
        hazard = float(row["hazard_contribution"])
        event_key = (row["event_id"], row["category"])
        event_entry = by_event.setdefault(
            event_key,
            {
                "event_id": row["event_id"],
                "category": row["category"],
                "cumulative_hazard": 0.0,
                "active_days": 0,
                "first_date": row["date"],
                "last_date": row["date"],
            },
        )
        event_entry["cumulative_hazard"] += hazard
        event_entry["active_days"] += 1
        event_entry["first_date"] = min(event_entry["first_date"], row["date"])
        event_entry["last_date"] = max(event_entry["last_date"], row["date"])

        category_entry = by_category.setdefault(
            row["category"],
            {"category": row["category"], "cumulative_hazard": 0.0, "active_event_days": 0},
        )
        category_entry["cumulative_hazard"] += hazard
        category_entry["active_event_days"] += 1

    event_rows = []
    for entry in by_event.values():
        event_rows.append(
            {
                **entry,
                "hazard_share": 0.0 if total_hazard == 0 else entry["cumulative_hazard"] / total_hazard,
            }
        )
    event_rows.sort(key=lambda row: (-row["cumulative_hazard"], row["event_id"]))

    category_rows = []
    for entry in by_category.values():
        category_rows.append(
            {
                **entry,
                "hazard_share": 0.0 if total_hazard == 0 else entry["cumulative_hazard"] / total_hazard,
            }
        )
    category_rows.sort(key=lambda row: (-row["cumulative_hazard"], row["category"]))
    return event_rows, category_rows


def regime_bucket_rows(decomposition_rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in decomposition_rows:
        grouped.setdefault(phase3_regime_bucket(float(row["rsi"])), []).append(row)

    ordered_buckets = [
        "RSI < 0.3 (high hazard)",
        "0.3 <= RSI <= 0.7 (transition)",
        "RSI > 0.7 (low hazard)",
    ]
    rows = []
    for bucket in ordered_buckets:
        bucket_rows = grouped.get(bucket, [])
        avg_probability = simple_mean([float(row["probability_share_of_hazard"]) for row in bucket_rows])
        avg_severity = simple_mean([float(row["severity_share_of_hazard"]) for row in bucket_rows])
        avg_velocity = simple_mean([float(row["velocity_share_of_hazard"]) for row in bucket_rows])
        avg_persistence = simple_mean([float(row["persistence_share_of_hazard"]) for row in bucket_rows])
        avg_rsi = simple_mean([float(row["rsi"]) for row in bucket_rows])
        avg_hazard = simple_mean([float(row["total_hazard"]) for row in bucket_rows])
        dominant_component = max(
            {
                "P_hazard": avg_probability,
                "S_severity": avg_severity,
                "C_velocity": avg_velocity,
                "T_persistence": avg_persistence,
            },
            key=lambda key: {
                "P_hazard": avg_probability,
                "S_severity": avg_severity,
                "C_velocity": avg_velocity,
                "T_persistence": avg_persistence,
            }[key],
        )
        rows.append(
            {
                "regime_bucket": bucket,
                "day_count": len(bucket_rows),
                "avg_rsi": avg_rsi,
                "avg_total_hazard": avg_hazard,
                "avg_probability_share": avg_probability,
                "avg_severity_share": avg_severity,
                "avg_velocity_share": avg_velocity,
                "avg_persistence_share": avg_persistence,
                "dominant_component": dominant_component,
            }
        )
    return rows


def proxy_family_coverage_rows(resolved_seeds: list[dict], config: dict) -> list[dict]:
    cassandra = config["cassandra"]
    event_policy = cassandra.get("multi_family_aggregation", cassandra.get("multi_proxy_aggregation", "weighted_average"))
    grouped: dict[str, list[dict]] = {}
    for seed in resolved_seeds:
        normalized = normalize_proxy_metadata(seed)
        grouped.setdefault(normalized["event_id"], []).append(normalized)

    rows = []
    for event_id, seeds in sorted(grouped.items()):
        family_groups: dict[str, list[dict]] = defaultdict(list)
        for seed in seeds:
            family_groups[seed["proxy_family_id"]].append(seed)

        family_policy_parts = []
        relations = set()
        source_types = set()
        market_ids = []
        quality_scores = []
        event_window_starts = []
        event_window_ends = []
        for family_id, family_rows in sorted(family_groups.items()):
            policy = resolve_proxy_aggregation_policy(family_rows, config)
            relation = family_rows[0].get("proxy_relation") or "substitute"
            relations.add(relation)
            family_policy_parts.append(f"{family_id}:{policy}({relation})")
            for row in family_rows:
                source_types.add(row["source"])
                if row.get("market_id"):
                    market_ids.append(row["market_id"])
                quality_scores.append(float(row.get("quality_score", 0.0)))
                event_window_starts.append(row.get("event_window_start"))
                event_window_ends.append(row.get("event_window_end"))

        first = seeds[0]
        rows.append(
            {
                "event_id": event_id,
                "category": first["category"],
                "structural_theme": first.get("structural_theme", ""),
                "proxy_count": len(seeds),
                "proxy_family_count": len(family_groups),
                "proxy_family_ids": " | ".join(sorted(family_groups)),
                "proxy_relations": " | ".join(sorted(relations)),
                "family_aggregation_policies": " | ".join(family_policy_parts),
                "event_aggregation_policy": event_policy,
                "source_types": " | ".join(sorted(source_types)),
                "market_ids": " | ".join(sorted(market_ids)),
                "event_window_start": min(value for value in event_window_starts if value),
                "event_window_end": max(value for value in event_window_ends if value),
                "quality_score_min": min(quality_scores) if quality_scores else 0.0,
                "quality_score_max": max(quality_scores) if quality_scores else 0.0,
            }
        )
    return rows


def render_phase3_summary_report(
    path: Path,
    low_rsi_rows: list[dict],
    event_rows: list[dict],
    category_rows: list[dict],
    regime_rows: list[dict],
) -> None:
    lines: list[str] = []
    lines.append("# Phase 3 Summary Report")
    lines.append("")
    lines.append("## Top 20 Lowest-RSI Days")
    lines.append("")
    lines.append("Table 1 candidate for Paper 2. Days are sorted by RSI ascending; the dominant event and dominant P/S/C/T component are flagged for each day.")
    lines.append("")
    lines.append("| Date | RSI | Total Hazard | Dominant Event | Dominant Category | Dominant Component | P Share | S Share | C Share | T Share |")
    lines.append("| --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |")
    for row in low_rsi_rows:
        lines.append(
            f"| {row['date']} | {row['rsi']:.3f} | {row['total_hazard']:.3f} | {row['dominant_event_id']} | "
            f"{row['dominant_category']} | {row['dominant_component']} | "
            f"{row['probability_share'] * 100:.2f}% | {row['severity_share'] * 100:.2f}% | "
            f"{row['velocity_share'] * 100:.2f}% | {row['persistence_share'] * 100:.2f}% |"
        )
    lines.append("")
    lines.append("## Top Hazard Contributors By Event")
    lines.append("")
    lines.append("Cumulative hazard share over the full backtest window. This addresses whether the result is event-specific or distributed across the event set.")
    lines.append("")
    lines.append("| Rank | Event | Category | Cum Hazard | Hazard Share | Active Days | First Date | Last Date |")
    lines.append("| ---: | --- | --- | ---: | ---: | ---: | --- | --- |")
    for index, row in enumerate(event_rows, start=1):
        lines.append(
            f"| {index} | {row['event_id']} | {row['category']} | {row['cumulative_hazard']:.3f} | "
            f"{row['hazard_share'] * 100:.2f}% | {row['active_days']} | {row['first_date']} | {row['last_date']} |"
        )
    lines.append("")
    lines.append("## Top Hazard Contributors By Category")
    lines.append("")
    lines.append("| Rank | Category | Cum Hazard | Hazard Share | Active Event-Days |")
    lines.append("| ---: | --- | ---: | ---: | ---: |")
    for index, row in enumerate(category_rows, start=1):
        lines.append(
            f"| {index} | {row['category']} | {row['cumulative_hazard']:.3f} | "
            f"{row['hazard_share'] * 100:.2f}% | {row['active_event_days']} |"
        )
    lines.append("")
    lines.append("## Average P/S/C/T Shares By Regime Bucket")
    lines.append("")
    lines.append("Average component shares by RSI bucket. This is the transparency layer for how the hazard formula changes character across regimes.")
    lines.append("")
    lines.append("| Regime Bucket | Days | Avg RSI | Avg Hazard | Avg P Share | Avg S Share | Avg C Share | Avg T Share | Dominant Component |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in regime_rows:
        lines.append(
            f"| {row['regime_bucket']} | {row['day_count']} | {row['avg_rsi']:.3f} | {row['avg_total_hazard']:.3f} | "
            f"{row['avg_probability_share'] * 100:.2f}% | {row['avg_severity_share'] * 100:.2f}% | "
            f"{row['avg_velocity_share'] * 100:.2f}% | {row['avg_persistence_share'] * 100:.2f}% | {row['dominant_component']} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_version(
    version: str,
    base_config: dict,
    base_seeds: list[dict],
    shortlist: list[dict],
    dates: list[str],
    price_returns: list[float],
    price_rows: list[dict],
    raw_dir: Path,
    refresh: bool,
    fred_rows: list[dict],
    fallback_annual_rate: float,
    fred_fetch_succeeded: bool,
    extra_curated_seeds: list[dict] | None = None,
    extra_curated_audit: list[dict] | None = None,
) -> dict:
    config = configure_version(base_config, version)
    resolved_seeds, shortlist_merge_audit = merge_seeds_with_shortlist(base_seeds, shortlist)
    if extra_curated_seeds:
        resolved_seeds.extend(copy.deepcopy(extra_curated_seeds))
        resolved_seeds.sort(key=lambda item: (item["event_id"], item.get("market_id") or "", item["source"]))
        shortlist_merge_audit.extend(
            extra_curated_audit
            or [
                {
                    "event_id": seed["event_id"],
                    "merge_action": "added_curated_event",
                    "source": seed["source"],
                    "market_id": seed.get("market_id"),
                    "selection_reason": seed.get("notes", "Approved curated expansion event."),
                }
                for seed in extra_curated_seeds
            ]
        )
    event_rows = build_event_panel(config, resolved_seeds, raw_dir, refresh=refresh)
    event_metadata = build_event_metadata(event_rows)
    daily_events = aggregate_daily_probabilities(event_rows, config)
    risk_free_annual_rates, risk_free_source = risk_free_inputs(
        version,
        dates,
        fred_rows,
        fallback_annual_rate,
        fred_fetch_succeeded,
    )

    buy_hold_positions = compute_buy_hold_positions(dates)
    vol_target_positions = compute_vol_target_positions(config, price_returns)
    cassandra_rsi, cassandra_hazard, threshold_events = compute_cassandra_signal(dates, daily_events, config)

    transaction_cost_bps = float(config["transaction_cost_bps"])
    buy_hold_result = simulate_strategy(dates, price_returns, buy_hold_positions, transaction_cost_bps)
    vol_target_result = simulate_strategy(dates, price_returns, vol_target_positions, transaction_cost_bps)
    cassandra_result = simulate_strategy(dates, price_returns, cassandra_rsi, transaction_cost_bps)

    summaries = {
        "buy_hold": summarize_strategy(buy_hold_result, risk_free_annual_rates),
        "vol_target": summarize_strategy(vol_target_result, risk_free_annual_rates),
        "cassandra": summarize_strategy(cassandra_result, risk_free_annual_rates),
    }
    summaries["cassandra"]["paranoia_tax"] = summaries["cassandra"]["cagr"] - summaries["buy_hold"]["cagr"]
    metrics_rows = metrics_table(summaries)
    comparison_rows = compare_to_paper(summaries, config["paper_metrics"])
    brier_rows = brier_score_summary(event_rows)
    event_analysis_rows = event_window_analysis(
        resolved_seeds,
        dates,
        price_returns,
        cassandra_result["positions"],
        cassandra_rsi,
        daily_events,
    )
    hazard_attribution_rows, daily_rsi_decomposition_rows = build_hazard_attribution(
        dates,
        daily_events,
        config,
    )

    robustness_rows = []
    if version == "v3":
        for scenario in config["cassandra"]["robustness_scenarios"]:
            scenario_rsi, _, _ = compute_cassandra_signal(
                dates,
                daily_events,
                config,
                lambda_scale=float(scenario["lambda_scale"]),
                probability_scale=float(scenario["probability_scale"]),
            )
            scenario_result = simulate_strategy(dates, price_returns, scenario_rsi, transaction_cost_bps)
            summary = summarize_strategy(scenario_result, risk_free_annual_rates)
            robustness_rows.append(
                {
                    "scenario": scenario["name"],
                    "cagr": summary["cagr"],
                    "max_drawdown": summary["max_drawdown"],
                    "sortino": summary["sortino"],
                    "avg_position": summary["avg_position"],
                }
            )

    bootstrap_rows = []
    if version == "v3":
        bootstrap_rows = bootstrap_confidence_intervals(
            {
                "buy_hold": buy_hold_result["daily_returns"],
                "vol_target": vol_target_result["daily_returns"],
                "cassandra": cassandra_result["daily_returns"],
            },
            block_size=int(config["bootstrap"]["block_size"]),
            resamples=int(config["bootstrap"]["resamples"]),
            seed=int(config["bootstrap"]["seed"]),
            risk_free_annual_rates=risk_free_annual_rates,
        )

    return {
        "config": config,
        "shortlist": shortlist,
        "resolved_seeds": resolved_seeds,
        "shortlist_merge_audit": shortlist_merge_audit,
        "event_rows": event_rows,
        "event_metadata": event_metadata,
        "daily_events": daily_events,
        "risk_free_annual_rates": risk_free_annual_rates,
        "risk_free_source": risk_free_source,
        "metrics_rows": metrics_rows,
        "comparison_rows": comparison_rows,
        "brier_rows": brier_rows,
        "event_analysis_rows": event_analysis_rows,
        "hazard_attribution_rows": hazard_attribution_rows,
        "daily_rsi_decomposition_rows": daily_rsi_decomposition_rows,
        "robustness_rows": robustness_rows,
        "bootstrap_rows": bootstrap_rows,
        "threshold_events": threshold_events,
        "price_rows": price_rows,
        "buy_hold_result": buy_hold_result,
        "vol_target_result": vol_target_result,
        "cassandra_result": cassandra_result,
        "cassandra_rsi": cassandra_rsi,
        "cassandra_hazard": cassandra_hazard,
        "summaries": summaries,
    }


def write_version_outputs(version: str, output_dir: Path, result: dict) -> None:
    write_csv(output_dir / "metrics.csv", result["metrics_rows"])
    write_csv(output_dir / "paper_comparison.csv", result["comparison_rows"])
    write_csv(
        output_dir / "equity_curves.csv",
        series_rows("buy_hold", result["buy_hold_result"])
        + series_rows("vol_target", result["vol_target_result"])
        + series_rows(
            "cassandra",
            result["cassandra_result"],
            {"rsi": result["cassandra_rsi"], "hazard": result["cassandra_hazard"]},
        ),
    )
    write_json(output_dir / "summary.json", result["summaries"])
    write_json(
        output_dir / "risk_free_summary.json",
        {
            "source": result["risk_free_source"],
            "fallback_annual_rate": float(result["config"]["risk_free_rate"]["fallback_annual_rate"]),
            "observations": len(result["risk_free_annual_rates"]),
        },
    )
    if version == "v3":
        write_csv(output_dir / "bootstrap_intervals.csv", result["bootstrap_rows"])
        write_csv(output_dir / "brier_scores.csv", result["brier_rows"])
        write_csv(output_dir / "event_analysis.csv", result["event_analysis_rows"])
        write_csv(output_dir / "hazard_attribution.csv", result["hazard_attribution_rows"])
        write_csv(output_dir / "daily_rsi_decomposition.csv", result["daily_rsi_decomposition_rows"])
        write_csv(output_dir / "robustness.csv", result["robustness_rows"])
        write_csv(output_dir / "threshold_events.csv", result["threshold_events"])
        write_csv(output_dir / "shortlist_merge_audit.csv", result["shortlist_merge_audit"])
        write_json(output_dir / "event_metadata.json", result["event_metadata"])
        legacy_search_audit = output_dir / "manifold_search_audit.csv"
        if legacy_search_audit.exists():
            legacy_search_audit.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Refresh raw data from public APIs")
    parser.add_argument(
        "--include-polymarket-approved",
        action="store_true",
        help="Include the Phase 5 approved Polymarket universe in the event panel.",
    )
    args = parser.parse_args()

    base_config = load_json(ROOT / "config" / "backtest_config.json")
    base_seeds = load_json(ROOT / "data" / "seeds" / "event_seeds.json")
    shortlist = load_curated_shortlist(ROOT / "data" / "curated" / "manifold_shortlist.json")
    approved_seeds, approved_audit = load_polymarket_approved_universe(
        ROOT / "data" / "curated" / "polymarket_approved.json",
        ROOT / "data" / "candidates" / "polymarket_candidates.json",
    )

    raw_dir = ensure_dir(ROOT / "data" / "raw")
    processed_dir = ensure_dir(ROOT / "data" / "processed")
    output_root = ensure_dir(ROOT / "outputs")

    price_rows = fetch_spy_prices(base_config, raw_dir, refresh=args.refresh)
    dates, _, price_returns = compute_price_returns(price_rows)

    fallback_annual_rate = float(base_config["risk_free_rate"]["fallback_annual_rate"])
    try:
        fred_rows = fetch_fred_tb3ms(raw_dir, refresh=args.refresh)
        fred_fetch_succeeded = True
    except Exception:
        fred_rows = []
        fred_fetch_succeeded = False

    version_results = {}
    for version in ("v1", "v2", "v3"):
        version_results[version] = run_version(
            version=version,
            base_config=base_config,
            base_seeds=base_seeds,
            shortlist=shortlist,
            dates=dates,
            price_returns=price_returns,
            price_rows=price_rows,
            raw_dir=raw_dir,
            refresh=args.refresh,
            fred_rows=fred_rows,
            fallback_annual_rate=fallback_annual_rate,
            fred_fetch_succeeded=fred_fetch_succeeded,
            extra_curated_seeds=approved_seeds if args.include_polymarket_approved else None,
            extra_curated_audit=approved_audit if args.include_polymarket_approved else None,
        )

    for version, folder in (("v1", "v1"), ("v2", "v2"), ("v3", "latest")):
        write_version_outputs(version, ensure_dir(output_root / folder), version_results[version])

    version_summaries = {version: result["summaries"] for version, result in version_results.items()}
    comparison_rows = build_version_comparison(version_summaries, base_config["paper_metrics"])
    latest_dir = ensure_dir(output_root / "latest")
    write_csv(latest_dir / "v1_v2_v3_paper_comparison.csv", comparison_rows)
    render_version_markdown(latest_dir / "v1_v2_v3_paper_comparison.md", comparison_rows)

    v3_result = version_results["v3"]
    phase3_low_rsi_rows = top_low_rsi_days_rows(
        v3_result["daily_rsi_decomposition_rows"],
        v3_result["hazard_attribution_rows"],
        limit=20,
    )
    phase3_event_rows, phase3_category_rows = cumulative_hazard_rows(v3_result["hazard_attribution_rows"])
    phase3_regime_rows = regime_bucket_rows(v3_result["daily_rsi_decomposition_rows"])
    coverage_rows = proxy_family_coverage_rows(v3_result["resolved_seeds"], v3_result["config"])

    write_csv(
        processed_dir / "event_panel.csv",
        [
            {
                "date": row["date"],
                "event_id": row["event_id"],
                "question": row["question"],
                "source": row["source"],
                "category": row["category"],
                "probability": row["probability"],
                "resolution_date": row["resolution_date"],
                "resolved_outcome": row["resolved_outcome"],
                "provenance": row["provenance"],
                "structural_theme": row.get("structural_theme", ""),
            }
            for row in v3_result["event_rows"]
        ],
    )
    write_csv(processed_dir / "spy_prices.csv", price_rows)
    write_csv(latest_dir / "proxy_family_coverage.csv", coverage_rows)
    write_json(latest_dir / "version_summaries.json", version_summaries)
    render_phase3_summary_report(
        latest_dir / "phase3_summary_report.md",
        phase3_low_rsi_rows,
        phase3_event_rows,
        phase3_category_rows,
        phase3_regime_rows,
    )
    (latest_dir / "gap_hypotheses.md").write_text(
        "\n".join(
            f"- {item}"
            for item in build_gap_hypotheses(
                version_results["v2"]["summaries"],
                v3_result["summaries"],
                shortlist,
                v3_result["shortlist_merge_audit"],
                v3_result["risk_free_source"],
            )
        ),
        encoding="utf-8",
    )

    render_report(
        latest_dir / "report.md",
        metrics_rows=v3_result["metrics_rows"],
        comparison_rows=v3_result["comparison_rows"],
        robustness_rows=v3_result["robustness_rows"],
        bootstrap_rows=v3_result["bootstrap_rows"],
        brier_rows=v3_result["brier_rows"],
        event_rows=v3_result["event_analysis_rows"],
        replication_gaps=build_replication_gaps(shortlist, v3_result["shortlist_merge_audit"]),
    )

    print("Completed Cassandra-Risk closest-public replication.")
    print(f"Outputs written to: {latest_dir}")
    print("Headline metrics:")
    for version in ("v1", "v2", "v3"):
        summaries = version_results[version]["summaries"]
        print(f"  {version}:")
        for name, summary in summaries.items():
            print(
                f"    {name}: CAGR={summary['cagr']:.4f}, DailyMDD={summary['max_drawdown_daily']:.4f}, "
                f"MonthlyMDD={summary['max_drawdown_monthly']:.4f}, Sortino={summary['sortino']:.3f}, "
                f"AvgPos={summary['avg_position']:.3f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
