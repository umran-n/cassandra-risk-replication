from __future__ import annotations

import json
from pathlib import Path

from .event_graph import build_event_graph, load_governed_event_families
from .signal_engine import build_signal_book
from .source_registry import load_source_registry
from .source_sync import collect_source_catalogs, write_source_outputs
from .utils import ensure_dir, write_json


def signal_output_dir(root: Path) -> Path:
    return root / "outputs" / "signals"


def load_payload(root: Path, name: str):
    path = signal_output_dir(root) / name
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
    family_lookup = {row["event_family_id"]: row for row in family_rows}
    for row in snapshots[:15]:
        family_row = family_lookup[row["event_family_id"]]
        lines.append(
            f"| {row['event_family_id']} | {row['structural_theme']} | {row['selected_source']} | "
            f"{row['selected_probability_governed']:.3f} | {row['calibration_applied']} | "
            f"{family_row.get('theme_cap_applied', False)} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_live_signal_artifacts(root: Path, refresh: bool = False) -> dict:
    registry, source_markets, source_status_rows = collect_source_catalogs(root, refresh=refresh)
    write_source_outputs(root, source_markets, source_status_rows)

    governed_families = load_governed_event_families(root)
    families, link_audit = build_event_graph(governed_families, source_markets, registry)
    family_rows, snapshots, rsi_snapshot = build_signal_book(families, registry, root)

    output_dir = ensure_dir(signal_output_dir(root))
    write_json(output_dir / "canonical_event_families.json", families)
    write_json(output_dir / "link_audit.json", link_audit)
    write_json(output_dir / "family_signal_book.json", family_rows)
    write_json(output_dir / "signal_snapshots.json", snapshots)
    write_json(output_dir / "rsi_snapshot.json", rsi_snapshot)
    render_signal_summary(output_dir / "signal_summary.md", source_status_rows, family_rows, snapshots, rsi_snapshot)

    return {
        "registry": registry,
        "source_markets": source_markets,
        "source_status_rows": source_status_rows,
        "canonical_families": families,
        "family_rows": family_rows,
        "snapshots": snapshots,
        "rsi_snapshot": rsi_snapshot,
        "link_audit": link_audit,
    }


def registry_meta(root: Path) -> dict:
    registry = load_source_registry(root)
    sources = []
    for source_name, settings in sorted(registry.get("sources", {}).items()):
        sources.append(
            {
                "source": source_name,
                "display_name": settings.get("display_name", source_name.title()),
                "enabled": bool(settings.get("enabled", True)),
                "priority": int(settings.get("priority", 999)),
                "quality_tier": settings.get("quality_tier", ""),
                "role": settings.get("role", ""),
                "auth_mode": settings.get("auth_mode", ""),
                "token_env_var": settings.get("token_env_var", ""),
            }
        )
    return {
        "sources": sources,
        "theme_policies": registry.get("theme_policies", {}),
        "selection_policy": registry.get("selection_policy", {}),
    }


def list_source_markets(
    root: Path,
    source: str = "",
    theme: str = "",
    status: str = "",
    min_quality: float | None = None,
    limit: int | None = None,
) -> list[dict]:
    payload = load_payload(root, "source_markets.json") or []
    rows = list(payload)
    if source:
        rows = [row for row in rows if row.get("source") == source]
    if theme:
        rows = [row for row in rows if row.get("structural_theme") == theme]
    if status:
        rows = [row for row in rows if str(row.get("status") or "").lower() == status.lower()]
    if min_quality is not None:
        rows = [row for row in rows if float(row.get("quality_score") or 0.0) >= min_quality]
    rows.sort(key=lambda row: (row.get("source", ""), row.get("structural_theme", ""), -float(row.get("quality_score") or 0.0), row.get("market_id", "")))
    if limit is not None:
        rows = rows[: max(limit, 0)]
    return rows


def list_event_families(
    root: Path,
    theme: str = "",
    discovered: bool | None = None,
    selection_state: str = "",
) -> list[dict]:
    payload = load_payload(root, "family_signal_book.json") or []
    rows = list(payload)
    if theme:
        rows = [row for row in rows if row.get("structural_theme") == theme]
    if discovered is not None:
        rows = [row for row in rows if bool(row.get("discovered")) is discovered]
    if selection_state:
        rows = [row for row in rows if row.get("selection_state") == selection_state]
    return rows


def get_event_family_detail(root: Path, event_family_id: str) -> dict | None:
    canonical_families = load_payload(root, "canonical_event_families.json") or []
    family_rows = load_payload(root, "family_signal_book.json") or []
    snapshots = load_payload(root, "signal_snapshots.json") or []
    link_audit = load_payload(root, "link_audit.json") or []

    canonical = next((row for row in canonical_families if row.get("event_family_id") == event_family_id), None)
    summary = next((row for row in family_rows if row.get("event_family_id") == event_family_id), None)
    snapshot = next((row for row in snapshots if row.get("event_family_id") == event_family_id), None)
    family_links = [row for row in link_audit if row.get("event_family_id") == event_family_id]
    if canonical is None and summary is None and snapshot is None:
        return None
    return {
        "event_family_id": event_family_id,
        "summary": summary,
        "canonical": canonical,
        "snapshot": snapshot,
        "link_audit": family_links,
    }


def list_signal_snapshots(root: Path, theme: str = "", source: str = "") -> list[dict]:
    payload = load_payload(root, "signal_snapshots.json") or []
    rows = list(payload)
    if theme:
        rows = [row for row in rows if row.get("structural_theme") == theme]
    if source:
        rows = [row for row in rows if row.get("selected_source") == source]
    return rows


def get_signal_snapshot(root: Path, event_family_id: str) -> dict | None:
    payload = load_payload(root, "signal_snapshots.json") or []
    return next((row for row in payload if row.get("event_family_id") == event_family_id), None)


def list_link_audit(root: Path, source: str = "", status: str = "") -> list[dict]:
    payload = load_payload(root, "link_audit.json") or []
    rows = list(payload)
    if source:
        rows = [row for row in rows if row.get("source") == source]
    if status:
        rows = [row for row in rows if row.get("link_status") == status]
    return rows
