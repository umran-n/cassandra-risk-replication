from __future__ import annotations

import copy
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .backtest import hazard_components_for_row
from .becker_calibration import calibrate_probability
from .config import load_json
from .signal_types import RSISnapshot, SignalSnapshot
from .source_registry import source_priority, theme_policy
from .utils import clamp


def _asof_date_string() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _live_config(root: Path, registry: dict) -> dict:
    config = copy.deepcopy(load_json(root / "config" / "backtest_config.json"))
    config.setdefault("becker_calibration", {})["enabled"] = True
    config["becker_calibration"]["theme_longshot_thresholds"] = {}
    for theme, policy in registry.get("theme_policies", {}).items():
        if "longshot_threshold" in policy:
            config["becker_calibration"]["theme_longshot_thresholds"][theme] = list(policy["longshot_threshold"])
        if "becker_gap" in policy:
            config["becker_calibration"].setdefault("efficiency_gaps", {})[theme] = float(policy["becker_gap"])
    return config


def _candidate_sort_key(candidate: dict, registry: dict) -> tuple:
    return (
        source_priority(registry, candidate.get("source", "")),
        -float(candidate.get("quality_score") or 0.0),
        candidate.get("title") or "",
    )


def _is_open_candidate(candidate: dict) -> bool:
    status = str(candidate.get("status") or "").lower()
    return status in {"open", "active", ""}


def select_family_candidates(families: list[dict], registry: dict) -> tuple[list[dict], list[dict]]:
    family_rows: list[dict] = []
    selected_rows: list[dict] = []
    for family in families:
        candidates = [
            candidate
            for candidate in family.get("linked_markets", [])
            if _is_open_candidate(candidate) and candidate.get("current_probability") is not None
        ]
        candidates.sort(key=lambda item: _candidate_sort_key(item, registry))
        selected = candidates[0] if candidates else None
        family_row = {
            "event_family_id": family["event_family_id"],
            "title": family["title"],
            "structural_theme": family["structural_theme"],
            "category": family["category"],
            "governance_source": family["governance_source"],
            "discovered": bool(family.get("discovered", False)),
            "candidate_count": len(candidates),
            "source_options": sorted({candidate["source"] for candidate in candidates}),
            "selected_source": selected.get("source") if selected else "",
            "selected_market_id": selected.get("market_id") if selected else "",
            "selected_probability_raw": selected.get("current_probability") if selected else "",
            "selected_quality_score": selected.get("quality_score") if selected else "",
            "selection_state": "selected" if selected else "no_live_candidate",
            "notes": family.get("notes", ""),
        }
        family_rows.append(family_row)
        if selected is not None:
            selected_rows.append(
                {
                    "event_family_id": family["event_family_id"],
                    "title": family["title"],
                    "structural_theme": family["structural_theme"],
                    "category": family["category"],
                    "governance_source": family["governance_source"],
                    "discovered": bool(family.get("discovered", False)),
                    **selected,
                }
            )

    return family_rows, selected_rows


def apply_theme_bucket_limits(selected_rows: list[dict], registry: dict) -> list[dict]:
    by_theme: dict[str, list[dict]] = defaultdict(list)
    for row in selected_rows:
        by_theme[row["structural_theme"]].append(dict(row))

    limited_rows: list[dict] = []
    for theme, rows in by_theme.items():
        policy = theme_policy(registry, theme)
        max_bucket_events = int(policy.get("max_bucket_events", len(rows)))
        rows.sort(key=lambda row: (-float(row.get("quality_score") or 0.0), source_priority(registry, row.get("source", "")), row["event_family_id"]))
        kept = rows[:max_bucket_events]
        dropped = rows[max_bucket_events:]
        for row in kept:
            row["theme_bucket_selected"] = True
            row["theme_bucket_drop_reason"] = ""
            limited_rows.append(row)
        for row in dropped:
            row["theme_bucket_selected"] = False
            row["theme_bucket_drop_reason"] = "theme_max_bucket_events"
            limited_rows.append(row)
    limited_rows.sort(key=lambda row: (not bool(row["theme_bucket_selected"]), row["structural_theme"], row["event_family_id"]))
    return limited_rows


def apply_probability_governance(rows: list[dict], registry: dict, root: Path) -> list[dict]:
    config = _live_config(root, registry)
    governed_rows: list[dict] = []
    for row in rows:
        updated = dict(row)
        raw_probability = clamp(float(updated.get("current_probability") or 0.0), 0.0, 1.0)
        theme = updated.get("structural_theme")
        policy = theme_policy(registry, theme)
        governed_probability = raw_probability
        calibration_applied = "none"
        if bool(updated.get("theme_bucket_selected", True)) and bool(policy.get("becker_enabled", False)):
            governed_probability, metadata = calibrate_probability(raw_probability, theme, config)
            calibration_applied = "becker"
            updated.update(metadata)
        updated["selected_probability_raw"] = raw_probability
        updated["selected_probability_governed"] = governed_probability
        updated["calibration_applied"] = calibration_applied
        governed_rows.append(updated)
    return governed_rows


def apply_theme_hazard_caps(rows: list[dict], registry: dict, config: dict, asof_date: str) -> list[dict]:
    active_rows = [dict(row) for row in rows if bool(row.get("theme_bucket_selected", True))]
    if not active_rows:
        return [dict(row) for row in rows]

    total_hazard = 0.0
    theme_hazard: dict[str, float] = defaultdict(float)
    for row in active_rows:
        event_row = {
            "category": row["category"],
            "probability": row["selected_probability_governed"],
            "resolution_date": row.get("resolution_time") or row.get("close_time") or asof_date,
            "structural_theme": row["structural_theme"],
        }
        hazard = hazard_components_for_row(event_row, asof_date, config)["hazard_contribution"]
        row["_hazard_pre_cap"] = hazard
        total_hazard += hazard
        theme_hazard[row["structural_theme"]] += hazard

    for row in active_rows:
        theme = row["structural_theme"]
        policy = theme_policy(registry, theme)
        cap_share = policy.get("bucket_cap")
        row["theme_cap_scale"] = 1.0
        row["theme_cap_applied"] = False
        if cap_share is None or total_hazard <= 0.0:
            continue
        cap_share = float(cap_share)
        allowed = cap_share * total_hazard
        current_theme_hazard = theme_hazard.get(theme, 0.0)
        if current_theme_hazard > allowed and current_theme_hazard > 0.0:
            scale = allowed / current_theme_hazard
            row["selected_probability_governed"] *= scale
            row["theme_cap_scale"] = scale
            row["theme_cap_applied"] = True

    merged: list[dict] = []
    active_index = {(row["source"], row["market_id"]): row for row in active_rows}
    for row in rows:
        key = (row["source"], row["market_id"])
        merged.append(active_index.get(key, dict(row)))
    return merged


def build_signal_book(families: list[dict], registry: dict, root: Path) -> tuple[list[dict], list[dict], dict]:
    family_rows, selected_rows = select_family_candidates(families, registry)
    bucket_limited = apply_theme_bucket_limits(selected_rows, registry)
    governed = apply_probability_governance(bucket_limited, registry, root)
    config = _live_config(root, registry)
    asof_date = _asof_date_string()
    governed = apply_theme_hazard_caps(governed, registry, config, asof_date)

    snapshots: list[dict] = []
    active_rows: list[dict] = []
    for row in governed:
        family = next(item for item in family_rows if item["event_family_id"] == row["event_family_id"])
        family["selected_probability_governed"] = row.get("selected_probability_governed", "")
        family["calibration_applied"] = row.get("calibration_applied", "")
        family["theme_cap_applied"] = row.get("theme_cap_applied", False)
        family["theme_cap_scale"] = row.get("theme_cap_scale", 1.0)
        if bool(family.get("discovered", False)):
            family["selection_state"] = "candidate_only"
            continue
        if not bool(row.get("theme_bucket_selected", True)):
            family["selection_state"] = "suppressed_by_theme_limit"
            continue

        snapshot = SignalSnapshot(
            asof=asof_date,
            event_family_id=row["event_family_id"],
            title=row["title"],
            structural_theme=row["structural_theme"],
            category=row["category"],
            selected_source=row["source"],
            selected_market_id=row["market_id"],
            selected_probability_raw=float(row["selected_probability_raw"]),
            selected_probability_governed=float(row["selected_probability_governed"]),
            quality_score=float(row.get("quality_score") or 0.0),
            source_priority=source_priority(registry, row.get("source", "")),
            candidate_count=int(family.get("candidate_count", 0)),
            source_options=list(family.get("source_options", [])),
            calibration_applied=str(row.get("calibration_applied", "none")),
            notes=str(family.get("notes", "")),
        )
        snapshots.append(snapshot.to_dict())
        active_rows.append(dict(row))

    rsi_snapshot = build_rsi_snapshot(active_rows, registry, root, asof_date)
    family_rows.sort(key=lambda row: (row["structural_theme"], row["event_family_id"]))
    snapshots.sort(key=lambda row: (row["structural_theme"], row["event_family_id"]))
    return family_rows, snapshots, rsi_snapshot


def build_rsi_snapshot(active_rows: list[dict], registry: dict, root: Path, asof_date: str | None = None) -> dict:
    asof = asof_date or _asof_date_string()
    config = _live_config(root, registry)
    total_hazard = 0.0
    theme_hazard: dict[str, float] = defaultdict(float)
    source_count: dict[str, int] = defaultdict(int)
    payload_rows: list[dict] = []

    for row in active_rows:
        event_row = {
            "category": row["category"],
            "probability": row["selected_probability_governed"],
            "resolution_date": row.get("resolution_time") or row.get("close_time") or asof,
            "structural_theme": row["structural_theme"],
        }
        components = hazard_components_for_row(event_row, asof, config)
        hazard = components["hazard_contribution"]
        total_hazard += hazard
        theme_hazard[row["structural_theme"]] += hazard
        source_count[row["source"]] += 1
        payload_rows.append(
            {
                "event_family_id": row["event_family_id"],
                "title": row["title"],
                "source": row["source"],
                "market_id": row["market_id"],
                "structural_theme": row["structural_theme"],
                "category": row["category"],
                "selected_probability_governed": row["selected_probability_governed"],
                "hazard_contribution": hazard,
                "theme_cap_applied": bool(row.get("theme_cap_applied", False)),
                "calibration_applied": row.get("calibration_applied", "none"),
            }
        )

    dominant_theme = ""
    dominant_event = ""
    if theme_hazard:
        dominant_theme = max(theme_hazard, key=theme_hazard.get)
    if payload_rows:
        dominant_event = max(payload_rows, key=lambda row: row["hazard_contribution"])["event_family_id"]

    rsi = 1.0 / (1.0 + total_hazard)
    theme_hazard_shares = {
        theme: 0.0 if total_hazard == 0 else value / total_hazard
        for theme, value in sorted(theme_hazard.items())
    }

    snapshot = RSISnapshot(
        asof=asof,
        rsi=rsi,
        total_hazard=total_hazard,
        event_count=len(payload_rows),
        dominant_theme=dominant_theme,
        dominant_event_family_id=dominant_event,
        theme_hazard_shares=theme_hazard_shares,
        signal_count_by_source=dict(sorted(source_count.items())),
        events=sorted(payload_rows, key=lambda row: (-row["hazard_contribution"], row["event_family_id"])),
    )
    return snapshot.to_dict()
