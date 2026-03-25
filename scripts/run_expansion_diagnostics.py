from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.events import load_polymarket_approved_universe  # noqa: E402
from cassandra_risk.expansion_diagnostics import (  # noqa: E402
    filter_out_theme,
    monetary_concentration_rows,
    quarterly_drag_rows,
    render_diagnostic_report,
    theme_ablation_row,
)
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from run_backtest import compute_price_returns, fetch_fred_tb3ms, fetch_spy_prices, run_version  # noqa: E402


def main() -> int:
    base_config = load_json(ROOT / "config" / "backtest_config.json")
    approved_seeds, approved_audit = load_polymarket_approved_universe(
        ROOT / "data" / "curated" / "polymarket_approved.json",
        ROOT / "data" / "candidates" / "polymarket_candidates.json",
    )

    raw_dir = ensure_dir(ROOT / "data" / "raw")
    output_dir = ensure_dir(ROOT / "outputs" / "expansion")

    price_rows = fetch_spy_prices(base_config, raw_dir, refresh=False)
    dates, _, price_returns = compute_price_returns(price_rows)

    fallback_annual_rate = float(base_config["risk_free_rate"]["fallback_annual_rate"])
    try:
        fred_rows = fetch_fred_tb3ms(raw_dir, refresh=False)
        fred_fetch_succeeded = True
    except Exception:
        fred_rows = []
        fred_fetch_succeeded = False

    baseline_result = run_version(
        version="v3",
        base_config=base_config,
        base_seeds=[],
        shortlist=[],
        dates=dates,
        price_returns=price_returns,
        price_rows=price_rows,
        raw_dir=raw_dir,
        refresh=False,
        fred_rows=fred_rows,
        fallback_annual_rate=fallback_annual_rate,
        fred_fetch_succeeded=fred_fetch_succeeded,
        extra_curated_seeds=approved_seeds,
        extra_curated_audit=approved_audit,
        include_robustness=False,
        include_bootstrap=False,
    )

    theme_rows: list[dict] = []
    for theme_removed in ("monetary_policy", "geopolitical", "electoral"):
        filtered_seeds = filter_out_theme(approved_seeds, theme_removed)
        filtered_result = run_version(
            version="v3",
            base_config=base_config,
            base_seeds=[],
            shortlist=[],
            dates=dates,
            price_returns=price_returns,
            price_rows=price_rows,
            raw_dir=raw_dir,
            refresh=False,
            fred_rows=fred_rows,
            fallback_annual_rate=fallback_annual_rate,
            fred_fetch_succeeded=fred_fetch_succeeded,
            extra_curated_seeds=filtered_seeds,
            extra_curated_audit=approved_audit,
            include_robustness=False,
            include_bootstrap=False,
        )
        theme_rows.append(theme_ablation_row(theme_removed, filtered_result))

    monetary_rows = monetary_concentration_rows(baseline_result["hazard_attribution_rows"])
    quarter_rows = quarterly_drag_rows(
        dates,
        baseline_result["daily_rsi_decomposition_rows"],
        baseline_result["cassandra_result"]["positions"],
        price_returns,
        baseline_result["cassandra_result"]["daily_returns"],
        start_quarter="2022Q1",
        end_quarter="2024Q4",
    )

    write_csv(output_dir / "theme_ablation.csv", theme_rows)
    write_csv(output_dir / "monetary_concentration.csv", monetary_rows)
    write_csv(output_dir / "rsi_drag_by_quarter.csv", quarter_rows)
    render_diagnostic_report(
        output_dir / "diagnostic_report.md",
        baseline_result=baseline_result,
        approved_audit=approved_audit,
        theme_rows=theme_rows,
        monetary_rows=monetary_rows,
        quarter_rows=quarter_rows,
    )

    print("Completed V5 expansion diagnostics.")
    print(f"Outputs written to: {output_dir}")
    for row in theme_rows:
        print(
            f"remove_{row['theme_removed']}: n_events={row['n_events']}, sortino={row['sortino']:.3f}, "
            f"cagr={row['cagr']:.4f}, mdd={row['mdd']:.4f}, avg_position={row['avg_position']:.4f}"
        )
    if monetary_rows:
        top = monetary_rows[0]
        print(
            f"top_monetary={top['event_id']}, cumulative_hazard={top['cumulative_hazard']:.3f}, "
            f"theme_share={top['hazard_share_within_theme']:.4f}"
        )
    flagged = [row for row in quarter_rows if row["missed_recovery_flag"]]
    print(f"flagged_quarters={len(flagged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
