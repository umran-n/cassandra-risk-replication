from __future__ import annotations

import json
import re
from pathlib import Path

from .aggregation_policy import backfill_registry_aggregation_policy, resolve_aggregation_policy, theme_default_aggregation_policy
from .events import infer_category_from_theme
from .signal_contract import SignalContract, ensure_signal_contract
from .signal_types import EventFamily
from .sources.base import jaccard_score, normalize_tokens
from .taxonomy import infer_structural_theme


def _load_json_if_exists(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return list(payload)


def _canonical_title(record: dict) -> str:
    return str(record.get("title") or record.get("question") or record.get("event_id") or "").strip()


def _canonical_theme(record: dict) -> str:
    if record.get("theme"):
        return str(record["theme"])
    return infer_structural_theme(record)


def _base_family(record: dict, governance_source: str) -> EventFamily:
    title = _canonical_title(record)
    theme = _canonical_theme(record)
    category = str(record.get("category") or infer_category_from_theme(theme))
    event_family_id = str(record.get("event_family_id") or record.get("event_id") or record.get("proxy_family_id") or title.lower().replace(" ", "_"))
    proxy_family_id = str(record.get("proxy_family_id") or event_family_id)
    notes = str(record.get("approval_reason") or record.get("notes") or "")
    aggregation_policy, _ = resolve_aggregation_policy(
        record.get("aggregation_policy"),
        structural_theme=theme,
        candidates=record.get("source_candidates", []),
    )
    family = EventFamily(
        event_family_id=event_family_id,
        title=title,
        structural_theme=theme,
        category=category,
        governance_source=governance_source,
        proxy_family_id=proxy_family_id,
        aggregation_policy=aggregation_policy,
        source_candidates=[],
        discovered=False,
        notes=notes,
    )
    if record.get("source_candidates"):
        for candidate in record.get("source_candidates", []):
            normalized_candidate = dict(candidate)
            normalized_candidate.setdefault("aggregation_policy", aggregation_policy)
            family.source_candidates.append(normalized_candidate)
    else:
        family.source_candidates.append(
            {
                "link_type": "governed_reference",
                "source": str(record.get("source") or governance_source),
                "market_id": str(record.get("market_id") or ""),
                "title": title,
                "resolution_date": record.get("resolution_date"),
                "quality_score": record.get("quality_score"),
                "aggregation_policy": aggregation_policy,
            }
        )
    return family


def load_legacy_governed_event_families(root: Path) -> list[dict]:
    families: dict[str, EventFamily] = {}

    sources = [
        (root / "data" / "seeds" / "event_seeds.json", "seed_file"),
        (root / "data" / "curated" / "manifold_shortlist.json", "manifold_shortlist"),
        (root / "data" / "curated" / "polymarket_approved.json", "polymarket_approved"),
        (root / "data" / "curated" / "polymarket_geopolitical_expansion.json", "polymarket_geo_expansion"),
    ]
    for path, governance_source in sources:
        for record in _load_json_if_exists(path):
            family = _base_family(record, governance_source)
            existing = families.get(family.event_family_id)
            if existing is None:
                families[family.event_family_id] = family
            else:
                existing.source_candidates.extend(family.source_candidates)
                if not existing.notes and family.notes:
                    existing.notes = family.notes

    rows = [family.to_dict() for family in families.values()]
    rows.sort(key=lambda row: (row["structural_theme"], row["event_family_id"]))
    return rows


def load_governed_event_families(root: Path) -> list[dict]:
    signal_registry_path = root / "data" / "governed" / "signal_registry.json"
    if signal_registry_path.exists():
        families: dict[str, EventFamily] = {}
        raw_rows = _load_json_if_exists(signal_registry_path)
        normalized_rows, changed = backfill_registry_aggregation_policy(raw_rows)
        if changed:
            with signal_registry_path.open("w", encoding="utf-8") as handle:
                json.dump(normalized_rows, handle, indent=2)
        for record in normalized_rows:
            family = _base_family(record, "signal_registry")
            existing = families.get(family.event_family_id)
            if existing is None:
                families[family.event_family_id] = family
            else:
                existing.source_candidates.extend(family.source_candidates)
                if not existing.notes and family.notes:
                    existing.notes = family.notes
        if families:
            rows = [family.to_dict() for family in families.values()]
            rows.sort(key=lambda row: (row["structural_theme"], row["event_family_id"]))
            return rows
    return load_legacy_governed_event_families(root)


def _known_source_market_ids(family: dict) -> set[tuple[str, str]]:
    known = set()
    for candidate in family.get("source_candidates", []):
        source = str(candidate.get("source") or "")
        market_id = str(candidate.get("market_id") or "")
        if source and market_id:
            known.add((source.lower(), market_id))
    return known


def _family_tokens(family: dict) -> set[str]:
    return normalize_tokens(family.get("title"), family.get("event_family_id"), family.get("notes"))


def _extract_year(value: object) -> int | None:
    if value is None:
        return None
    match = re.search(r"(19|20)\d{2}", str(value))
    if not match:
        return None
    return int(match.group(0))


def _family_reference_years(family: dict) -> set[int]:
    years: set[int] = set()
    years.add(_extract_year(family.get("event_family_id")) or 0)
    years.add(_extract_year(family.get("title")) or 0)
    for candidate in family.get("source_candidates", []):
        year = _extract_year(candidate.get("resolution_date"))
        if year is not None:
            years.add(year)
    years.discard(0)
    return years


def _market_reference_year(market: dict) -> int | None:
    for key in ("resolution_time", "close_time", "open_time", "title"):
        year = _extract_year(market.get(key))
        if year is not None:
            return year
    return None


def _temporal_link_allowed(family: dict, market: dict) -> bool:
    family_years = _family_reference_years(family)
    market_year = _market_reference_year(market)
    if not family_years or market_year is None:
        return True
    return min(abs(year - market_year) for year in family_years) <= 1


def _link_score(family: dict, market: dict) -> float:
    tokens_family = _family_tokens(family)
    contract = ensure_signal_contract(market)
    tokens_market = normalize_tokens(contract.question_text, contract.metadata.get("subtitle"))
    score = jaccard_score(tokens_family, tokens_market)
    if contract.structural_theme == family.get("structural_theme"):
        score += 0.1
    return min(score, 1.0)


def build_event_graph(
    governed_families: list[dict],
    source_markets: list[SignalContract | dict],
    registry: dict,
) -> tuple[list[dict], list[dict]]:
    threshold = float(registry.get("selection_policy", {}).get("minimum_text_overlap_score", 0.3))
    min_quality = float(registry.get("selection_policy", {}).get("minimum_quality_score", 0.4))
    families = [json.loads(json.dumps(family)) for family in governed_families]
    link_audit: list[dict] = []
    linked_market_ids: set[tuple[str, str]] = set()

    for market in source_markets:
        contract = ensure_signal_contract(market)
        market_key = (contract.source.value, contract.native_id)
        best_family = None
        best_score = 0.0

        for family in families:
            if market_key in _known_source_market_ids(family):
                best_family = family
                best_score = 1.0
                break
            if contract.structural_theme != family.get("structural_theme"):
                continue
            if not _temporal_link_allowed(family, contract.to_dict(include_aliases=True)):
                continue
            score = _link_score(family, contract)
            if score > best_score:
                best_score = score
                best_family = family

        if best_family is not None and best_score >= threshold:
            linked_market_ids.add(market_key)
            attached = contract.with_updates(
                link_score=round(best_score, 6),
                link_type="explicit_market_id" if best_score >= 1.0 else "title_similarity",
                event_family_id=str(best_family["event_family_id"]),
                governance_source=str(best_family.get("governance_source", "")),
                discovered=bool(best_family.get("discovered", False)),
                notes=str(best_family.get("notes", "")),
            )
            best_family.setdefault("linked_markets", []).append(attached)
            link_audit.append(
                {
                    "event_family_id": best_family["event_family_id"],
                    "source": contract.source.value,
                    "market_id": contract.native_id,
                    "title": contract.question_text,
                    "link_score": round(best_score, 6),
                    "link_status": attached.link_type,
                }
            )
        else:
            link_audit.append(
                {
                    "event_family_id": "",
                    "source": contract.source.value,
                    "market_id": contract.native_id,
                    "title": contract.question_text,
                    "link_score": round(best_score, 6),
                    "link_status": "unlinked",
                }
            )

    max_unlinked_per_theme = int(registry.get("selection_policy", {}).get("max_unlinked_candidates_per_theme", 8))
    by_theme: dict[str, list[dict]] = {}
    for market in source_markets:
        contract = ensure_signal_contract(market)
        market_key = (contract.source.value, contract.native_id)
        if market_key in linked_market_ids:
            continue
        if float(contract.quality_score or 0.0) < min_quality:
            continue
        theme = str(contract.structural_theme or "trade_technology")
        by_theme.setdefault(theme, []).append(contract)

    for theme, items in by_theme.items():
        items.sort(key=lambda row: (-float(row.quality_score or 0.0), row.source.value, row.native_id))
        for market in items[:max_unlinked_per_theme]:
            family = EventFamily(
                event_family_id=f"discovered_{market.source.value}_{market.native_id}",
                title=str(market.question_text or ""),
                structural_theme=theme,
                category=str(market.category or infer_category_from_theme(theme)),
                governance_source="autonomous_discovery",
                proxy_family_id=f"discovered_{theme}_{market.source.value}",
                aggregation_policy=theme_default_aggregation_policy(theme),
                source_candidates=[],
                discovered=True,
                notes="Autonomously discovered live market candidate not yet promoted into the governed universe.",
            )
            linked = market.with_updates(
                link_score=1.0,
                link_type="autonomous_discovery",
                event_family_id=family.event_family_id,
                governance_source=family.governance_source,
                discovered=True,
                notes=family.notes,
            )
            family_dict = family.to_dict()
            family_dict["linked_markets"] = [linked]
            families.append(family_dict)

    families.sort(key=lambda row: (row.get("discovered", False), row["structural_theme"], row["event_family_id"]))
    link_audit.sort(key=lambda row: (row["link_status"], row["source"], row["market_id"]))
    return families, link_audit


def serialize_families(families: list[dict]) -> list[dict]:
    serialized: list[dict] = []
    for family in families:
        row = dict(family)
        linked_markets = []
        for market in row.get("linked_markets", []):
            contract = ensure_signal_contract(market)
            linked_markets.append(contract.to_dict(include_aliases=True))
        row["linked_markets"] = linked_markets
        serialized.append(row)
    return serialized
