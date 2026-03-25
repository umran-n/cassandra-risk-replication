from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cassandra_risk.event_graph import build_event_graph, load_governed_event_families  # noqa: E402
from cassandra_risk.signal_engine import build_signal_book  # noqa: E402
from cassandra_risk.source_sync import collect_source_catalogs, write_source_outputs  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_json  # noqa: E402


def render_signal_summary(
    path: Path,
    source_status_rows: list[dict],
    family_rows: list[dict],
    snapshots: list[dict],
    rsi_snapshot: dict,
) -> None:
    active_count = sum(1 for row in family_rows if row.get("selection_state") == "selected")
    discovered_count = sum(1 for row in family_rows if row.get("discovered"))
    lines = [
        "# Unified Signal API Summary",
        "",
        f"- Governed families loaded: `{len([row for row in family_rows if not row.get('discovered')])}`",
        f"- Discovered candidate families: `{discovered_count}`",
        f"- Selected live signals: `{active_count}`",
        f"- Current governed RSI: `{rsi_snapshot['rsi']:.4f}`",
        f"- Current total hazard: `{rsi_snapshot['total_hazard']:.4f}`",
        f"- Dominant theme: `{rsi_snapshot['dominant_theme']}`",
        f"- Dominant event family: `{rsi_snapshot['dominant_event_family_id']}`",
        "",
        "## Source Status",
        "",
        "| Source | Reachable | Markets | Notes |",
        "| --- | --- | ---: | --- |",
    ]
    for row in source_status_rows:
        lines.append(f"| {row['source']} | {row['reachable']} | {row['market_count']} | {row['notes']} |")
    lines.extend(
        [
            "",
            "## Top Selected Signals",
            "",
            "| Event Family | Theme | Source | Probability | Calibration | Theme Cap |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in snapshots[:15]:
        family_row = next(item for item in family_rows if item["event_family_id"] == row["event_family_id"])
        lines.append(
            f"| {row['event_family_id']} | {row['structural_theme']} | {row['selected_source']} | "
            f"{row['selected_probability_governed']:.3f} | {row['calibration_applied']} | "
            f"{family_row.get('theme_cap_applied', False)} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    refresh = "--refresh" in argv

    registry, source_markets, source_status_rows = collect_source_catalogs(ROOT, refresh=refresh)
    write_source_outputs(ROOT, source_markets, source_status_rows)

    governed_families = load_governed_event_families(ROOT)
    families, link_audit = build_event_graph(governed_families, source_markets, registry)
    family_rows, snapshots, rsi_snapshot = build_signal_book(families, registry, ROOT)

    output_dir = ensure_dir(ROOT / "outputs" / "signals")
    write_json(output_dir / "canonical_event_families.json", families)
    write_json(output_dir / "link_audit.json", link_audit)
    write_json(output_dir / "family_signal_book.json", family_rows)
    write_json(output_dir / "signal_snapshots.json", snapshots)
    write_json(output_dir / "rsi_snapshot.json", rsi_snapshot)
    render_signal_summary(output_dir / "signal_summary.md", source_status_rows, family_rows, snapshots, rsi_snapshot)

    print("Unified signal book built.")
    print(f"Selected signals: {len(snapshots)}")
    print(f"Current RSI: {rsi_snapshot['rsi']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
