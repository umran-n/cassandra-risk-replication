from __future__ import annotations

import copy
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
from cassandra_risk.monetary_subablation import (  # noqa: E402
    apply_theme_hazard_cap,
    compress_monetary_by_phase,
    count_monetary_events,
    remove_event_ids,
)
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from run_backtest import compute_price_returns, fetch_fred_tb3ms, fetch_spy_prices, run_version  # noqa: E402


def summary_row(test_name: str, result: dict) -> dict:
    summary = result["summaries"]["cassandra"]
    return {
        "test": test_name,
        "n_monetary_events": count_monetary_events(result["resolved_seeds"]),
        "sortino": summary["sortino"],
        "cagr": summary["cagr"],
        "mdd": summary["max_drawdown_daily"],
        "avg_position": summary["avg_position"],
    }


def main() -> int:
    base_config = load_json(ROOT / "config" / "backtest_config.json")
    approved_entries = load_json(ROOT / "data" / "curated" / "polymarket_approved.json")
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

    compressed_seeds, _phase_selection = compress_monetary_by_phase(approved_entries, approved_seeds)
    test_a_result = run_version(
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
        extra_curated_seeds=compressed_seeds,
        extra_curated_audit=approved_audit,
        include_robustness=False,
        include_bootstrap=False,
    )

    # Use the ranked event-level diagnostic output from the baseline attribution.
    event_totals: dict[str, float] = {}
    for row in baseline_result["hazard_attribution_rows"]:
        if row.get("structural_theme") != "monetary_policy":
            continue
        event_totals[row["event_id"]] = event_totals.get(row["event_id"], 0.0) + float(row["hazard_contribution"])
    top_five_event_ids = {
        event_id for event_id, _value in sorted(event_totals.items(), key=lambda item: (-item[1], item[0]))[:5]
    }
    top_removed_seeds = remove_event_ids(approved_seeds, top_five_event_ids)
    test_b_result = run_version(
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
        extra_curated_seeds=top_removed_seeds,
        extra_curated_audit=approved_audit,
        include_robustness=False,
        include_bootstrap=False,
    )

    test_c_result = run_version(
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
        daily_events_transform=lambda daily_events, config, _dates: apply_theme_hazard_cap(
            daily_events,
            config,
            structural_theme="monetary_policy",
            cap_share=0.30,
        ),
    )

    rows = [
        summary_row("family_compression", test_a_result),
        summary_row("top_5_removal", test_b_result),
        summary_row("bucket_cap_30pct", test_c_result),
    ]
    write_csv(output_dir / "monetary_subablation.csv", rows)

    print("Completed monetary-policy sub-ablation.")
    for row in rows:
        print(
            f"{row['test']}: n_monetary_events={row['n_monetary_events']}, sortino={row['sortino']:.3f}, "
            f"cagr={row['cagr']:.4f}, mdd={row['mdd']:.4f}, avg_position={row['avg_position']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
