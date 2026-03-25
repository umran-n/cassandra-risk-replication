from __future__ import annotations

import json
from pathlib import Path

from .events import infer_category_from_theme
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
    event_family_id = str(record.get("event_id") or record.get("proxy_family_id") or title.lower().replace(" ", "_"))
    proxy_family_id = str(record.get("proxy_family_id") or event_family_id)
    notes = str(record.get("approval_reason") or record.get("notes") or "")
    family = EventFamily(
        event_family_id=event_family_id,
        title=title,
        structural_theme=theme,
        category=category,
        governance_source=governance_source,
        proxy_family_id=proxy_family_id,
        source_candidates=[],
        discovered=False,
        notes=notes,
    )
    family.source_candidates.append(
        {
            "link_type": "governed_reference",
            "source": str(record.get("source") or governance_source),
            "market_id": str(record.get("market_id") or ""),
            "title": title,
            "resolution_date": record.get("resolution_date"),
            "quality_score": record.get("quality_score"),
        }
    )
    return family


def load_governed_event_families(root: Path) -> list[dict]:
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


def _link_score(family: dict, market: dict) -> float:
    tokens_family = _family_tokens(family)
    tokens_market = normalize_tokens(market.get("title"), market.get("metadata", {}).get("subtitle"))
    score = jaccard_score(tokens_family, tokens_market)
    if market.get("structural_theme") == family.get("structural_theme"):
        score += 0.1
    return min(score, 1.0)


def build_event_graph(
    governed_families: list[dict],
    source_markets: list[dict],
    registry: dict,
) -> tuple[list[dict], list[dict]]:
    threshold = float(registry.get("selection_policy", {}).get("minimum_text_overlap_score", 0.3))
    min_quality = float(registry.get("selection_policy", {}).get("minimum_quality_score", 0.4))
    families = [json.loads(json.dumps(family)) for family in governed_families]
    link_audit: list[dict] = []
    linked_market_ids: set[tuple[str, str]] = set()

    for market in source_markets:
        market_key = (str(market.get("source")), str(market.get("market_id")))
        best_family = None
        best_score = 0.0

        for family in families:
            if market_key in _known_source_market_ids(family):
                best_family = family
                best_score = 1.0
                break
            if market.get("structural_theme") != family.get("structural_theme"):
                continue
            score = _link_score(family, market)
            if score > best_score:
                best_score = score
                best_family = family

        if best_family is not None and best_score >= threshold:
            linked_market_ids.add(market_key)
            attached = dict(market)
            attached["link_score"] = round(best_score, 6)
            attached["link_type"] = "explicit_market_id" if best_score >= 1.0 else "title_similarity"
            best_family.setdefault("linked_markets", []).append(attached)
            link_audit.append(
                {
                    "event_family_id": best_family["event_family_id"],
                    "source": market["source"],
                    "market_id": market["market_id"],
                    "title": market["title"],
                    "link_score": round(best_score, 6),
                    "link_status": attached["link_type"],
                }
            )
        else:
            link_audit.append(
                {
                    "event_family_id": "",
                    "source": market["source"],
                    "market_id": market["market_id"],
                    "title": market["title"],
                    "link_score": round(best_score, 6),
                    "link_status": "unlinked",
                }
            )

    max_unlinked_per_theme = int(registry.get("selection_policy", {}).get("max_unlinked_candidates_per_theme", 8))
    by_theme: dict[str, list[dict]] = {}
    for market in source_markets:
        market_key = (str(market.get("source")), str(market.get("market_id")))
        if market_key in linked_market_ids:
            continue
        if float(market.get("quality_score") or 0.0) < min_quality:
            continue
        theme = str(market.get("structural_theme") or "trade_technology")
        by_theme.setdefault(theme, []).append(market)

    for theme, items in by_theme.items():
        items.sort(key=lambda row: (-float(row.get("quality_score") or 0.0), row.get("source"), row.get("market_id")))
        for market in items[:max_unlinked_per_theme]:
            family = EventFamily(
                event_family_id=f"discovered_{market['source']}_{market['market_id']}",
                title=str(market.get("title") or ""),
                structural_theme=theme,
                category=str(market.get("category") or infer_category_from_theme(theme)),
                governance_source="autonomous_discovery",
                proxy_family_id=f"discovered_{theme}_{market['source']}",
                source_candidates=[],
                discovered=True,
                notes="Autonomously discovered live market candidate not yet promoted into the governed universe.",
            )
            linked = dict(market)
            linked["link_score"] = 1.0
            linked["link_type"] = "autonomous_discovery"
            family_dict = family.to_dict()
            family_dict["linked_markets"] = [linked]
            families.append(family_dict)

    families.sort(key=lambda row: (row.get("discovered", False), row["structural_theme"], row["event_family_id"]))
    link_audit.sort(key=lambda row: (row["link_status"], row["source"], row["market_id"]))
    return families, link_audit
