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

from cassandra_risk.backtest import monthly_drawdown_episode_stats  # noqa: E402
from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.events import load_polymarket_approved_universe  # noqa: E402
from cassandra_risk.monetary_subablation import remove_event_ids  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from run_becker_stack import STACK_CONFIGS, compose_daily_transform  # noqa: E402
from run_backtest import compute_price_returns, fetch_fred_tb3ms, fetch_spy_prices, run_version  # noqa: E402


def risk_row(version: str, result: dict) -> dict:
    summary = result["summaries"]["cassandra"]
    episode_stats = monthly_drawdown_episode_stats(
        result["cassandra_result"]["dates"],
        result["cassandra_result"]["equity"],
    )
    return {
        "version": version,
        "sortino": summary["sortino"],
        "downside_dev": summary["downside_deviation"],
        "cvar_95": summary["cvar_95"],
        "monthly_mdd_mean": episode_stats["monthly_mdd_mean"],
        "monthly_mdd_worst": episode_stats["monthly_mdd_worst"],
    }


def main() -> int:
    base_config = load_json(ROOT / "config" / "backtest_config.json")
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

    event_totals: dict[str, float] = {}
    for row in v5_result["hazard_attribution_rows"]:
        if row.get("structural_theme") != "monetary_policy":
            continue
        event_totals[row["event_id"]] = event_totals.get(row["event_id"], 0.0) + float(row["hazard_contribution"])
    top_five_event_ids = {
        event_id for event_id, _value in sorted(event_totals.items(), key=lambda item: (-item[1], item[0]))[:5]
    }

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
        daily_events_transform=compose_daily_transform(enable_becker=True, bucket_cap=None, enable_kelly=False),
    )

    rows = [
        risk_row("V5", v5_result),
        risk_row("V5_Becker", v5_becker_result),
    ]

    for version, settings in STACK_CONFIGS.items():
        seeds = approved_seeds
        if settings["top5_removal"]:
            seeds = remove_event_ids(seeds, top_five_event_ids)
        result = run_version(
            version="v3",
            base_config=becker_config if settings["becker"] else base_config,
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
            extra_curated_seeds=seeds,
            extra_curated_audit=approved_audit,
            include_robustness=False,
            include_bootstrap=False,
            daily_events_transform=compose_daily_transform(
                enable_becker=settings["becker"],
                bucket_cap=settings["bucket_cap"],
                enable_kelly=settings["kelly"],
            ),
        )
        rows.append(risk_row(version, result))

    write_csv(output_dir / "risk_decomposition.csv", rows)

    print("Completed Becker stack risk decomposition.")
    for row in rows:
        print(
            f"{row['version']}: sortino={row['sortino']:.3f}, downside_dev={row['downside_dev']:.4f}, "
            f"cvar_95={row['cvar_95']:.4f}, monthly_mdd_mean={row['monthly_mdd_mean']:.4f}, "
            f"monthly_mdd_worst={row['monthly_mdd_worst']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
