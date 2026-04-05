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
from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.events import load_polymarket_approved_universe  # noqa: E402
from cassandra_risk.kelly_weighting import apply_asymmetric_kelly_weighting, apply_kelly_weighting  # noqa: E402
from cassandra_risk.monetary_subablation import apply_theme_hazard_cap, remove_event_ids  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from run_backtest import compute_price_returns, fetch_fred_tb3ms, fetch_spy_prices, run_version  # noqa: E402


STACK_CONFIGS = {
    "V5_Becker_top5": {"becker": True, "top5_removal": True, "bucket_cap": None, "kelly_scale": None, "kelly_mode": None},
    "V5_Becker_cap30": {"becker": True, "top5_removal": False, "bucket_cap": 0.30, "kelly_scale": None, "kelly_mode": None},
    "V5_Becker_top5_cap": {"becker": True, "top5_removal": True, "bucket_cap": 0.30, "kelly_scale": None, "kelly_mode": None},
    "V5+Becker+Kelly25": {"becker": True, "top5_removal": True, "bucket_cap": 0.30, "kelly_scale": 0.25, "kelly_mode": "fractional"},
    "V5+Becker+Kelly50": {"becker": True, "top5_removal": True, "bucket_cap": 0.30, "kelly_scale": 0.50, "kelly_mode": "fractional"},
    "V5+Becker+Kelly": {"becker": True, "top5_removal": True, "bucket_cap": 0.30, "kelly_scale": 1.00, "kelly_mode": "fractional"},
    "V5+Becker+AsymKelly": {"becker": True, "top5_removal": True, "bucket_cap": 0.30, "kelly_scale": None, "kelly_mode": "asymmetric"},
}


def compose_daily_transform(
    *,
    enable_becker: bool,
    bucket_cap: float | None,
    kelly_scale: float | None = None,
    kelly_mode: str | None = None,
):
    if not enable_becker and bucket_cap is None and kelly_scale is None and kelly_mode is None:
        return None

    def transform(daily_events: dict[str, dict[str, dict]], config: dict, dates: list[str]):
        transformed = daily_events
        if enable_becker:
            transformed = apply_becker_calibration(transformed, config, dates)
        if kelly_mode == "fractional" and kelly_scale is not None:
            transformed = apply_kelly_weighting(transformed, config, dates, fraction_scale=float(kelly_scale))
        elif kelly_mode == "asymmetric":
            transformed = apply_asymmetric_kelly_weighting(transformed, config, dates)
        if bucket_cap is not None:
            transformed = apply_theme_hazard_cap(
                transformed,
                config,
                structural_theme="monetary_policy",
                cap_share=float(bucket_cap),
            )
        return transformed

    return transform


def stack_summary_row(
    version: str,
    *,
    calibration: str,
    top5_removal: bool,
    bucket_cap: float | None,
    kelly_scale: float | None,
    kelly_mode: str | None,
    result: dict,
) -> dict:
    summary = result["summaries"]["cassandra"]
    return {
        "version": version,
        "calibration": calibration,
        "top5_removal": top5_removal,
        "bucket_cap": "" if bucket_cap is None else bucket_cap,
        "kelly_weighting": kelly_scale is not None or kelly_mode is not None,
        "kelly_mode": "" if kelly_mode is None else kelly_mode,
        "kelly_scale": "" if kelly_scale is None else kelly_scale,
        "n_events": len(result["resolved_seeds"]),
        "sortino": summary["sortino"],
        "cagr": summary["cagr"],
        "mdd": summary["max_drawdown_daily"],
        "avg_position": summary["avg_position"],
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
        daily_events_transform=compose_daily_transform(enable_becker=True, bucket_cap=None),
    )

    rows = [
        stack_summary_row(
            "V5",
            calibration="off",
            top5_removal=False,
            bucket_cap=None,
            kelly_scale=None,
            kelly_mode=None,
            result=v5_result,
        ),
        stack_summary_row(
            "V5_Becker",
            calibration="enabled",
            top5_removal=False,
            bucket_cap=None,
            kelly_scale=None,
            kelly_mode=None,
            result=v5_becker_result,
        ),
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
                kelly_scale=settings["kelly_scale"],
                kelly_mode=settings["kelly_mode"],
            ),
        )
        rows.append(
            stack_summary_row(
                version,
                calibration="enabled" if settings["becker"] else "off",
                top5_removal=settings["top5_removal"],
                bucket_cap=settings["bucket_cap"],
                kelly_scale=settings["kelly_scale"],
                kelly_mode=settings["kelly_mode"],
                result=result,
            )
        )

    write_csv(output_dir / "becker_stack_summary.csv", rows)

    print("Completed Becker stack backtests.")
    for row in rows:
        print(
            f"{row['version']}: calibration={row['calibration']}, top5_removal={row['top5_removal']}, "
            f"bucket_cap={row['bucket_cap']}, n_events={row['n_events']}, sortino={row['sortino']:.3f}, "
            f"cagr={row['cagr']:.4f}, mdd={row['mdd']:.4f}, avg_position={row['avg_position']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
