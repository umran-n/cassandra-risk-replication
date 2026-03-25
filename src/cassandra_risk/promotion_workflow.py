from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return list(json.load(handle))


def _load_signal_artifact(root: Path, name: str) -> list[dict]:
    path = root / "outputs" / "signals" / name
    return _load_json(path)


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


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


def macro_relevance_score(title: str, theme: str) -> float:
    title_lower = title.lower()
    theme_bonus = {
        "monetary_policy": 0.55,
        "geopolitical": 0.55,
        "fiscal_debt": 0.5,
        "systemic_credit": 0.5,
        "trade_technology": 0.45,
        "electoral": 0.35,
    }.get(theme, 0.25)
    keywords = {
        "monetary_policy": ["fed", "rate", "fomc", "ecb", "cpi", "inflation", "cut", "hike"],
        "geopolitical": ["war", "strike", "ceasefire", "iran", "israel", "ukraine", "taiwan", "nato", "military"],
        "fiscal_debt": ["debt", "default", "shutdown", "treasury", "ceiling", "bond"],
        "systemic_credit": ["bank", "credit", "svb", "contagion", "liquidity"],
        "trade_technology": ["tariff", "sanction", "chips", "crypto", "sec", "ai"],
        "electoral": ["election", "president", "senate", "house", "prime minister", "ballot"],
    }
    hits = sum(1 for keyword in keywords.get(theme, []) if keyword in title_lower)
    return min(theme_bonus + 0.1 * hits, 1.0)


def derive_proxy_family_id(title: str, theme: str, resolution_time: object) -> str:
    year = ""
    parsed = _parse_datetime(resolution_time)
    if parsed is not None:
        year = f"_{parsed.year}"
    return f"{theme}_{slugify(title)}{year}"


@dataclass
class PromotionCandidate:
    contract_id: str
    source: str
    market_id: str
    question_text: str
    structural_theme: str
    category: str
    proxy_family_id: str | None
    current_probability: float | None
    resolution_date: str | None
    open_time: str | None
    total_volume_usd: float | None
    num_traders: int | None
    num_history_points: int
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
    decided_at: str | None
    source_url: str = ""
    liquidity_usd: float | None = None
    macro_relevance_score: float = 0.0
    days_to_resolution: int | None = None
    family_event_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_promotion_queue(
    root: Path,
    theme: str = "",
    min_gates: int = 0,
    include_rejected: bool = False,
    decision_state: str = "pending",
    decisions_map: dict[str, dict] | None = None,
) -> list[dict]:
    family_rows = _load_signal_artifact(root, "family_signal_book.json")
    source_markets = _load_signal_artifact(root, "source_markets.json")
    source_lookup = {(row.get("source"), row.get("market_id")): row for row in source_markets}
    decisions_map = decisions_map or {}

    candidates: list[dict] = []
    for family in family_rows:
        if not bool(family.get("discovered")):
            continue
        if theme and family.get("structural_theme") != theme:
            continue
        source = str(family.get("selected_source") or "")
        market_id = str(family.get("selected_market_id") or "")
        if not source or not market_id:
            continue
        source_market = dict(source_lookup.get((source, market_id), {}))
        if not source_market:
            continue

        contract_id = contract_id_for_market(source, market_id)
        decision_record = decisions_map.get(contract_id, {})
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

        gates = {
            "gate1_probability_history": source_market.get("current_probability") is not None,
            "gate2_resolution_horizon": ((_days_to_resolution(source_market.get("resolution_time") or source_market.get("close_time")) or 10**9) <= 180),
            "gate3_category_assigned": bool(source_market.get("structural_theme")) and str(source_market.get("structural_theme")) != "noise",
            "gate4_volume_floor": float(source_market.get("volume_usd") or 0.0) >= volume_floor_for_theme(str(source_market.get("structural_theme") or "")),
            "gate5_binary": str(source_market.get("outcome_type") or "").upper() == "BINARY",
            "gate6_macro_relevant": False,
            "gate7_no_lookahead": False,
        }
        macro_score = macro_relevance_score(str(source_market.get("title") or ""), str(source_market.get("structural_theme") or ""))
        gates["gate6_macro_relevant"] = macro_score >= 0.55
        open_time = _parse_datetime(source_market.get("open_time"))
        resolution_time = _parse_datetime(source_market.get("resolution_time") or source_market.get("close_time"))
        gates["gate7_no_lookahead"] = bool(open_time and resolution_time and open_time <= resolution_time)

        gates_passed = sum(1 for value in gates.values() if value)
        quality_score = min(1.0, 0.6 * float(source_market.get("quality_score") or 0.0) + 0.4 * (gates_passed / 7.0))
        if gates_passed == 7 and quality_score >= 0.80:
            recommendation = "APPROVE"
        elif gates_passed >= 5 and quality_score >= 0.50:
            recommendation = "REVIEW"
        else:
            recommendation = "REJECT"

        if gates_passed < min_gates:
            continue

        candidate = PromotionCandidate(
            contract_id=contract_id,
            source=source,
            market_id=market_id,
            question_text=str(source_market.get("title") or family.get("title") or ""),
            structural_theme=str(source_market.get("structural_theme") or family.get("structural_theme") or ""),
            category=str(source_market.get("category") or family.get("category") or ""),
            proxy_family_id=derive_proxy_family_id(
                str(source_market.get("title") or family.get("title") or ""),
                str(source_market.get("structural_theme") or family.get("structural_theme") or ""),
                source_market.get("resolution_time") or source_market.get("close_time"),
            ),
            current_probability=source_market.get("current_probability"),
            resolution_date=str(source_market.get("resolution_time") or source_market.get("close_time") or ""),
            open_time=str(source_market.get("open_time") or ""),
            total_volume_usd=source_market.get("volume_usd"),
            num_traders=source_market.get("num_traders"),
            num_history_points=int(source_market.get("metadata", {}).get("history_points") or 1),
            quality_score=quality_score,
            gates_passed=gates_passed,
            auto_recommendation=recommendation,
            decision=decision_record.get("decision"),
            decision_reason=decision_record.get("decision_reason"),
            decided_by=decision_record.get("decided_by"),
            decided_at=decision_record.get("decided_at"),
            source_url=str(source_market.get("url") or ""),
            liquidity_usd=source_market.get("liquidity_usd"),
            macro_relevance_score=macro_score,
            days_to_resolution=_days_to_resolution(source_market.get("resolution_time") or source_market.get("close_time")),
            family_event_id=str(family.get("event_family_id") or ""),
            **gates,
        )
        candidates.append(candidate.to_dict())

    priority = {"APPROVE": 0, "REVIEW": 1, "REJECT": 2}
    candidates.sort(
        key=lambda row: (
            priority.get(row["auto_recommendation"], 9),
            -int(row["gates_passed"]),
            -float(row["quality_score"]),
            -(float(row.get("total_volume_usd") or 0.0)),
            row["contract_id"],
        )
    )
    return candidates


def find_promotion_candidate(
    root: Path,
    contract_id: str,
    decisions_map: dict[str, dict] | None = None,
) -> dict | None:
    queue = build_promotion_queue(
        root,
        include_rejected=True,
        decision_state="all",
        decisions_map=decisions_map or {},
    )
    return next((row for row in queue if row.get("contract_id") == contract_id), None)
