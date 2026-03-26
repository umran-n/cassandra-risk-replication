from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .signal_contract import SignalContract, ensure_signal_contract


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return list(json.load(handle))


def _load_signal_artifact(root: Path, name: str) -> list[dict]:
    path = root / "outputs" / "signals" / name
    return _load_json(path)


def _parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _days_to_resolution(value: object, asof: datetime | None = None) -> int | None:
    resolution = _parse_datetime(value)
    if resolution is None:
        return None
    anchor = asof or datetime.now(timezone.utc)
    return max((resolution.date() - anchor.date()).days, 0)


def volume_floor_for_theme(theme: str) -> float:
    return 500_000.0 if theme == "geopolitical" else 100_000.0


def contract_id_for_market(source: str, market_id: str) -> str:
    return f"{source}::{market_id}"


def slugify(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", "_", lowered)
    return lowered.strip("_") or "candidate"


def derive_proxy_family_id(title: str, theme: str, resolution_time: object) -> str:
    year = ""
    parsed = _parse_datetime(resolution_time)
    if parsed is not None:
        year = f"_{parsed.year}"
    return f"{theme}_{slugify(title)}{year}"


@dataclass
class PromotionCandidate:
    contract: SignalContract
    gate1_probability_history: bool
    gate2_resolution_horizon: bool
    gate3_category_assigned: bool
    gate4_volume_floor: bool
    gate5_binary: bool
    gate6_macro_relevant: bool
    gate7_no_lookahead: bool
    quality_score: float
    gates_passed: int
    auto_recommendation: str
    decision: str | None
    decision_reason: str | None
    decided_by: str | None
    decided_at: datetime | None
    family_event_id: str = ""

    @property
    def contract_id(self) -> str:
        return self.contract.contract_id

    @property
    def proxy_family_id(self) -> str:
        return self.contract.proxy_family_id or derive_proxy_family_id(
            self.contract.question_text,
            self.contract.structural_theme,
            self.contract.resolution_time,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "contract": self.contract.to_dict(include_aliases=True),
            "contract_id": self.contract.contract_id,
            "source": self.contract.source.value,
            "market_id": self.contract.native_id,
            "question_text": self.contract.question_text,
            "structural_theme": self.contract.structural_theme,
            "category": self.contract.category,
            "proxy_family_id": self.proxy_family_id,
            "current_probability": self.contract.probability_raw,
            "resolution_date": self.contract.resolution_time,
            "open_time": self.contract.open_time,
            "total_volume_usd": self.contract.volume_usd,
            "num_traders": self.contract.num_traders,
            "num_history_points": int(self.contract.metadata.get("history_points") or 1),
            "source_url": self.contract.url,
            "liquidity_usd": self.contract.liquidity_usd,
            "days_to_resolution": _days_to_resolution(self.contract.resolution_time),
            "family_event_id": self.family_event_id,
        }
        payload.update(
            {
                "gate1_probability_history": self.gate1_probability_history,
                "gate2_resolution_horizon": self.gate2_resolution_horizon,
                "gate3_category_assigned": self.gate3_category_assigned,
                "gate4_volume_floor": self.gate4_volume_floor,
                "gate5_binary": self.gate5_binary,
                "gate6_macro_relevant": self.gate6_macro_relevant,
                "gate7_no_lookahead": self.gate7_no_lookahead,
                "quality_score": self.quality_score,
                "gates_passed": self.gates_passed,
                "auto_recommendation": self.auto_recommendation,
                "decision": self.decision,
                "decision_reason": self.decision_reason,
                "decided_by": self.decided_by,
                "decided_at": self.decided_at.astimezone(timezone.utc).isoformat() if self.decided_at else None,
            }
        )
        return payload


def _source_contract_lookup(root: Path) -> dict[tuple[str, str], SignalContract]:
    source_markets = _load_signal_artifact(root, "source_markets.json")
    lookup: dict[tuple[str, str], SignalContract] = {}
    for row in source_markets:
        contract = ensure_signal_contract(row)
        lookup[(contract.source.value, contract.native_id)] = contract
    return lookup


def build_promotion_queue(
    root: Path,
    theme: str = "",
    min_gates: int = 0,
    include_rejected: bool = False,
    decision_state: str = "pending",
    decisions_map: dict[str, dict] | None = None,
) -> list[PromotionCandidate]:
    family_rows = _load_signal_artifact(root, "family_signal_book.json")
    source_lookup = _source_contract_lookup(root)
    decisions_map = decisions_map or {}

    candidates: list[PromotionCandidate] = []
    for family in family_rows:
        if not bool(family.get("discovered")):
            continue
        if theme and family.get("structural_theme") != theme:
            continue

        source = str(family.get("selected_source") or "")
        market_id = str(family.get("selected_market_id") or "")
        if not source or not market_id:
            continue
        contract = source_lookup.get((source, market_id))
        if contract is None:
            continue

        decision_record = decisions_map.get(contract.contract_id, {})
        decision = decision_record.get("decision")
        if decision_state == "pending" and decision in {"APPROVED", "REJECTED"}:
            if decision == "REJECTED" and include_rejected:
                pass
            else:
                continue
        if decision_state == "approved" and decision != "APPROVED":
            continue
        if decision_state == "rejected" and decision != "REJECTED":
            continue
        if decision == "REJECTED" and not include_rejected and decision_state == "pending":
            continue

        gate1_probability_history = contract.probability_raw is not None
        gate2_resolution_horizon = ((_days_to_resolution(contract.resolution_time) or 10**9) <= 180)
        gate3_category_assigned = bool(contract.structural_theme) and contract.structural_theme != "noise"
        gate4_volume_floor = float(contract.volume_usd or 0.0) >= volume_floor_for_theme(contract.structural_theme)
        gate5_binary = bool(contract.is_binary)
        gate6_macro_relevant = bool(contract.is_macro_relevant)
        open_time = _parse_datetime(contract.open_time)
        resolution_time = _parse_datetime(contract.resolution_time)
        gate7_no_lookahead = bool(open_time and resolution_time and open_time <= resolution_time)

        gates_passed = sum(
            1
            for value in (
                gate1_probability_history,
                gate2_resolution_horizon,
                gate3_category_assigned,
                gate4_volume_floor,
                gate5_binary,
                gate6_macro_relevant,
                gate7_no_lookahead,
            )
            if value
        )
        quality_score = min(1.0, 0.6 * float(contract.quality_score or 0.0) + 0.4 * (gates_passed / 7.0))
        if gates_passed == 7 and quality_score >= 0.80:
            recommendation = "APPROVE"
        elif gates_passed >= 5 and quality_score >= 0.50:
            recommendation = "REVIEW"
        else:
            recommendation = "REJECT"

        if gates_passed < min_gates:
            continue

        candidates.append(
            PromotionCandidate(
                contract=contract,
                gate1_probability_history=gate1_probability_history,
                gate2_resolution_horizon=gate2_resolution_horizon,
                gate3_category_assigned=gate3_category_assigned,
                gate4_volume_floor=gate4_volume_floor,
                gate5_binary=gate5_binary,
                gate6_macro_relevant=gate6_macro_relevant,
                gate7_no_lookahead=gate7_no_lookahead,
                quality_score=quality_score,
                gates_passed=gates_passed,
                auto_recommendation=recommendation,
                decision=decision_record.get("decision"),
                decision_reason=decision_record.get("decision_reason"),
                decided_by=decision_record.get("decided_by"),
                decided_at=_parse_datetime(decision_record.get("decided_at")),
                family_event_id=str(family.get("event_family_id") or ""),
            )
        )

    priority = {"APPROVE": 0, "REVIEW": 1, "REJECT": 2}
    candidates.sort(
        key=lambda candidate: (
            priority.get(candidate.auto_recommendation, 9),
            -int(candidate.gates_passed),
            -float(candidate.quality_score),
            -(float(candidate.contract.volume_usd or 0.0)),
            candidate.contract.contract_id,
        )
    )
    return candidates


def find_promotion_candidate(
    root: Path,
    contract_id: str,
    decisions_map: dict[str, dict] | None = None,
) -> PromotionCandidate | None:
    queue = build_promotion_queue(
        root,
        include_rejected=True,
        decision_state="all",
        decisions_map=decisions_map or {},
    )
    return next((row for row in queue if row.contract_id == contract_id), None)
