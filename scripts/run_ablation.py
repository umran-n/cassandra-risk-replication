from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cassandra_risk.ablation import (  # noqa: E402
    dominant_proxy_by_event_from_attribution_rows,
    force_config_aggregation,
    load_csv_rows,
    multi_proxy_event_ids,
    prepare_ablation_inputs,
    render_ablation_report,
    summarize_ablation_run,
)
from cassandra_risk.ablation_figures import render_ablation_figures  # noqa: E402
from cassandra_risk.clients import fetch_fred_tb3ms, fetch_spy_prices  # noqa: E402
from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.events import load_curated_shortlist  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from cassandra_risk.backtest import compute_price_returns  # noqa: E402
import run_backtest as replication_runner  # noqa: E402


STRUCTURAL_THEME_ORDER = [
    "geopolitical",
    "monetary_policy",
    "fiscal_debt",
    "electoral",
    "systemic_credit",
    "trade_technology",
]


def execute_ablation_run(
    run_id: str,
    notes: str,
    *,
    config: dict,
    seeds: list[dict],
    shortlist: list[dict],
    dates: list[str],
    price_returns: list[float],
    price_rows: list[dict],
    raw_dir: Path,
    refresh: bool,
    fred_rows: list[dict],
    fallback_annual_rate: float,
    fred_fetch_succeeded: bool,
) -> tuple[dict, dict]:
    runtime_config = force_config_aggregation(config, None)
    runtime_config["bootstrap"]["resamples"] = 0
    runtime_config["cassandra"]["robustness_scenarios"] = []
    result = replication_runner.run_version(
        version="v3",
        base_config=runtime_config,
        base_seeds=seeds,
        shortlist=shortlist,
        dates=dates,
        price_returns=price_returns,
        price_rows=price_rows,
        raw_dir=raw_dir,
        refresh=refresh,
        fred_rows=fred_rows,
        fallback_annual_rate=fallback_annual_rate,
        fred_fetch_succeeded=fred_fetch_succeeded,
    )
    return summarize_ablation_run(run_id, result, notes), result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Refresh raw data from public APIs")
    args = parser.parse_args()

    base_config = load_json(ROOT / "config" / "backtest_config.json")
    base_seeds = load_json(ROOT / "data" / "seeds" / "event_seeds.json")
    shortlist = load_curated_shortlist(ROOT / "data" / "curated" / "manifold_shortlist.json")

    raw_dir = ensure_dir(ROOT / "data" / "raw")
    output_dir = ensure_dir(ROOT / "outputs" / "ablation")

    price_rows = fetch_spy_prices(base_config, raw_dir, refresh=args.refresh)
    dates, _, price_returns = compute_price_returns(price_rows)

    fallback_annual_rate = float(base_config["risk_free_rate"]["fallback_annual_rate"])
    try:
        fred_rows = fetch_fred_tb3ms(raw_dir, refresh=args.refresh)
        fred_fetch_succeeded = True
    except Exception:
        fred_rows = []
        fred_fetch_succeeded = False

    ablation_rows: list[dict] = []

    baseline_seeds, baseline_shortlist = prepare_ablation_inputs(base_seeds, shortlist)
    baseline_row, baseline_result = execute_ablation_run(
        "aggregation_per_family",
        "Current per-family proxy governance baseline.",
        config=base_config,
        seeds=baseline_seeds,
        shortlist=baseline_shortlist,
        dates=dates,
        price_returns=price_returns,
        price_rows=price_rows,
        raw_dir=raw_dir,
        refresh=args.refresh,
        fred_rows=fred_rows,
        fallback_annual_rate=fallback_annual_rate,
        fred_fetch_succeeded=fred_fetch_succeeded,
    )

    def append_run(
        run_id: str,
        notes: str,
        *,
        public_only: bool = False,
        structural_theme: str | None = None,
        removed_event_ids: set[str] | None = None,
        dominant_proxy_by_event: dict[str, str] | None = None,
        forced_aggregation: str | None = None,
    ) -> tuple[dict, dict]:
        seeds, filtered_shortlist = prepare_ablation_inputs(
            base_seeds,
            shortlist,
            public_only=public_only,
            structural_theme=structural_theme,
            removed_event_ids=removed_event_ids,
            dominant_proxy_by_event=dominant_proxy_by_event,
            forced_aggregation=forced_aggregation,
        )
        config = force_config_aggregation(base_config, forced_aggregation)
        row, result = execute_ablation_run(
            run_id,
            notes,
            config=config,
            seeds=seeds,
            shortlist=filtered_shortlist,
            dates=dates,
            price_returns=price_returns,
            price_rows=price_rows,
            raw_dir=raw_dir,
            refresh=args.refresh,
            fred_rows=fred_rows,
            fallback_annual_rate=fallback_annual_rate,
            fred_fetch_succeeded=fred_fetch_succeeded,
        )
        ablation_rows.append(row)
        return row, result

    append_run(
        "no_manual_events",
        "Public approved shortlist only; manual reconstructed seeds removed.",
        public_only=True,
    )
    append_run(
        "top_event_removal_ukraine",
        "Removed ukraine_invasion_2022 from both seeds and shortlist.",
        removed_event_ids={"ukraine_invasion_2022"},
    )
    append_run(
        "top_event_removal_debt_ceiling",
        "Removed us_debt_ceiling_2023 from both seeds and shortlist.",
        removed_event_ids={"us_debt_ceiling_2023"},
    )
    append_run(
        "aggregation_max",
        "Forced max aggregation across all proxy families and events.",
        forced_aggregation="max",
    )
    append_run(
        "aggregation_weighted_average",
        "Forced weighted-average aggregation across all proxy families and events.",
        forced_aggregation="weighted_average",
    )
    ablation_rows.append(baseline_row)

    for theme in STRUCTURAL_THEME_ORDER:
        append_run(
            f"theme_{theme}_only",
            f"Only `{theme}` events active; all other structural themes removed.",
            structural_theme=theme,
        )

    hazard_path = ROOT / "outputs" / "latest" / "hazard_attribution.csv"
    hazard_rows = load_csv_rows(hazard_path)
    dominant_proxy_map = dominant_proxy_by_event_from_attribution_rows(hazard_rows)
    for event_id in multi_proxy_event_ids(shortlist):
        dominant_market_id = dominant_proxy_map.get(event_id)
        combined_row = baseline_row.copy()
        combined_row["run_id"] = f"single_proxy_{event_id}_all_combined"
        combined_row["notes"] = f"All approved proxies combined for `{event_id}` under the current per-family policy."
        ablation_rows.append(combined_row)
        if not dominant_market_id:
            missing_row = baseline_row.copy()
            missing_row["run_id"] = f"single_proxy_{event_id}_dominant_only"
            missing_row["notes"] = f"No dominant proxy could be inferred for `{event_id}` from outputs/latest/hazard_attribution.csv."
            ablation_rows.append(missing_row)
            continue
        append_run(
            f"single_proxy_{event_id}_dominant_only",
            f"Only dominant proxy `{dominant_market_id}` retained for `{event_id}`.",
            dominant_proxy_by_event={event_id: dominant_market_id},
        )

    write_csv(output_dir / "ablation_summary.csv", ablation_rows)
    render_ablation_report(
        output_dir / "ablation_report.md",
        baseline_row,
        ablation_rows,
        baseline_result["summaries"]["buy_hold"]["sortino"],
        baseline_result["summaries"]["vol_target"]["sortino"],
    )
    render_ablation_figures(output_dir / "ablation_summary.csv", output_dir)

    print("Completed Cassandra-Risk ablation harness.")
    print(f"Outputs written to: {output_dir}")
    print(
        f"Baseline per-family metrics: CAGR={baseline_row['CAGR']:.4f}, "
        f"Sortino={baseline_row['Sortino']:.3f}, MDD={baseline_row['MDD']:.4f}, "
        f"AvgPos={baseline_row['avg_position']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
