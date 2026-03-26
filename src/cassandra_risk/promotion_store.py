from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .aggregation_policy import backfill_registry_aggregation_policy, resolve_aggregation_policy
from .event_graph import load_legacy_governed_event_families
from .promotion_workflow import PromotionCandidate, contract_id_for_market
from .utils import ensure_dir, write_csv, write_json


def _governed_dir(root: Path) -> Path:
    return ensure_dir(root / "data" / "governed")


def signal_registry_path(root: Path) -> Path:
    return _governed_dir(root) / "signal_registry.json"


def promotion_audit_json_path(root: Path) -> Path:
    return _governed_dir(root) / "promotion_audit.json"


def promotion_audit_csv_path(root: Path) -> Path:
    return _governed_dir(root) / "promotion_audit.csv"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    import json

    with path.open("r", encoding="utf-8") as handle:
        return list(json.load(handle))


def load_signal_registry(root: Path, bootstrap: bool = True) -> list[dict]:
    path = signal_registry_path(root)
    if path.exists():
        rows = _load_json_list(path)
        normalized_rows, changed = backfill_registry_aggregation_policy(rows)
        if changed:
            write_signal_registry(root, normalized_rows)
        return normalized_rows
    if bootstrap:
        return bootstrap_signal_registry(root)
    return []


def write_signal_registry(root: Path, rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda row: (row.get("structural_theme", ""), row.get("event_family_id", "")))
    write_json(signal_registry_path(root), rows)


def load_promotion_audit(root: Path, bootstrap: bool = True) -> list[dict]:
    path = promotion_audit_json_path(root)
    if path.exists():
        return _load_json_list(path)
    if bootstrap:
        bootstrap_signal_registry(root)
        return _load_json_list(path)
    return []


def write_promotion_audit(root: Path, rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda row: (row.get("decided_at", ""), row.get("contract_id", "")))
    write_json(promotion_audit_json_path(root), rows)
    write_csv(promotion_audit_csv_path(root), rows)


def latest_decisions_map(root: Path) -> dict[str, dict]:
    audit_rows = load_promotion_audit(root)
    latest: dict[str, dict] = {}
    for row in audit_rows:
        latest[row["contract_id"]] = row
    return latest


def bootstrap_signal_registry(root: Path) -> list[dict]:
    registry_rows = []
    audit_rows = []
    timestamp = _now_iso()
    for family in load_legacy_governed_event_families(root):
        aggregation_policy, backfilled = resolve_aggregation_policy(
            family.get("aggregation_policy"),
            structural_theme=str(family.get("structural_theme") or family.get("theme") or ""),
            candidates=family.get("source_candidates", []),
        )
        first_candidate = next(iter(family.get("source_candidates", [])), {})
        contract_id = contract_id_for_market(
            str(first_candidate.get("source") or "legacy"),
            str(first_candidate.get("market_id") or family["event_family_id"]),
        )
        registry_row = {
            "event_family_id": family["event_family_id"],
            "title": family["title"],
            "structural_theme": family["structural_theme"],
            "theme": family["structural_theme"],
            "category": family["category"],
            "governance_source": "signal_registry_bootstrap",
            "proxy_family_id": family["proxy_family_id"],
            "source_candidates": [
                {
                    **dict(candidate),
                    "aggregation_policy": dict(candidate).get("aggregation_policy") or aggregation_policy,
                }
                for candidate in family.get("source_candidates", [])
            ],
            "discovered": False,
            "notes": family.get("notes", ""),
            "approval_status": "APPROVED",
            "approval_reason": "Bootstrap imported from legacy governed universe.",
            "aggregation_policy": aggregation_policy,
            "_policy_backfilled": backfilled,
            "decided_by": "bootstrap",
            "decided_at": timestamp,
        }
        registry_rows.append(registry_row)
        audit_rows.append(
            {
                "contract_id": contract_id,
                "event_family_id": family["event_family_id"],
                "source": first_candidate.get("source", "legacy"),
                "market_id": first_candidate.get("market_id", ""),
                "title": family["title"],
                "structural_theme": family["structural_theme"],
                "decision": "APPROVED",
                "decision_reason": "Bootstrap imported from legacy governed universe.",
                "decided_by": "bootstrap",
                "decided_at": timestamp,
                "quality_score": first_candidate.get("quality_score", ""),
                "gates_passed": "",
                "auto_recommendation": "APPROVE",
            }
        )
    write_signal_registry(root, registry_rows)
    write_promotion_audit(root, audit_rows)
    return registry_rows


def _upsert_registry_row(rows: list[dict], new_row: dict) -> list[dict]:
    updated = False
    for idx, row in enumerate(rows):
        if row.get("event_family_id") == new_row.get("event_family_id"):
            rows[idx] = new_row
            updated = True
            break
    if not updated:
        rows.append(new_row)
    return rows


def build_registry_row_from_candidate(
    candidate: PromotionCandidate,
    proxy_family_id: str,
    reason: str,
    decided_by: str,
    aggregation_policy: str = "max",
    event_family_id: str = "",
) -> dict:
    final_event_family_id = event_family_id or proxy_family_id
    source_candidate = {
        "link_type": "governed_reference",
        "source": candidate.contract.source.value,
        "market_id": candidate.contract.native_id,
        "title": candidate.contract.question_text,
        "resolution_date": candidate.contract.resolution_time,
        "quality_score": candidate.quality_score,
        "aggregation_policy": aggregation_policy,
        "volume_usd": candidate.contract.volume_usd,
        "open_time": candidate.contract.open_time,
    }
    return {
        "event_family_id": final_event_family_id,
        "title": candidate.contract.question_text,
        "structural_theme": candidate.contract.structural_theme,
        "theme": candidate.contract.structural_theme,
        "category": candidate.contract.category,
        "governance_source": "promotion_workflow",
        "proxy_family_id": proxy_family_id,
        "source_candidates": [source_candidate],
        "discovered": False,
        "notes": reason,
        "approval_status": "APPROVED",
        "approval_reason": reason,
        "aggregation_policy": aggregation_policy,
        "decided_by": decided_by,
        "decided_at": _now_iso(),
    }


def apply_promotion_decision(
    root: Path,
    candidate: PromotionCandidate,
    decision: str,
    reason: str,
    decided_by: str = "operator",
    proxy_family_id: str = "",
    aggregation_policy: str = "",
    event_family_id: str = "",
) -> dict:
    decision_upper = decision.upper()
    registry_rows = load_signal_registry(root)
    audit_rows = load_promotion_audit(root)
    timestamp = _now_iso()

    final_proxy_family_id = proxy_family_id or candidate.proxy_family_id or candidate.family_event_id or "promoted_candidate"
    final_event_family_id = event_family_id or final_proxy_family_id

    final_aggregation_policy = aggregation_policy or candidate.contract.aggregation_policy

    if decision_upper == "APPROVED":
        registry_row = build_registry_row_from_candidate(
            candidate,
            proxy_family_id=final_proxy_family_id,
            reason=reason,
            decided_by=decided_by,
            aggregation_policy=final_aggregation_policy,
            event_family_id=final_event_family_id,
        )
        registry_rows = _upsert_registry_row(registry_rows, registry_row)
        write_signal_registry(root, registry_rows)

    audit_row = {
        "contract_id": candidate.contract_id,
        "event_family_id": final_event_family_id,
        "source": candidate.contract.source.value,
        "market_id": candidate.contract.native_id,
        "title": candidate.contract.question_text,
        "structural_theme": candidate.contract.structural_theme,
        "decision": decision_upper,
        "decision_reason": reason,
        "decided_by": decided_by,
        "decided_at": timestamp,
        "quality_score": candidate.quality_score,
        "gates_passed": candidate.gates_passed,
        "auto_recommendation": candidate.auto_recommendation,
        "proxy_family_id": final_proxy_family_id,
        "aggregation_policy": final_aggregation_policy,
    }
    audit_rows.append(audit_row)
    write_promotion_audit(root, audit_rows)
    return audit_row
