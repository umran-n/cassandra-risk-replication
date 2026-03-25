from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.events import load_curated_shortlist, load_polymarket_approved_universe  # noqa: E402
from cassandra_risk.expansion_figures import render_expansion_delta  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from run_backtest import compute_price_returns, fetch_fred_tb3ms, fetch_spy_prices, run_version  # noqa: E402


def expansion_summary_rows(
    *,
    baseline_result: dict,
    expansion_result: dict,
    baseline_event_count: int,
    approved_event_count: int,
) -> list[dict]:
    return [
        {
            "version": "V4",
            "n_events": baseline_event_count,
            "sortino": baseline_result["summaries"]["cassandra"]["sortino"],
            "cagr": baseline_result["summaries"]["cassandra"]["cagr"],
            "mdd": baseline_result["summaries"]["cassandra"]["max_drawdown_daily"],
            "avg_position": baseline_result["summaries"]["cassandra"]["avg_position"],
            "benchmark_sortino": baseline_result["summaries"]["vol_target"]["sortino"],
        },
        {
            "version": "V5",
            "n_events": approved_event_count,
            "sortino": expansion_result["summaries"]["cassandra"]["sortino"],
            "cagr": expansion_result["summaries"]["cassandra"]["cagr"],
            "mdd": expansion_result["summaries"]["cassandra"]["max_drawdown_daily"],
            "avg_position": expansion_result["summaries"]["cassandra"]["avg_position"],
            "benchmark_sortino": expansion_result["summaries"]["vol_target"]["sortino"],
        },
    ]


def render_expansion_report(
    path: Path,
    summary_rows: list[dict],
    approved_audit: list[dict],
) -> None:
    lookup = {row["version"]: row for row in summary_rows}
    v4 = lookup["V4"]
    v5 = lookup["V5"]
    status_counts = Counter(row["status"] for row in approved_audit)

    lines = [
        "# Expansion Backtest Report",
        "",
        "## Scope",
        "",
        "- `V4` baseline uses the original 9-event governed universe.",
        "- `V5` uses `data/curated/polymarket_approved.json` as the 38-event approved universe.",
        f"- Active historical loads from the approved universe: `{status_counts.get('loaded_polymarket_history', 0)}`",
        f"- Approved entries skipped for lack of history: `{status_counts.get('skipped_no_history', 0)}`",
        "",
        "## Summary Table",
        "",
        "| Version | n_events | Cassandra Sortino | Cassandra CAGR | Cassandra Daily MDD | Cassandra Avg Position | Vol Target Sortino |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| V4 | {v4['n_events']} | {v4['sortino']:.3f} | {v4['cagr'] * 100:.2f}% | {v4['mdd'] * 100:.2f}% | {v4['avg_position'] * 100:.2f}% | {v4['benchmark_sortino']:.3f} |",
        f"| V5 | {v5['n_events']} | {v5['sortino']:.3f} | {v5['cagr'] * 100:.2f}% | {v5['mdd'] * 100:.2f}% | {v5['avg_position'] * 100:.2f}% | {v5['benchmark_sortino']:.3f} |",
        "",
        "## Delta Versus V4",
        "",
        f"- Sortino delta: `{v5['sortino'] - v4['sortino']:+.3f}`",
        f"- CAGR delta: `{(v5['cagr'] - v4['cagr']) * 100:+.2f}%`",
        f"- Daily MDD delta: `{(v5['mdd'] - v4['mdd']) * 100:+.2f}%`",
        f"- Avg position delta: `{(v5['avg_position'] - v4['avg_position']) * 100:+.2f}%`",
        "",
        "## Interpretation",
        "",
        "- The approved 38-event universe de-risks more often, but the public Polymarket-only historical panel does not convert that extra caution into better downside-adjusted performance.",
        "- In this run, V5 underperforms both the V4 Cassandra baseline and the Vol Target benchmark on Sortino.",
        "- The most likely causes are event-density over-warning and the fact that 6 approved Metaculus entries remain placeholders with no usable historical path in the workspace.",
        "",
        "## Notes",
        "",
        "- `benchmark_sortino` is the Vol Target Sortino from the same run.",
        "- Manual Metaculus approvals remain governed-universe entries, but they do not contribute live history in this public replication because no Metaculus time series is available in the workspace yet.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    base_config = load_json(ROOT / "config" / "backtest_config.json")
    base_seeds = load_json(ROOT / "data" / "seeds" / "event_seeds.json")
    shortlist = load_curated_shortlist(ROOT / "data" / "curated" / "manifold_shortlist.json")
    approved_payload = load_json(ROOT / "data" / "curated" / "polymarket_approved.json")
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
        base_seeds=base_seeds,
        shortlist=shortlist,
        dates=dates,
        price_returns=price_returns,
        price_rows=price_rows,
        raw_dir=raw_dir,
        refresh=False,
        fred_rows=fred_rows,
        fallback_annual_rate=fallback_annual_rate,
        fred_fetch_succeeded=fred_fetch_succeeded,
    )
    expansion_result = run_version(
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
    )

    summary_rows = expansion_summary_rows(
        baseline_result=baseline_result,
        expansion_result=expansion_result,
        baseline_event_count=len(base_seeds),
        approved_event_count=len(approved_payload),
    )
    write_csv(output_dir / "expansion_summary.csv", summary_rows)
    render_expansion_delta(summary_rows, output_dir / "fig5_expansion_delta.png")
    render_expansion_report(output_dir / "expansion_report.md", summary_rows, approved_audit)
    write_csv(output_dir / "approved_universe_audit.csv", approved_audit)

    print("Completed expansion backtest comparison.")
    print(f"Outputs written to: {output_dir}")
    for row in summary_rows:
        print(
            f"{row['version']}: n_events={row['n_events']}, sortino={row['sortino']:.3f}, "
            f"cagr={row['cagr']:.4f}, mdd={row['mdd']:.4f}, avg_position={row['avg_position']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
