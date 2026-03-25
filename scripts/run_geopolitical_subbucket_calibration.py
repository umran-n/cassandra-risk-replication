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
from cassandra_risk.geopolitical_subbucket_calibration import GEO_SUBBUCKET_GAPS  # noqa: E402
from cassandra_risk.monetary_subablation import remove_event_ids  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from run_backtest import compute_price_returns, fetch_fred_tb3ms, fetch_spy_prices, run_version  # noqa: E402
from run_geopolitical_expansion import compose_transform, top_five_monetary_event_ids  # noqa: E402


def summary_row(version: str, result: dict, baseline: dict | None = None) -> dict:
    summary = result["summaries"]["cassandra"]
    row = {
        "version": version,
        "n_events": len(result["resolved_seeds"]),
        "sortino": summary["sortino"],
        "cagr": summary["cagr"],
        "mdd": summary["max_drawdown_daily"],
        "avg_position": summary["avg_position"],
    }
    if baseline is not None:
        row["sortino_delta"] = row["sortino"] - baseline["sortino"]
        row["cagr_delta"] = row["cagr"] - baseline["cagr"]
        row["mdd_delta"] = row["mdd"] - baseline["mdd"]
        row["avg_position_delta"] = row["avg_position"] - baseline["avg_position"]
    return row


def render_report(path: Path, summary_rows: list[dict]) -> None:
    by_version = {row["version"]: row for row in summary_rows}
    lines = [
        "# Phase 5.7 Geopolitical Sub-Bucket Calibration Report",
        "",
        "This experiment holds the governed geopolitical add-on set fixed and changes only the calibration granularity.",
        "",
        "## Comparison",
        "",
        "| Version | Loaded Events | Sortino | CAGR | Daily MDD | Avg Position |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['version']} | {row['n_events']} | {row['sortino']:.3f} | {row['cagr'] * 100:.2f}% | "
            f"{row['mdd'] * 100:.2f}% | {row['avg_position'] * 100:.2f}% |"
        )
    flat = by_version["V5_Becker_top5_cap_geo_flat"]
    subbucket = by_version["V5_Becker_top5_cap_geo_subbucket"]
    lines.extend(
        [
            "",
            "## Readout",
            "",
            f"- Flat calibrated geo vs published best row: Sortino `{flat['sortino_delta']:+.3f}`, CAGR `{flat['cagr_delta'] * 100:+.2f}pp`.",
            f"- Sub-bucket calibrated geo vs published best row: Sortino `{subbucket['sortino_delta']:+.3f}`, CAGR `{subbucket['cagr_delta'] * 100:+.2f}pp`.",
            f"- Sub-bucket delta over flat geo calibration: Sortino `{subbucket['sortino'] - flat['sortino']:+.3f}`, CAGR `{(subbucket['cagr'] - flat['cagr']) * 100:+.2f}pp`.",
            "",
            "## Sub-Bucket Constants",
            "",
            "| Sub-Bucket | Becker Gap | Longshot Band | Horizon Profile |",
            "| --- | ---: | --- | --- |",
        ]
    )
    for name, payload in GEO_SUBBUCKET_GAPS.items():
        lower, upper = payload["longshot_band"]
        lines.append(
            f"| {name} | {payload['becker_gap']:.4f} | ({lower:.2f}, {upper:.2f}) | {payload['horizon_profile']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    base_config = load_json(ROOT / "config" / "backtest_config.json")
    geopolitical_policy = load_json(ROOT / "config" / "geopolitical_admission_policy.json")

    approved_seeds, approved_audit = load_polymarket_approved_universe(
        ROOT / "data" / "curated" / "polymarket_approved.json",
        ROOT / "data" / "candidates" / "polymarket_candidates.json",
    )
    geopolitical_seeds, geopolitical_audit = load_polymarket_approved_universe(
        ROOT / "data" / "curated" / "polymarket_geopolitical_expansion.json",
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
    geo_stack_seeds = baseline_seeds + geopolitical_seeds
    geo_stack_audit = approved_audit + geopolitical_audit

    base_becker = copy.deepcopy(base_config)
    base_becker.setdefault("becker_calibration", {})["enabled"] = True

    flat_geo_config = copy.deepcopy(base_becker)
    flat_geo_config["becker_calibration"]["theme_longshot_thresholds"] = {
        "geopolitical": list(geopolitical_policy["longshot_threshold"]),
    }

    subbucket_geo_config = copy.deepcopy(flat_geo_config)
    subbucket_geo_config["becker_calibration"]["subbucket_efficiency_gaps"] = {
        key: float(value["becker_gap"])
        for key, value in GEO_SUBBUCKET_GAPS.items()
    }
    subbucket_geo_config["becker_calibration"]["subbucket_longshot_thresholds"] = {
        key: list(value["longshot_band"])
        for key, value in GEO_SUBBUCKET_GAPS.items()
    }

    results = {}
    results["V5_Becker_top5_cap_geo"] = run_version(
        version="v3",
        base_config=base_becker,
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
        extra_curated_seeds=geo_stack_seeds,
        extra_curated_audit=geo_stack_audit,
        include_robustness=False,
        include_bootstrap=False,
        daily_events_transform=compose_transform(
            enable_becker=True,
            monetary_bucket_cap=0.30,
            geopolitical_bucket_cap=None,
        ),
    )
    results["V5_Becker_top5_cap_geo_flat"] = run_version(
        version="v3",
        base_config=flat_geo_config,
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
        extra_curated_seeds=geo_stack_seeds,
        extra_curated_audit=geo_stack_audit,
        include_robustness=False,
        include_bootstrap=False,
        daily_events_transform=compose_transform(
            enable_becker=True,
            monetary_bucket_cap=0.30,
            geopolitical_bucket_cap=float(geopolitical_policy["bucket_cap"]),
        ),
    )
    results["V5_Becker_top5_cap_geo_subbucket"] = run_version(
        version="v3",
        base_config=subbucket_geo_config,
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
        extra_curated_seeds=geo_stack_seeds,
        extra_curated_audit=geo_stack_audit,
        include_robustness=False,
        include_bootstrap=False,
        daily_events_transform=compose_transform(
            enable_becker=True,
            monetary_bucket_cap=0.30,
            geopolitical_bucket_cap=float(geopolitical_policy["bucket_cap"]),
        ),
    )

    baseline_row = summary_row("V5_Becker_top5_cap_geo", results["V5_Becker_top5_cap_geo"])
    summary_rows = [baseline_row]
    for version in ("V5_Becker_top5_cap_geo_flat", "V5_Becker_top5_cap_geo_subbucket"):
        summary_rows.append(summary_row(version, results[version], baseline=baseline_row))

    write_csv(output_dir / "geopolitical_subbucket_summary.csv", summary_rows)
    render_report(output_dir / "geopolitical_subbucket_report.md", summary_rows)

    print("Completed geopolitical sub-bucket calibration backtests.")
    for row in summary_rows:
        print(
            f"{row['version']}: n_events={row['n_events']}, sortino={row['sortino']:.3f}, "
            f"cagr={row['cagr']:.4f}, mdd={row['mdd']:.4f}, avg_position={row['avg_position']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
