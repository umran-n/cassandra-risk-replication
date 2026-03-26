from __future__ import annotations

import copy
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .aggregation_policy import resolve_aggregation_policy
from .backtest import hazard_components_for_row
from .becker_calibration import calibrate_probability
from .config import load_json
from .rsi_engine import RSIEngine
from .signal_contract import SignalContract, ensure_signal_contract
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


def _is_open_candidate(candidate: SignalContract) -> bool:
    status = str(candidate.status or "").lower()
    return status in {"open", "active", ""}


def select_family_representative(
    contracts: list[SignalContract],
    aggregation_policy: str,
) -> SignalContract:
    if not contracts:
        raise ValueError("Cannot select from an empty family")

    policies = {str(contract.aggregation_policy or "").strip() for contract in contracts}
    if len(policies) != 1:
        raise ValueError(f"Family contains mixed aggregation policies: {sorted(policies)}")
    contract_policy = next(iter(policies))
    if contract_policy != aggregation_policy:
        raise ValueError(
            f"Family policy {aggregation_policy!r} does not match contract policy {contract_policy!r}"
        )

    if aggregation_policy == "max":
        return max(
            contracts,
            key=lambda contract: (
                float(contract.probability_calibrated if contract.probability_calibrated is not None else -1.0),
                float(contract.volume_usd or 0.0),
                contract.contract_id,
            ),
        )

    if aggregation_policy == "weighted_average":
        return max(
            contracts,
            key=lambda contract: (
                float(contract.volume_usd or 0.0),
                float(contract.probability_calibrated if contract.probability_calibrated is not None else -1.0),
                contract.contract_id,
            ),
        )

    raise ValueError(f"Unknown aggregation_policy: {aggregation_policy}")


def select_family_candidates(families: list[dict], registry: dict) -> tuple[list[dict], list[SignalContract]]:
    family_rows: list[dict] = []
    selected_rows: list[SignalContract] = []
    for family in families:
        candidates: list[SignalContract] = []
        for candidate in family.get("linked_markets", []):
            typed = ensure_signal_contract(candidate)
            if _is_open_candidate(typed) and typed.current_probability is not None:
                candidates.append(typed)
        aggregation_policy, _ = resolve_aggregation_policy(
            family.get("aggregation_policy"),
            structural_theme=str(family.get("structural_theme") or ""),
            candidates=candidates or family.get("source_candidates", []),
        )
        selected = select_family_representative(candidates, aggregation_policy) if candidates else None
        family_row = {
            "event_family_id": family["event_family_id"],
            "title": family["title"],
            "structural_theme": family["structural_theme"],
            "category": family["category"],
            "aggregation_policy": aggregation_policy,
            "governance_source": family["governance_source"],
            "discovered": bool(family.get("discovered", False)),
            "candidate_count": len(candidates),
            "source_options": sorted({candidate.source.value for candidate in candidates}),
            "selected_source": selected.source.value if selected else "",
            "selected_market_id": selected.native_id if selected else "",
            "selected_probability_raw": selected.current_probability if selected else "",
            "selected_quality_score": selected.quality_score if selected else "",
            "selection_state": "selected" if selected else "no_live_candidate",
            "notes": family.get("notes", ""),
        }
        family_rows.append(family_row)
        if selected is not None:
            selected_rows.append(
                selected.with_updates(
                    event_family_id=family["event_family_id"],
                    question_text=family["title"],
                    structural_theme=family["structural_theme"],
                    category=family["category"],
                    governance_source=family["governance_source"],
                    discovered=bool(family.get("discovered", False)),
                    notes=str(family.get("notes", "")),
                )
            )

    return family_rows, selected_rows


def apply_theme_bucket_limits(selected_rows: list[SignalContract], registry: dict) -> list[SignalContract]:
    by_theme: dict[str, list[SignalContract]] = defaultdict(list)
    for row in selected_rows:
        by_theme[row.structural_theme].append(row)

    limited_rows: list[SignalContract] = []
    for theme, rows in by_theme.items():
        policy = theme_policy(registry, theme)
        max_bucket_events = int(policy.get("max_bucket_events", len(rows)))
        rows.sort(key=lambda row: (-float(row.quality_score or 0.0), source_priority(registry, row.source.value), row.event_family_id))
        kept = rows[:max_bucket_events]
        dropped = rows[max_bucket_events:]
        for row in kept:
            limited_rows.append(row.with_updates(theme_bucket_selected=True, theme_bucket_drop_reason=""))
        for row in dropped:
            limited_rows.append(row.with_updates(theme_bucket_selected=False, theme_bucket_drop_reason="theme_max_bucket_events"))
    limited_rows.sort(key=lambda row: (not bool(row.theme_bucket_selected), row.structural_theme, row.event_family_id))
    return limited_rows


def apply_probability_governance(rows: list[SignalContract], registry: dict, root: Path) -> list[SignalContract]:
    config = _live_config(root, registry)
    governed_rows: list[SignalContract] = []
    for row in rows:
        raw_probability = clamp(float(row.current_probability or 0.0), 0.0, 1.0)
        theme = row.structural_theme
        policy = theme_policy(registry, theme)
        governed_probability = raw_probability
        calibration_applied = "none"
        efficiency_gap_applied = 0.0
        if bool(row.theme_bucket_selected) and bool(policy.get("becker_enabled", False)):
            governed_probability, metadata = calibrate_probability(raw_probability, theme, config)
            calibration_applied = "becker"
            efficiency_gap_applied = float(metadata.get("efficiency_gap_applied") or 0.0)
        governed_rows.append(
            row.with_updates(
                probability_raw=raw_probability,
                probability_calibrated=governed_probability,
                calibration_applied=calibration_applied,
                efficiency_gap_applied=efficiency_gap_applied,
            )
        )
    return governed_rows


def apply_theme_hazard_caps(rows: list[SignalContract], registry: dict, config: dict, asof_date: str) -> list[SignalContract]:
    active_rows = [row for row in rows if bool(row.theme_bucket_selected)]
    if not active_rows:
        return list(rows)

    total_hazard = 0.0
    theme_hazard: dict[str, float] = defaultdict(float)
    for row in active_rows:
        event_row = {
            "category": row.category,
            "probability": row.probability_calibrated,
            "resolution_date": row.resolution_time or row.close_time or asof_date,
            "structural_theme": row.structural_theme,
        }
        hazard = hazard_components_for_row(event_row, asof_date, config)["hazard_contribution"]
        total_hazard += hazard
        theme_hazard[row.structural_theme] += hazard

    active_index: dict[tuple[str, str], SignalContract] = {}
    for row in active_rows:
        theme = row.structural_theme
        policy = theme_policy(registry, theme)
        cap_share = policy.get("bucket_cap")
        if cap_share is None or total_hazard <= 0.0:
            active_index[(row.source.value, row.native_id)] = row.with_updates(theme_cap_scale=1.0, theme_cap_applied=False)
            continue
        cap_share = float(cap_share)
        allowed = cap_share * total_hazard
        current_theme_hazard = theme_hazard.get(theme, 0.0)
        if current_theme_hazard > allowed and current_theme_hazard > 0.0:
            scale = allowed / current_theme_hazard
            active_index[(row.source.value, row.native_id)] = row.with_updates(
                probability_calibrated=(row.probability_calibrated or 0.0) * scale,
                theme_cap_scale=scale,
                theme_cap_applied=True,
            )
        else:
            active_index[(row.source.value, row.native_id)] = row.with_updates(theme_cap_scale=1.0, theme_cap_applied=False)

    merged: list[SignalContract] = []
    for row in rows:
        key = (row.source.value, row.native_id)
        merged.append(active_index.get(key, row))
    return merged


def build_signal_book(families: list[dict], registry: dict, root: Path) -> tuple[list[dict], list[dict], dict]:
    family_rows, selected_rows = select_family_candidates(families, registry)
    bucket_limited = apply_theme_bucket_limits(selected_rows, registry)
    governed = apply_probability_governance(bucket_limited, registry, root)
    config = _live_config(root, registry)
    asof_date = _asof_date_string()
    governed = apply_theme_hazard_caps(governed, registry, config, asof_date)

    snapshots: list[dict] = []
    active_rows: list[SignalContract] = []
    for row in governed:
        family = next(item for item in family_rows if item["event_family_id"] == row.event_family_id)
        family["selected_probability_governed"] = row.probability_calibrated if row.probability_calibrated is not None else ""
        family["calibration_applied"] = row.calibration_applied
        family["theme_cap_applied"] = row.theme_cap_applied
        family["theme_cap_scale"] = row.theme_cap_scale
        if bool(family.get("discovered", False)):
            family["selection_state"] = "candidate_only"
            continue
        if not bool(row.theme_bucket_selected):
            family["selection_state"] = "suppressed_by_theme_limit"
            continue

        snapshot = SignalSnapshot(
            asof=asof_date,
            event_family_id=row.event_family_id,
            title=row.question_text,
            structural_theme=row.structural_theme,
            category=row.category,
            selected_source=row.source.value,
            selected_market_id=row.native_id,
            selected_probability_raw=float(row.probability_raw or 0.0),
            selected_probability_governed=float(row.probability_calibrated or 0.0),
            quality_score=float(row.quality_score or 0.0),
            source_priority=source_priority(registry, row.source.value),
            candidate_count=int(family.get("candidate_count", 0)),
            source_options=list(family.get("source_options", [])),
            calibration_applied=str(row.calibration_applied or "none"),
            notes=str(family.get("notes", "")),
        )
        snapshots.append(snapshot.to_dict())
        active_rows.append(row)

    rsi_snapshot = RSIEngine().compute(active_rows, registry, root, asof_date)
    family_rows.sort(key=lambda row: (row["structural_theme"], row["event_family_id"]))
    snapshots.sort(key=lambda row: (row["structural_theme"], row["event_family_id"]))
    return family_rows, snapshots, rsi_snapshot


def build_rsi_snapshot(active_rows: list[SignalContract], registry: dict, root: Path, asof_date: str | None = None) -> dict:
    asof = asof_date or _asof_date_string()
    config = _live_config(root, registry)
    total_hazard = 0.0
    theme_hazard: dict[str, float] = defaultdict(float)
    source_count: dict[str, int] = defaultdict(int)
    payload_rows: list[dict] = []

    for row in active_rows:
        event_row = {
            "category": row.category,
            "probability": row.probability_calibrated,
            "resolution_date": row.resolution_time or row.close_time or asof,
            "structural_theme": row.structural_theme,
        }
        components = hazard_components_for_row(event_row, asof, config)
        hazard = components["hazard_contribution"]
        total_hazard += hazard
        theme_hazard[row.structural_theme] += hazard
        source_count[row.source.value] += 1
        payload_rows.append(
            {
                "event_family_id": row.event_family_id,
                "title": row.question_text,
                "source": row.source.value,
                "market_id": row.native_id,
                "structural_theme": row.structural_theme,
                "category": row.category,
                "selected_probability_governed": row.probability_calibrated,
                "hazard_contribution": hazard,
                "theme_cap_applied": bool(row.theme_cap_applied),
                "calibration_applied": row.calibration_applied or "none",
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
