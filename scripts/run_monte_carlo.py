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
from cassandra_risk.monetary_subablation import remove_event_ids  # noqa: E402
from cassandra_risk.monte_carlo import (  # noqa: E402
    bootstrap_metric_samples,
    monte_carlo_summary_rows,
    render_sortino_distribution,
)
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from run_backtest import compute_price_returns, fetch_fred_tb3ms, fetch_spy_prices, run_version  # noqa: E402
from run_geopolitical_expansion import compose_transform, top_five_monetary_event_ids  # noqa: E402


BLOCK_LENGTH = 20
SAMPLES = 500


def build_best_strategy_result() -> dict:
    base_config = load_json(ROOT / "config" / "backtest_config.json")

    approved_seeds, approved_audit = load_polymarket_approved_universe(
        ROOT / "data" / "curated" / "polymarket_approved.json",
        ROOT / "data" / "candidates" / "polymarket_candidates.json",
    )
    geopolitical_seeds, geopolitical_audit = load_polymarket_approved_universe(
        ROOT / "data" / "curated" / "polymarket_geopolitical_expansion.json",
        ROOT / "data" / "candidates" / "polymarket_candidates.json",
    )

    raw_dir = ensure_dir(ROOT / "data" / "raw")
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
    top_five_event_ids = top_five_monetary_event_ids(v5_result)
    baseline_seeds = remove_event_ids(approved_seeds, top_five_event_ids)

    becker_config = copy.deepcopy(base_config)
    becker_config.setdefault("becker_calibration", {})["enabled"] = True

    return run_version(
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
        extra_curated_seeds=baseline_seeds + geopolitical_seeds,
        extra_curated_audit=approved_audit + geopolitical_audit,
        include_robustness=False,
        include_bootstrap=False,
        daily_events_transform=compose_transform(
            enable_becker=True,
            monetary_bucket_cap=0.30,
            geopolitical_bucket_cap=None,
        ),
    )


def main() -> int:
    output_dir = ensure_dir(ROOT / "outputs" / "monte_carlo")
    result = build_best_strategy_result()

    returns = result["cassandra_result"]["daily_returns"]
    risk_free_annual_rates = result["risk_free_annual_rates"]
    observed_summary = result["summaries"]["cassandra"]
    observed = {
        "sortino": float(observed_summary["sortino"]),
        "cagr": float(observed_summary["cagr"]),
        "mdd": float(observed_summary["max_drawdown_daily"]),
        "downside_deviation": float(observed_summary["downside_deviation"]),
    }

    seed = int(result["config"]["bootstrap"]["seed"])
    metric_samples = bootstrap_metric_samples(
        returns,
        risk_free_annual_rates,
        block_length=BLOCK_LENGTH,
        samples=SAMPLES,
        seed=seed,
    )
    summary_rows = monte_carlo_summary_rows(observed, metric_samples)
    write_csv(output_dir / "mc_summary.csv", summary_rows)

    sortino_row = next(row for row in summary_rows if row["metric"] == "sortino")
    render_sortino_distribution(
        output_dir / "fig_mc_sortino_distribution.png",
        metric_samples["sortino"],
        observed=observed["sortino"],
        ci_lower=float(sortino_row["ci_lower_95"]),
        ci_upper=float(sortino_row["ci_upper_95"]),
        p_value=float(sortino_row["p_value"]),
    )

    print("Monte Carlo robustness test complete.")
    for row in summary_rows:
        p_value = row["p_value"]
        p_text = "" if p_value == "" else f", p_value={float(p_value):.4f}"
        print(
            f"{row['metric']}: observed={float(row['observed']):.6f}, mean_boot={float(row['mean_boot']):.6f}, "
            f"ci95=({float(row['ci_lower_95']):.6f}, {float(row['ci_upper_95']):.6f}){p_text}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
