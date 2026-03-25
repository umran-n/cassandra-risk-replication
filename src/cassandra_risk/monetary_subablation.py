from __future__ import annotations

import copy
from collections import defaultdict

from .backtest import hazard_components_for_row
from .utils import parse_date


def monetary_phase_for_resolution_date(resolution_date: str) -> str | None:
    day = parse_date(resolution_date)
    quarter = ((day.month - 1) // 3) + 1
    if (day.year == 2022 and quarter >= 1) or (day.year == 2023 and quarter <= 3):
        return "hiking"
    if day.year == 2023 and quarter == 4:
        return "pivot"
    if day.year == 2024 and 1 <= quarter <= 4:
        return "cutting"
    return None


def compress_monetary_by_phase(
    approved_entries: list[dict],
    approved_seeds: list[dict],
) -> tuple[list[dict], list[dict]]:
    volume_by_event = {
        entry["event_id"]: float(entry.get("total_volume_usd") or 0.0)
        for entry in approved_entries
        if entry.get("theme") == "monetary_policy"
    }
    phase_rows: dict[str, list[dict]] = defaultdict(list)
    for entry in approved_entries:
        if entry.get("theme") != "monetary_policy" or entry.get("source") != "polymarket":
            continue
        phase = monetary_phase_for_resolution_date(entry["resolution_date"])
        if phase:
            phase_rows[phase].append(entry)

    kept_event_ids: set[str] = set()
    selection_rows: list[dict] = []
    for phase in ("hiking", "pivot", "cutting"):
        candidates = phase_rows.get(phase, [])
        if not candidates:
            continue
        selected = max(
            candidates,
            key=lambda row: (float(row.get("total_volume_usd") or 0.0), row["event_id"]),
        )
        kept_event_ids.add(selected["event_id"])
        selection_rows.append(
            {
                "phase": phase,
                "event_id": selected["event_id"],
                "title": selected["title"],
                "resolution_date": selected["resolution_date"],
                "total_volume_usd": float(selected.get("total_volume_usd") or 0.0),
            }
        )

    filtered = []
    for seed in approved_seeds:
        if seed.get("structural_theme") != "monetary_policy":
            filtered.append(copy.deepcopy(seed))
            continue
        if seed["event_id"] in kept_event_ids:
            filtered.append(copy.deepcopy(seed))
    return filtered, selection_rows


def remove_event_ids(entries: list[dict], removed_event_ids: set[str]) -> list[dict]:
    return [copy.deepcopy(entry) for entry in entries if entry.get("event_id") not in removed_event_ids]


def apply_theme_hazard_cap(
    daily_events: dict[str, dict[str, dict]],
    config: dict,
    *,
    structural_theme: str,
    cap_share: float,
) -> dict[str, dict[str, dict]]:
    updated: dict[str, dict[str, dict]] = {}
    for day_string, events in daily_events.items():
        day_events = {event_id: copy.deepcopy(row) for event_id, row in events.items()}
        theme_event_ids = [
            event_id for event_id, row in day_events.items()
            if row.get("structural_theme") == structural_theme
        ]
        if not theme_event_ids:
            updated[day_string] = day_events
            continue

        total_hazard = 0.0
        theme_hazard = 0.0
        for event_id, row in day_events.items():
            hazard = hazard_components_for_row(row, day_string, config)["hazard_contribution"]
            total_hazard += hazard
            if event_id in theme_event_ids:
                theme_hazard += hazard

        if theme_hazard <= 0.0 or total_hazard <= 0.0:
            updated[day_string] = day_events
            continue

        allowed_theme_hazard = cap_share * total_hazard
        scale = min(1.0, allowed_theme_hazard / theme_hazard)
        if scale < 1.0:
            for event_id in theme_event_ids:
                row = day_events[event_id]
                row["probability"] = float(row["probability"]) * scale
                row["theme_cap_scale"] = scale
                row["theme_cap_applied"] = True
        updated[day_string] = day_events
    return updated


def count_monetary_events(entries: list[dict]) -> int:
    return sum(1 for entry in entries if entry.get("structural_theme") == "monetary_policy")

