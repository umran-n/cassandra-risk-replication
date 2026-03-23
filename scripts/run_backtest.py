from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.backtest import (  # noqa: E402
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
    resolve_event_sources,
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


def build_replication_gaps(search_audit_rows: list[dict]) -> list[str]:
    selected = sum(1 for row in search_audit_rows if row["replacement_status"] == "selected_pre_event_manifold_proxy")
    post_event_rejects = sum(1 for row in search_audit_rows if row["replacement_status"] == "post_event_market_rejected")
    no_match = sum(1 for row in search_audit_rows if row["replacement_status"] == "no_manifold_match")
    reviewed_manual = sum(1 for row in search_audit_rows if row["replacement_status"] == "search_results_reviewed_manual_kept")
    return [
        (
            f"V3 searched all nine kill-list events through Manifold and upgraded {selected} manual reconstructions to "
            "public market histories, but several events still have no clean public market coverage."
        ),
        (
            f"{post_event_rejects} candidate markets were intentionally rejected because they were created only after the "
            "target event window had already started, which would otherwise introduce look-ahead bias."
        ),
        (
            "The 2020 COVID crash and the mid-2022 rate-hike shock remain manually reconstructed because public Manifold "
            "coverage for those windows was not recoverable via search."
        ),
        (
            f"{no_match} kill-list events returned no usable Manifold match at all, and another {reviewed_manual} returned "
            "search hits that were judged too weak or off-target to replace the manual series."
        ),
        (
            "Even with broader Manifold coverage, the paper's full historical event panel remains unpublished, so the "
            "public replication can only approximate the production Cassandra signal rather than exactly reproduce it."
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
    search_audit_rows: list[dict],
    risk_free_source: str,
) -> list[str]:
    selected = sum(1 for row in search_audit_rows if row["replacement_status"] == "selected_pre_event_manifold_proxy")
    post_event_rejects = sum(1 for row in search_audit_rows if row["replacement_status"] == "post_event_market_rejected")
    no_match = sum(1 for row in search_audit_rows if row["replacement_status"] == "no_manifold_match")
    reviewed_manual = sum(1 for row in search_audit_rows if row["replacement_status"] == "search_results_reviewed_manual_kept")
    return [
        (
            f"Only {selected} additional manual events were upgraded in V3. Hypothesis: the remaining divergence versus the "
            "paper is still dominated by missing public event coverage rather than by arithmetic or risk-free-rate conventions."
        ),
        (
            f"{post_event_rejects} candidate markets were found but rejected for being post-event. Hypothesis: public Manifold "
            "coverage is often too late for fast-moving banking and crisis events, which leaves the replication underexposed to "
            "the paper's intended forward-looking signal."
        ),
        (
            f"{no_match} kill-list events still have no usable Manifold match, and {reviewed_manual} more only returned weak "
            "or off-target search hits. Hypothesis: the paper's production Dredger saw a broader event universe than what "
            "survives in public Manifold search, so false positives and de-risking spells are still understated here."
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


def run_version(
    version: str,
    base_config: dict,
    base_seeds: list[dict],
    dates: list[str],
    price_returns: list[float],
    price_rows: list[dict],
    raw_dir: Path,
    refresh: bool,
    fred_rows: list[dict],
    fallback_annual_rate: float,
    fred_fetch_succeeded: bool,
) -> dict:
    config = configure_version(base_config, version)
    enable_manifold_search = version == "v3"
    resolved_seeds, search_audit_rows = resolve_event_sources(
        base_seeds,
        raw_dir,
        refresh=refresh,
        enable_manifold_search=enable_manifold_search,
    )
    event_rows = build_event_panel(config, resolved_seeds, raw_dir, refresh=refresh)
    event_metadata = build_event_metadata(event_rows)
    daily_events = aggregate_daily_probabilities(event_rows)
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
        "resolved_seeds": resolved_seeds,
        "search_audit_rows": search_audit_rows,
        "event_rows": event_rows,
        "event_metadata": event_metadata,
        "daily_events": daily_events,
        "risk_free_annual_rates": risk_free_annual_rates,
        "risk_free_source": risk_free_source,
        "metrics_rows": metrics_rows,
        "comparison_rows": comparison_rows,
        "brier_rows": brier_rows,
        "event_analysis_rows": event_analysis_rows,
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
        write_csv(output_dir / "robustness.csv", result["robustness_rows"])
        write_csv(output_dir / "threshold_events.csv", result["threshold_events"])
        write_csv(output_dir / "manifold_search_audit.csv", result["search_audit_rows"])
        write_json(output_dir / "event_metadata.json", result["event_metadata"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Refresh raw data from public APIs")
    args = parser.parse_args()

    base_config = load_json(ROOT / "config" / "backtest_config.json")
    base_seeds = load_json(ROOT / "data" / "seeds" / "event_seeds.json")

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
            dates=dates,
            price_returns=price_returns,
            price_rows=price_rows,
            raw_dir=raw_dir,
            refresh=args.refresh,
            fred_rows=fred_rows,
            fallback_annual_rate=fallback_annual_rate,
            fred_fetch_succeeded=fred_fetch_succeeded,
        )

    for version, folder in (("v1", "v1"), ("v2", "v2"), ("v3", "latest")):
        write_version_outputs(version, ensure_dir(output_root / folder), version_results[version])

    version_summaries = {version: result["summaries"] for version, result in version_results.items()}
    comparison_rows = build_version_comparison(version_summaries, base_config["paper_metrics"])
    latest_dir = ensure_dir(output_root / "latest")
    write_csv(latest_dir / "v1_v2_v3_paper_comparison.csv", comparison_rows)
    render_version_markdown(latest_dir / "v1_v2_v3_paper_comparison.md", comparison_rows)

    v3_result = version_results["v3"]
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
            }
            for row in v3_result["event_rows"]
        ],
    )
    write_csv(processed_dir / "spy_prices.csv", price_rows)
    write_json(latest_dir / "version_summaries.json", version_summaries)
    (latest_dir / "gap_hypotheses.md").write_text(
        "\n".join(
            f"- {item}"
            for item in build_gap_hypotheses(
                version_results["v2"]["summaries"],
                v3_result["summaries"],
                v3_result["search_audit_rows"],
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
        replication_gaps=build_replication_gaps(v3_result["search_audit_rows"]),
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
