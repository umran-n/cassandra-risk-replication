from __future__ import annotations

import argparse
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
    summarize_strategy
)
from cassandra_risk.clients import fetch_spy_prices  # noqa: E402
from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.events import aggregate_daily_probabilities, build_event_metadata, build_event_panel  # noqa: E402
from cassandra_risk.reporting import render_report  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_csv, write_json  # noqa: E402


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Refresh raw data from public APIs")
    args = parser.parse_args()

    config = load_json(ROOT / "config" / "backtest_config.json")
    seeds = load_json(ROOT / "data" / "seeds" / "event_seeds.json")

    raw_dir = ensure_dir(ROOT / "data" / "raw")
    processed_dir = ensure_dir(ROOT / "data" / "processed")
    output_dir = ensure_dir(ROOT / "outputs" / "latest")

    price_rows = fetch_spy_prices(config, raw_dir, refresh=args.refresh)
    event_rows = build_event_panel(config, seeds, raw_dir, refresh=args.refresh)
    event_metadata = build_event_metadata(event_rows)
    daily_events = aggregate_daily_probabilities(event_rows)

    dates, _, price_returns = compute_price_returns(price_rows)
    buy_hold_positions = compute_buy_hold_positions(dates)
    vol_target_positions = compute_vol_target_positions(config, price_returns)
    base_rsi, base_hazard, threshold_events = compute_cassandra_signal(dates, daily_events, config)

    transaction_cost_bps = float(config["transaction_cost_bps"])
    buy_hold_result = simulate_strategy(dates, price_returns, buy_hold_positions, transaction_cost_bps)
    vol_target_result = simulate_strategy(dates, price_returns, vol_target_positions, transaction_cost_bps)
    cassandra_result = simulate_strategy(dates, price_returns, base_rsi, transaction_cost_bps)

    summaries = {
        "buy_hold": summarize_strategy(buy_hold_result),
        "vol_target": summarize_strategy(vol_target_result),
        "cassandra": summarize_strategy(cassandra_result)
    }
    summaries["cassandra"]["paranoia_tax"] = summaries["cassandra"]["cagr"] - summaries["buy_hold"]["cagr"]

    metrics_rows = metrics_table(summaries)
    comparison_rows = compare_to_paper(summaries, config["paper_metrics"])
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
        summary = summarize_strategy(scenario_result)
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
        seed=int(config["bootstrap"]["seed"])
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
    write_csv(output_dir / "threshold_events.csv", threshold_events)
    write_csv(
        output_dir / "equity_curves.csv",
        series_rows("buy_hold", buy_hold_result)
        + series_rows("vol_target", vol_target_result)
        + series_rows("cassandra", cassandra_result, {"rsi": base_rsi, "hazard": base_hazard})
    )
    write_json(output_dir / "event_metadata.json", event_metadata)
    write_json(output_dir / "summary.json", summaries)

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
    print("Headline metrics:")
    for name, summary in summaries.items():
        print(
            f"  {name}: CAGR={summary['cagr']:.4f}, MDD={summary['max_drawdown']:.4f}, "
            f"Sortino={summary['sortino']:.3f}, AvgPos={summary['avg_position']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
