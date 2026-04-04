from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from .event_graph import build_event_graph, load_governed_event_families, serialize_families
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


def _latest_output_dir(root: Path) -> Path:
    return root / "outputs" / "latest"


def _load_csv_rows(root: Path, name: str) -> list[dict[str, str]]:
    path = _latest_output_dir(root) / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _safe_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _within_date_range(date_value: str, start: str = "", end: str = "") -> bool:
    if start and date_value < start:
        return False
    if end and date_value > end:
        return False
    return True


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
    write_json(output_dir / "canonical_event_families.json", serialize_families(families))
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
    contracts = []
    canonical_families = load_payload(root, "canonical_event_families.json") or []
    for family in canonical_families:
        if bool(family.get("discovered")):
            continue
        for contract in family.get("linked_markets", []):
            contracts.append(contract)
    return {
        "sources": sources,
        "contracts": contracts,
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


def list_rsi_history(
    root: Path,
    start: str = "",
    end: str = "",
    limit: int | None = None,
) -> list[dict]:
    rows = _load_csv_rows(root, "daily_rsi_decomposition.csv")
    payload: list[dict] = []
    for row in rows:
        date_value = str(row.get("date") or "")
        if not _within_date_range(date_value, start=start, end=end):
            continue
        payload.append(
            {
                "date": date_value,
                "total_hazard": _safe_float(row.get("total_hazard")),
                "rsi": _safe_float(row.get("rsi")),
                "rsi_drag": _safe_float(row.get("rsi_drag")),
                "active_event_count": _safe_int(row.get("active_event_count")),
                "dominant_event_id": row.get("dominant_event_id") or "",
                "dominant_category": row.get("dominant_category") or "",
                "dominant_theme": row.get("dominant_theme") or "",
                "component_hazard": {
                    "probability": _safe_float(row.get("probability_component_hazard")),
                    "severity": _safe_float(row.get("severity_component_hazard")),
                    "velocity": _safe_float(row.get("velocity_component_hazard")),
                    "persistence": _safe_float(row.get("persistence_component_hazard")),
                },
                "component_hazard_shares": {
                    "probability": _safe_float(row.get("probability_share_of_hazard")),
                    "severity": _safe_float(row.get("severity_share_of_hazard")),
                    "velocity": _safe_float(row.get("velocity_share_of_hazard")),
                    "persistence": _safe_float(row.get("persistence_share_of_hazard")),
                },
            }
        )
    if limit is not None:
        payload = payload[-max(limit, 0) :]
    return payload


def list_theme_decomposition_history(
    root: Path,
    start: str = "",
    end: str = "",
    theme: str = "",
    limit: int | None = None,
) -> list[dict]:
    rows = _load_csv_rows(root, "hazard_attribution.csv")
    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        date_value = str(row.get("date") or "")
        if not _within_date_range(date_value, start=start, end=end):
            continue
        theme_value = str(row.get("structural_theme") or "")
        if theme and theme_value != theme:
            continue
        key = (date_value, theme_value)
        item = grouped.setdefault(
            key,
            {
                "date": date_value,
                "theme": theme_value,
                "total_hazard": 0.0,
                "event_count": 0,
                "dominant_event_id": "",
                "dominant_event_question": "",
                "dominant_event_hazard": 0.0,
                "theme_hazard_share": 0.0,
                "categories": defaultdict(float),
            },
        )
        hazard = _safe_float(row.get("hazard_contribution")) or 0.0
        item["total_hazard"] += hazard
        item["event_count"] += 1
        item["theme_hazard_share"] = max(item["theme_hazard_share"], _safe_float(row.get("theme_hazard_share")) or 0.0)
        category_value = str(row.get("category") or "")
        if category_value:
            item["categories"][category_value] += hazard
        if hazard > item["dominant_event_hazard"]:
            item["dominant_event_hazard"] = hazard
            item["dominant_event_id"] = row.get("event_id") or ""
            item["dominant_event_question"] = row.get("question") or ""

    payload = []
    for (_date, _theme), item in sorted(grouped.items()):
        payload.append(
            {
                "date": item["date"],
                "theme": item["theme"],
                "total_hazard": item["total_hazard"],
                "event_count": item["event_count"],
                "theme_hazard_share": item["theme_hazard_share"],
                "dominant_event_id": item["dominant_event_id"],
                "dominant_event_question": item["dominant_event_question"],
                "dominant_event_hazard": item["dominant_event_hazard"],
                "category_hazard": dict(sorted(item["categories"].items())),
            }
        )
    if limit is not None:
        payload = payload[-max(limit, 0) :]
    return payload


def list_latest_theme_decomposition(root: Path) -> list[dict]:
    rsi_snapshot = load_payload(root, "rsi_snapshot.json") or {}
    snapshots = load_payload(root, "signal_snapshots.json") or []
    theme_groups: dict[str, dict] = {}
    current_events = rsi_snapshot.get("events") or []
    hazard_share_lookup = dict(rsi_snapshot.get("theme_hazard_shares") or {})
    for event in current_events:
        theme_value = str(event.get("structural_theme") or "")
        if not theme_value:
            continue
        item = theme_groups.setdefault(
            theme_value,
            {
                "theme": theme_value,
                "asof": rsi_snapshot.get("asof", ""),
                "event_count": 0,
                "total_hazard": 0.0,
                "theme_hazard_share": hazard_share_lookup.get(theme_value),
                "dominant_event_family_id": "",
                "dominant_title": "",
                "dominant_event_hazard": 0.0,
                "families": [],
            },
        )
        hazard = _safe_float(event.get("hazard_contribution")) or 0.0
        item["event_count"] += 1
        item["total_hazard"] += hazard
        if hazard > item["dominant_event_hazard"]:
            item["dominant_event_hazard"] = hazard
            item["dominant_event_family_id"] = event.get("event_family_id") or ""
            item["dominant_title"] = event.get("title") or ""
        item["families"].append(
            {
                "event_family_id": event.get("event_family_id") or "",
                "title": event.get("title") or "",
                "category": event.get("category") or "",
                "source": event.get("source") or "",
                "market_id": event.get("market_id") or "",
                "selected_probability_governed": _safe_float(event.get("selected_probability_governed")),
                "hazard_contribution": hazard,
                "calibration_applied": event.get("calibration_applied") or "",
                "theme_cap_applied": bool(event.get("theme_cap_applied")),
            }
        )

    snapshot_lookup = {row.get("event_family_id"): row for row in snapshots}
    for item in theme_groups.values():
        item["families"].sort(key=lambda row: row.get("hazard_contribution") or 0.0, reverse=True)
        for family in item["families"]:
            snapshot = snapshot_lookup.get(family["event_family_id"]) or {}
            family["quality_score"] = _safe_float(snapshot.get("quality_score"))
            family["candidate_count"] = _safe_int(snapshot.get("candidate_count"))
            family["source_options"] = snapshot.get("source_options") or []
    return sorted(theme_groups.values(), key=lambda row: row["total_hazard"], reverse=True)


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


def list_family_breakdown(
    root: Path,
    theme: str = "",
    selection_state: str = "",
    discovered: bool | None = None,
    limit: int | None = None,
) -> list[dict]:
    family_rows = load_payload(root, "family_signal_book.json") or []
    canonical_rows = load_payload(root, "canonical_event_families.json") or []
    snapshots = load_payload(root, "signal_snapshots.json") or []

    canonical_lookup = {row.get("event_family_id"): row for row in canonical_rows}
    snapshot_lookup = {row.get("event_family_id"): row for row in snapshots}

    rows = []
    for row in family_rows:
        event_family_id = row.get("event_family_id")
        canonical = canonical_lookup.get(event_family_id) or {}
        snapshot = snapshot_lookup.get(event_family_id) or {}
        merged = {
            "event_family_id": event_family_id,
            "title": row.get("title") or canonical.get("title") or snapshot.get("title") or "",
            "structural_theme": row.get("structural_theme") or canonical.get("structural_theme") or snapshot.get("structural_theme") or "",
            "category": row.get("category") or canonical.get("category") or snapshot.get("category") or "",
            "selection_state": row.get("selection_state") or "",
            "discovered": bool(row.get("discovered")),
            "governance_source": row.get("governance_source") or "",
            "proxy_family_id": row.get("proxy_family_id") or canonical.get("proxy_family_id") or "",
            "selected_source": snapshot.get("selected_source") or "",
            "selected_market_id": snapshot.get("selected_market_id") or "",
            "selected_probability_governed": _safe_float(snapshot.get("selected_probability_governed")),
            "selected_probability_raw": _safe_float(snapshot.get("selected_probability_raw")),
            "quality_score": _safe_float(snapshot.get("quality_score")),
            "candidate_count": _safe_int(snapshot.get("candidate_count")),
            "source_options": snapshot.get("source_options") or [],
            "calibration_applied": snapshot.get("calibration_applied") or "",
            "notes": snapshot.get("notes") or row.get("notes") or "",
            "linked_market_count": len(canonical.get("linked_markets") or []),
        }
        rows.append(merged)

    if theme:
        rows = [row for row in rows if row.get("structural_theme") == theme]
    if selection_state:
        rows = [row for row in rows if row.get("selection_state") == selection_state]
    if discovered is not None:
        rows = [row for row in rows if bool(row.get("discovered")) is discovered]

    rows.sort(
        key=lambda row: (
            0 if row.get("selection_state") == "selected" else 1,
            row.get("structural_theme") or "",
            -(row.get("selected_probability_governed") or 0.0),
            row.get("event_family_id") or "",
        )
    )
    if limit is not None:
        rows = rows[: max(limit, 0)]
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
