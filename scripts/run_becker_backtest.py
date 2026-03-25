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

from cassandra_risk.becker_calibration import apply_becker_calibration  # noqa: E402
from cassandra_risk.becker_figures import render_becker_delta  # noqa: E402
from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.events import load_polymarket_approved_universe  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from run_backtest import compute_price_returns, fetch_fred_tb3ms, fetch_spy_prices, run_version  # noqa: E402


def summary_row(version: str, calibration: str, n_events: int, result: dict) -> dict:
    summary = result["summaries"]["cassandra"]
    return {
        "version": version,
        "calibration": calibration,
        "n_events": n_events,
        "sortino": summary["sortino"],
        "cagr": summary["cagr"],
        "mdd": summary["max_drawdown_daily"],
        "avg_position": summary["avg_position"],
    }


def main() -> int:
    base_config = load_json(ROOT / "config" / "backtest_config.json")
    approved_payload = load_json(ROOT / "data" / "curated" / "polymarket_approved.json")
    approved_seeds, approved_audit = load_polymarket_approved_universe(
        ROOT / "data" / "curated" / "polymarket_approved.json",
        ROOT / "data" / "candidates" / "polymarket_candidates.json",
    )

    raw_dir = ensure_dir(ROOT / "data" / "raw")
    output_dir = ensure_dir(ROOT / "outputs" / "becker")

    price_rows = fetch_spy_prices(base_config, raw_dir, refresh=False)
    dates, _, price_returns = compute_price_returns(price_rows)

    fallback_annual_rate = float(base_config["risk_free_rate"]["fallback_annual_rate"])
    try:
        fred_rows = fetch_fred_tb3ms(raw_dir, refresh=False)
        fred_fetch_succeeded = True
    except Exception:
        fred_rows = []
        fred_fetch_succeeded = False

    v5_result = run_version(
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

    becker_config = copy.deepcopy(base_config)
    becker_config.setdefault("becker_calibration", {})["enabled"] = True
    v5_becker_result = run_version(
        version="v3",
        base_config=becker_config,
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
        daily_events_transform=apply_becker_calibration,
    )

    rows = [
        summary_row("V5", "off", len(approved_payload), v5_result),
        summary_row("V5_Becker", "enabled", len(approved_payload), v5_becker_result),
    ]
    write_csv(output_dir / "becker_summary.csv", rows)
    render_becker_delta(rows, output_dir / "fig_becker_delta.png")

    print("Completed Becker-calibrated V5 backtest.")
    for row in rows:
        print(
            f"{row['version']}: calibration={row['calibration']}, n_events={row['n_events']}, "
            f"sortino={row['sortino']:.3f}, cagr={row['cagr']:.4f}, mdd={row['mdd']:.4f}, avg_position={row['avg_position']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
