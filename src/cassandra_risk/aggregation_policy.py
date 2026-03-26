from __future__ import annotations

from typing import Any, Iterable


VALID_AGGREGATION_POLICIES = {
    "max",
    "weighted_average",
}


THEME_DEFAULT_POLICY = {
    "monetary_policy": "max",
    "geopolitical": "weighted_average",
    "fiscal_debt": "max",
    "electoral": "max",
    "systemic_credit": "max",
    "trade_technology": "max",
}


def theme_default_aggregation_policy(theme: str) -> str:
    return THEME_DEFAULT_POLICY.get(str(theme or "").strip(), "max")


def _extract_candidate_policy(candidate: Any) -> str:
    if candidate is None:
        return ""
    if hasattr(candidate, "aggregation_policy"):
        return str(getattr(candidate, "aggregation_policy") or "").strip()
    if isinstance(candidate, dict):
        return str(candidate.get("aggregation_policy") or "").strip()
    return ""


def candidate_policy_set(candidates: Iterable[Any]) -> set[str]:
    return {
        policy
        for policy in (_extract_candidate_policy(candidate) for candidate in candidates)
        if policy in VALID_AGGREGATION_POLICIES
    }


def resolve_aggregation_policy(
    explicit_policy: str | None,
    *,
    structural_theme: str,
    candidates: Iterable[Any] = (),
) -> tuple[str, bool]:
    policy = str(explicit_policy or "").strip()
    if policy in VALID_AGGREGATION_POLICIES:
        return policy, False

    candidate_policies = candidate_policy_set(candidates)
    if len(candidate_policies) == 1:
        return next(iter(candidate_policies)), True

    return theme_default_aggregation_policy(structural_theme), True


def backfill_registry_aggregation_policy(rows: list[dict]) -> tuple[list[dict], bool]:
    changed = False
    normalized_rows: list[dict] = []

    for row in rows:
        normalized = dict(row)
        source_candidates = [dict(candidate) for candidate in normalized.get("source_candidates", [])]
        policy, backfilled = resolve_aggregation_policy(
            normalized.get("aggregation_policy"),
            structural_theme=str(normalized.get("structural_theme") or normalized.get("theme") or ""),
            candidates=source_candidates,
        )
        if normalized.get("aggregation_policy") != policy:
            normalized["aggregation_policy"] = policy
            changed = True
        if backfilled and not normalized.get("_policy_backfilled", False):
            normalized["_policy_backfilled"] = True
            changed = True
        for candidate in source_candidates:
            if candidate.get("aggregation_policy") != policy:
                candidate["aggregation_policy"] = policy
                changed = True
        normalized["source_candidates"] = source_candidates
        normalized_rows.append(normalized)

    return normalized_rows, changed
