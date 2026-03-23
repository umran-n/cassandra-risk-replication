from __future__ import annotations

import argparse
import csv
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
    max_drawdown,
    metrics_table,
    monthly_resampled_equity,
    simulate_strategy,
    summarize_strategy
)
from cassandra_risk.clients import fetch_fred_tb3ms, fetch_spy_prices  # noqa: E402
from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.events import aggregate_daily_probabilities, build_event_metadata, build_event_panel  # noqa: E402
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
            "equity": result["equity"][idx]
        }
        for key, values in extra.items():
            row[key] = values[idx]
        rows.append(row)
    return rows


def build_replication_gaps() -> list[str]:
    return [
        "The paper does not publish the full archived 2020-2022 prediction-market history, so several events are manually reconstructed from dates, categories, and peak probabilities disclosed in the paper.",
        "Metaculus historical question access was not publicly available from this environment, so the recovered archive subset comes from Manifold only.",
        "Category-level decay parameters are not fully disclosed in the paper; the base run uses a documented uniform lambda of 0.10 with sensitivity scenarios around that choice.",
        "The paper's Brier-score section is replicated structurally rather than exactly because the underlying 47-event resolved forecast panel is not published.",
        "Some paper events, especially the October 2023 and August/November 2024 episodes, required manual question reconstruction because no unambiguous public market identifiers were recoverable."
    ]


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


def load_previous_summary(v1_dir: Path) -> dict | None:
    summary_path = v1_dir / "summary.json"
    equity_path = v1_dir / "equity_curves.csv"
    if not summary_path.exists():
        return None
    summary = load_json(summary_path)
    if not equity_path.exists():
        return summary

    curves: dict[str, dict[str, list[float] | list[str]]] = {}
    with equity_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            bucket = curves.setdefault(row["strategy"], {"dates": [], "equity": []})
            bucket["dates"].append(row["date"])
            bucket["equity"].append(float(row["equity"]))

    for strategy in ("buy_hold", "vol_target", "cassandra"):
        if strategy not in summary or strategy not in curves:
            continue
        dates = curves[strategy]["dates"]
        equity = curves[strategy]["equity"]
        summary[strategy]["max_drawdown_daily"] = summary[strategy].get("max_drawdown")
        summary[strategy]["max_drawdown_monthly"] = max_drawdown(monthly_resampled_equity(dates, equity))
    summary.get("cassandra", {}).setdefault(
        "paranoia_tax",
        summary["cassandra"]["cagr"] - summary["buy_hold"]["cagr"],
    )
    return summary


def build_v1_v2_paper_comparison(v1_summary: dict | None, v2_summary: dict, paper_metrics: dict) -> list[dict]:
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
            v1_value = None if v1_summary is None else v1_summary.get(strategy, {}).get(metric)
            v2_value = v2_summary.get(strategy, {}).get(metric)
            if metric == "max_drawdown_daily":
                paper_value = None
            elif metric == "max_drawdown_monthly":
                paper_value = paper_metrics[paper_key].get("max_drawdown")
            else:
                paper_value = paper_metrics[paper_key].get(metric)
            if v1_value is None and v2_value is None and paper_value is None:
                continue
            rows.append(
                {
                    "strategy": strategy,
                    "metric": metric,
                    "v1": v1_value,
                    "v2": v2_value,
                    "paper": paper_value,
                    "v2_minus_v1": None if v1_value is None or v2_value is None else v2_value - v1_value,
                    "v2_minus_paper": None if paper_value is None or v2_value is None else v2_value - paper_value,
                }
            )
    return rows


def build_gap_hypotheses(v2_summary: dict, paper_metrics: dict, risk_free_source: str) -> list[str]:
    return [
        (
            "Buy & Hold still diverges from the paper on CAGR and drawdown. "
            f"Hypothesis: the paper likely used a different baseline construction, sample window, or month-end aggregation convention than raw Yahoo adjusted-close SPY."
        ),
        (
            "Cassandra average position remains materially above the paper's 73%. "
            "Hypothesis: the missing Metaculus archive and the manual event reconstructions still understate the amount of time the model should spend de-risked."
        ),
        (
            "Cassandra CAGR remains well above the paper despite the lambda and Sortino fixes. "
            "Hypothesis: the hybrid event panel is still too sparse and too concentrated in high-value protective episodes, so it captures downside without enough false-positive drag."
        ),
        (
            f"Sortino now uses {risk_free_source}. "
            "Hypothesis for any remaining Sortino gap: the paper may use a different excess-return convention, monthly risk-free interpolation, or downside-target definition than this implementation."
        ),
        (
            "The paper's reported MDD now lines up better conceptually with monthly-resampled drawdown. "
            "Hypothesis for any residual gap: the paper likely computed MDD from monthly portfolio series rather than from daily equity paths."
        ),
    ]


def render_v1_v2_paper_markdown(path: Path, rows: list[dict]) -> None:
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
    with path.open("w", encoding="utf-8") as handle:
        handle.write("| Strategy | Metric | V1 | V2 | Paper |\n")
        handle.write("| --- | --- | ---: | ---: | ---: |\n")
        for row in rows:
            def render(metric: str, value: float | None) -> str:
                if value is None:
                    return "n/a"
                if metric in percentage_metrics:
                    return f"{value * 100:.2f}%"
                if "days" in metric:
                    return str(int(round(value)))
                return f"{value:.3f}"

            handle.write(
                f"| {row['strategy']} | {row['metric']} | {render(row['metric'], row['v1'])} | "
                f"{render(row['metric'], row['v2'])} | {render(row['metric'], row['paper'])} |\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Refresh raw data from public APIs")
    args = parser.parse_args()

    config = load_json(ROOT / "config" / "backtest_config.json")
    seeds = load_json(ROOT / "data" / "seeds" / "event_seeds.json")

    raw_dir = ensure_dir(ROOT / "data" / "raw")
    processed_dir = ensure_dir(ROOT / "data" / "processed")
    output_dir = ensure_dir(ROOT / "outputs" / "latest")
    v1_dir = ROOT / "outputs" / "v1"

    previous_summary = load_previous_summary(v1_dir)

    price_rows = fetch_spy_prices(config, raw_dir, refresh=args.refresh)
    event_rows = build_event_panel(config, seeds, raw_dir, refresh=args.refresh)
    event_metadata = build_event_metadata(event_rows)
    daily_events = aggregate_daily_probabilities(event_rows)

    dates, _, price_returns = compute_price_returns(price_rows)
    fallback_annual_rate = float(config["risk_free_rate"]["fallback_annual_rate"])
    try:
        fred_rows = fetch_fred_tb3ms(raw_dir, refresh=args.refresh)
        risk_free_annual_rates = build_daily_risk_free_series(dates, fred_rows, fallback_annual_rate)
        risk_free_source = "FRED TB3MS"
    except Exception:
        fred_rows = []
        risk_free_annual_rates = [fallback_annual_rate] * len(dates)
        risk_free_source = "fallback 4.31% annualized"

    buy_hold_positions = compute_buy_hold_positions(dates)
    vol_target_positions = compute_vol_target_positions(config, price_returns)
    base_rsi, base_hazard, threshold_events = compute_cassandra_signal(dates, daily_events, config)

    transaction_cost_bps = float(config["transaction_cost_bps"])
    buy_hold_result = simulate_strategy(dates, price_returns, buy_hold_positions, transaction_cost_bps)
    vol_target_result = simulate_strategy(dates, price_returns, vol_target_positions, transaction_cost_bps)
    cassandra_result = simulate_strategy(dates, price_returns, base_rsi, transaction_cost_bps)

    summaries = {
        "buy_hold": summarize_strategy(buy_hold_result, risk_free_annual_rates),
        "vol_target": summarize_strategy(vol_target_result, risk_free_annual_rates),
        "cassandra": summarize_strategy(cassandra_result, risk_free_annual_rates)
    }
    summaries["cassandra"]["paranoia_tax"] = summaries["cassandra"]["cagr"] - summaries["buy_hold"]["cagr"]

    metrics_rows = metrics_table(summaries)
    comparison_rows = compare_to_paper(summaries, config["paper_metrics"])
    v1_v2_paper_rows = build_v1_v2_paper_comparison(previous_summary, summaries, config["paper_metrics"])
    brier_rows = brier_score_summary(event_rows)
    event_analysis_rows = event_window_analysis(
        seeds,
        dates,
        price_returns,
        cassandra_result["positions"],
        base_rsi,
        daily_events
    )

    robustness_rows = []
    for scenario in config["cassandra"]["robustness_scenarios"]:
        rsi_values, _, _ = compute_cassandra_signal(
            dates,
            daily_events,
            config,
            lambda_scale=float(scenario["lambda_scale"]),
            probability_scale=float(scenario["probability_scale"])
        )
        scenario_result = simulate_strategy(dates, price_returns, rsi_values, transaction_cost_bps)
        summary = summarize_strategy(scenario_result, risk_free_annual_rates)
        robustness_rows.append(
            {
                "scenario": scenario["name"],
                "cagr": summary["cagr"],
                "max_drawdown": summary["max_drawdown"],
                "sortino": summary["sortino"],
                "avg_position": summary["avg_position"]
            }
        )

    bootstrap_rows = bootstrap_confidence_intervals(
        {
            "buy_hold": buy_hold_result["daily_returns"],
            "vol_target": vol_target_result["daily_returns"],
            "cassandra": cassandra_result["daily_returns"]
        },
        block_size=int(config["bootstrap"]["block_size"]),
        resamples=int(config["bootstrap"]["resamples"]),
        seed=int(config["bootstrap"]["seed"]),
        risk_free_annual_rates=risk_free_annual_rates
    )

    normalized_event_rows = [
        {
            "date": row["date"],
            "event_id": row["event_id"],
            "question": row["question"],
            "source": row["source"],
            "category": row["category"],
            "probability": row["probability"],
            "resolution_date": row["resolution_date"],
            "resolved_outcome": row["resolved_outcome"],
            "provenance": row["provenance"]
        }
        for row in event_rows
    ]
    write_csv(processed_dir / "event_panel.csv", normalized_event_rows)
    write_csv(processed_dir / "spy_prices.csv", price_rows)
    write_csv(output_dir / "metrics.csv", metrics_rows)
    write_csv(output_dir / "paper_comparison.csv", comparison_rows)
    write_csv(output_dir / "bootstrap_intervals.csv", bootstrap_rows)
    write_csv(output_dir / "brier_scores.csv", brier_rows)
    write_csv(output_dir / "event_analysis.csv", event_analysis_rows)
    write_csv(output_dir / "robustness.csv", robustness_rows)
    write_csv(output_dir / "v1_v2_paper_comparison.csv", v1_v2_paper_rows)
    write_csv(output_dir / "threshold_events.csv", threshold_events)
    write_csv(
        output_dir / "equity_curves.csv",
        series_rows("buy_hold", buy_hold_result)
        + series_rows("vol_target", vol_target_result)
        + series_rows("cassandra", cassandra_result, {"rsi": base_rsi, "hazard": base_hazard})
    )
    write_json(output_dir / "event_metadata.json", event_metadata)
    write_json(output_dir / "summary.json", summaries)
    write_json(
        output_dir / "risk_free_summary.json",
        {
            "source": risk_free_source,
            "fallback_annual_rate": fallback_annual_rate,
            "observations": len(risk_free_annual_rates),
        },
    )
    render_v1_v2_paper_markdown(output_dir / "v1_v2_paper_comparison.md", v1_v2_paper_rows)
    (output_dir / "gap_hypotheses.md").write_text(
        "\n".join(f"- {item}" for item in build_gap_hypotheses(summaries, config["paper_metrics"], risk_free_source)),
        encoding="utf-8",
    )

    render_report(
        output_dir / "report.md",
        metrics_rows=metrics_rows,
        comparison_rows=comparison_rows,
        robustness_rows=robustness_rows,
        bootstrap_rows=bootstrap_rows,
        brier_rows=brier_rows,
        event_rows=event_analysis_rows,
        replication_gaps=build_replication_gaps()
    )

    print("Completed Cassandra-Risk closest-public replication.")
    print(f"Outputs written to: {output_dir}")
    print(f"Risk-free source: {risk_free_source}")
    print("Headline metrics:")
    for name, summary in summaries.items():
        print(
            f"  {name}: CAGR={summary['cagr']:.4f}, MDD={summary['max_drawdown']:.4f}, "
            f"Sortino={summary['sortino']:.3f}, AvgPos={summary['avg_position']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
