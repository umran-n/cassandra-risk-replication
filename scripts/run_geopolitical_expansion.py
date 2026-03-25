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
from cassandra_risk.geopolitical_expansion import GEO_ADMISSION_POLICY  # noqa: E402
from cassandra_risk.monetary_subablation import apply_theme_hazard_cap, remove_event_ids  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from run_backtest import compute_price_returns, fetch_fred_tb3ms, fetch_spy_prices, run_version  # noqa: E402


def compose_transform(
    *,
    enable_becker: bool,
    monetary_bucket_cap: float | None,
    geopolitical_bucket_cap: float | None,
) -> callable | None:
    if not enable_becker and monetary_bucket_cap is None and geopolitical_bucket_cap is None:
        return None

    def transform(daily_events: dict[str, dict[str, dict]], config: dict, dates: list[str]):
        transformed = daily_events
        if enable_becker:
            transformed = apply_becker_calibration(transformed, config, dates)
        if monetary_bucket_cap is not None:
            transformed = apply_theme_hazard_cap(
                transformed,
                config,
                structural_theme="monetary_policy",
                cap_share=float(monetary_bucket_cap),
            )
        if geopolitical_bucket_cap is not None:
            transformed = apply_theme_hazard_cap(
                transformed,
                config,
                structural_theme="geopolitical",
                cap_share=float(geopolitical_bucket_cap),
            )
        return transformed

    return transform


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


def top_five_monetary_event_ids(result: dict) -> set[str]:
    event_totals: dict[str, float] = {}
    for row in result["hazard_attribution_rows"]:
        if row.get("structural_theme") != "monetary_policy":
            continue
        event_id = row["event_id"]
        event_totals[event_id] = event_totals.get(event_id, 0.0) + float(row["hazard_contribution"])
    return {event_id for event_id, _value in sorted(event_totals.items(), key=lambda item: (-item[1], item[0]))[:5]}


def geopolitical_contribution_rows(result: dict, geopolitical_ids: set[str], version: str) -> list[dict]:
    total_hazard = sum(float(row["hazard_contribution"]) for row in result["hazard_attribution_rows"])
    geopolitical_total = sum(
        float(row["hazard_contribution"])
        for row in result["hazard_attribution_rows"]
        if row.get("structural_theme") == "geopolitical"
    )
    by_event: dict[str, dict] = {}
    for row in result["hazard_attribution_rows"]:
        if row["event_id"] not in geopolitical_ids:
            continue
        entry = by_event.setdefault(
            row["event_id"],
            {
                "version": version,
                "event_id": row["event_id"],
                "question": row["question"],
                "cumulative_hazard": 0.0,
                "first_date": row["date"],
                "last_date": row["date"],
            },
        )
        hazard = float(row["hazard_contribution"])
        entry["cumulative_hazard"] += hazard
        entry["first_date"] = min(entry["first_date"], row["date"])
        entry["last_date"] = max(entry["last_date"], row["date"])

    rows = []
    for entry in by_event.values():
        rows.append(
            {
                **entry,
                "total_hazard_share": 0.0 if total_hazard == 0 else entry["cumulative_hazard"] / total_hazard,
                "geopolitical_hazard_share": 0.0 if geopolitical_total == 0 else entry["cumulative_hazard"] / geopolitical_total,
            }
        )
    rows.sort(key=lambda row: (-row["cumulative_hazard"], row["event_id"]))
    return rows


def render_report(path: Path, summary_rows: list[dict], contribution_rows: list[dict]) -> None:
    by_version = {row["version"]: row for row in summary_rows}
    geo_plain = by_version["V5_Becker_top5_cap_geo"]
    geo_calibrated = by_version["V5_Becker_top5_cap_geo_calibrated"]
    lines = [
        "# Phase 5.6 Geopolitical Expansion Report",
        "",
        "This experiment tests a governed geopolitical add-on set against the published `V5_Becker_top5_cap` stack.",
        "",
        "## Stack Comparison",
        "",
        "| Version | Loaded Events | Sortino | CAGR | Daily MDD | Avg Position |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['version']} | {row['n_events']} | {row['sortino']:.3f} | {row['cagr'] * 100:.2f}% | "
            f"{row['mdd'] * 100:.2f}% | {row['avg_position'] * 100:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Readout",
            "",
            f"- `V5_geo_only` vs baseline stack: Sortino `{by_version['V5_geo_only']['sortino_delta']:+.3f}`, CAGR `{by_version['V5_geo_only']['cagr_delta'] * 100:+.2f}pp`.",
            f"- `V5_Becker_top5_cap_geo` vs baseline stack: Sortino `{geo_plain['sortino_delta']:+.3f}`, CAGR `{geo_plain['cagr_delta'] * 100:+.2f}pp`.",
            f"- `V5_Becker_top5_cap_geo_calibrated` vs baseline stack: Sortino `{geo_calibrated['sortino_delta']:+.3f}`, CAGR `{geo_calibrated['cagr_delta'] * 100:+.2f}pp`.",
            f"- Geopolitical calibration delta over uncalibrated geo stack: Sortino `{geo_calibrated['sortino'] - geo_plain['sortino']:+.3f}`, "
            f"CAGR `{(geo_calibrated['cagr'] - geo_plain['cagr']) * 100:+.2f}pp`.",
            "",
            "## Calibrated Add-On Hazard Contributors",
            "",
            "| Event | Cum Hazard | Share of Total Hazard | Share of Geopolitical Hazard | First Date | Last Date |",
            "| --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in contribution_rows:
        if row["version"] != "V5_Becker_top5_cap_geo_calibrated":
            continue
        lines.append(
            f"| {row['event_id']} | {row['cumulative_hazard']:.3f} | {row['total_hazard_share'] * 100:.2f}% | "
            f"{row['geopolitical_hazard_share'] * 100:.2f}% | {row['first_date']} | {row['last_date']} |"
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

    becker_config = copy.deepcopy(base_config)
    becker_config.setdefault("becker_calibration", {})["enabled"] = True

    geo_calibrated_config = copy.deepcopy(becker_config)
    geo_calibrated_config["becker_calibration"]["theme_longshot_thresholds"] = {
        "geopolitical": list(geopolitical_policy["longshot_threshold"]),
    }

    baseline_seeds = remove_event_ids(approved_seeds, top_five_event_ids)
    geopolitical_ids = {seed["event_id"] for seed in geopolitical_seeds}

    results = {}
    results["V5_Becker_top5_cap"] = run_version(
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
        extra_curated_seeds=baseline_seeds,
        extra_curated_audit=approved_audit,
        include_robustness=False,
        include_bootstrap=False,
        daily_events_transform=compose_transform(
            enable_becker=True,
            monetary_bucket_cap=0.30,
            geopolitical_bucket_cap=None,
        ),
    )
    results["V5_geo_only"] = run_version(
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
        extra_curated_seeds=approved_seeds + geopolitical_seeds,
        extra_curated_audit=approved_audit + geopolitical_audit,
        include_robustness=False,
        include_bootstrap=False,
    )
    results["V5_Becker_top5_cap_geo"] = run_version(
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
    results["V5_Becker_top5_cap_geo_calibrated"] = run_version(
        version="v3",
        base_config=geo_calibrated_config,
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
            geopolitical_bucket_cap=float(geopolitical_policy["bucket_cap"]),
        ),
    )

    baseline_row = summary_row("V5_Becker_top5_cap", results["V5_Becker_top5_cap"])
    summary_rows = [baseline_row]
    for version in ("V5_geo_only", "V5_Becker_top5_cap_geo", "V5_Becker_top5_cap_geo_calibrated"):
        summary_rows.append(summary_row(version, results[version], baseline=baseline_row))

    contribution_rows = []
    for version in ("V5_Becker_top5_cap_geo", "V5_Becker_top5_cap_geo_calibrated"):
        contribution_rows.extend(geopolitical_contribution_rows(results[version], geopolitical_ids, version))

    write_csv(output_dir / "geopolitical_expansion_summary.csv", summary_rows)
    write_csv(output_dir / "geopolitical_addon_contribution.csv", contribution_rows)
    render_report(output_dir / "geopolitical_expansion_report.md", summary_rows, contribution_rows)

    print("Completed geopolitical expansion backtests.")
    for row in summary_rows:
        print(
            f"{row['version']}: n_events={row['n_events']}, sortino={row['sortino']:.3f}, "
            f"cagr={row['cagr']:.4f}, mdd={row['mdd']:.4f}, avg_position={row['avg_position']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
