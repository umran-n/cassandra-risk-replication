from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

from .clients import fetch_manifold_bets, fetch_manifold_search_markets
from .events import load_curated_shortlist
from .utils import epoch_millis_to_date, format_date, parse_date


STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "be",
    "before",
    "by",
    "for",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "will",
    "with",
}


CATEGORY_KEYWORDS = {
    "Kinetic": {"war", "invasion", "military", "armed", "conflict", "ukraine", "taiwan", "china", "russia"},
    "Sovereign": {"bank", "banking", "debt", "default", "sovereign", "ceiling", "contagion", "crisis", "covid"},
    "Trade": {"trade", "tariff", "tariffs", "export", "imports", "sanction", "sanctions", "controls"},
    "Monetary": {"fed", "rates", "rate", "yield", "treasury", "inflation", "tightening", "higher", "longer"},
    "Technology": {"technology", "tech", "ai", "chip", "chips", "semiconductor", "volatility", "carry", "yen"},
}


CATEGORY_QUERY_PACKS = {
    "Kinetic": [
        "Ukraine invade before March 2022",
        "China Taiwan armed conflict 2024",
        "war escalation 2025",
    ],
    "Sovereign": [
        "covid market crash march 2020",
        "Silicon Valley Bank another bank fail March 2023",
        "US debt ceiling May 2023",
        "EU banking contagion November 2024",
        "banking crisis 2024",
        "sovereign default 2025",
    ],
    "Trade": [
        "trade war 2025",
        "tariffs 2024",
        "export controls China 2024",
    ],
    "Monetary": [
        "Fed rate hike recession selloff June 2022",
        "10 year treasury 5% end of 2023",
        "higher for longer rates 2024",
    ],
    "Technology": [
        "August 2024 volatility spike market",
        "yen carry trade August 2024",
        "AI bubble crash 2025",
        "chip export restrictions 2024",
    ],
}


def load_overrides(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return list(json.load(handle))


def tokenize(value: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", value.lower()))
    return {token for token in tokens if token not in STOPWORDS and len(token) > 1}


def normalize_question(value: str) -> str:
    return " ".join(sorted(tokenize(value)))


def build_query_pack(config: dict, seeds: list[dict]) -> list[dict]:
    queries: list[dict] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for seed in seeds:
        for term in seed.get("manifold_search_terms", []):
            key = (term.lower(), seed.get("category"), seed.get("event_id"))
            if key in seen:
                continue
            seen.add(key)
            queries.append(
                {
                    "query": term,
                    "category_hint": seed.get("category"),
                    "event_id_hint": seed.get("event_id"),
                    "query_source": "seed",
                }
            )

    sample_start = parse_date(config["sample"]["start"])
    sample_end = parse_date(config["sample"]["end"])
    active_years = {str(year) for year in range(sample_start.year, sample_end.year + 1)}
    for category, category_queries in CATEGORY_QUERY_PACKS.items():
        for term in category_queries:
            if not any(year in term for year in active_years):
                continue
            key = (term.lower(), category, None)
            if key in seen:
                continue
            seen.add(key)
            queries.append(
                {
                    "query": term,
                    "category_hint": category,
                    "event_id_hint": None,
                    "query_source": "systemic",
                }
            )
    return queries


def seed_lookup(seeds: list[dict]) -> dict[str, dict]:
    lookup = {}
    for seed in seeds:
        lookup[seed["event_id"]] = {
            "event_id": seed["event_id"],
            "category": seed["category"],
            "event_date": parse_date(seed["event_date"]),
            "analysis_bucket": seed.get("analysis_bucket"),
            "tokens": tokenize(seed["question"] + " " + " ".join(seed.get("manifold_search_terms", []))),
        }
    return lookup


def infer_category(question_tokens: set[str], query_spec: dict) -> tuple[str, float]:
    scores: dict[str, float] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        keyword_hits = len(question_tokens & keywords)
        query_bonus = 2.0 if query_spec.get("category_hint") == category else 0.0
        scores[category] = keyword_hits + query_bonus
    best_category = max(scores, key=scores.get)
    return best_category, scores[best_category]


def infer_event_link(
    question_tokens: set[str],
    created_date,
    query_spec: dict,
    seeds: list[dict],
) -> tuple[str | None, float, dict | None]:
    lookup = seed_lookup(seeds)
    if query_spec.get("event_id_hint") and query_spec["event_id_hint"] in lookup:
        seed = lookup[query_spec["event_id_hint"]]
        overlap = len(question_tokens & seed["tokens"])
        days_delta = abs((created_date - seed["event_date"]).days)
        time_score = 2.5 if created_date <= seed["event_date"] else -2.5
        score = 5.0 + overlap + time_score - min(days_delta / 365.0, 2.0)
        return seed["event_id"], score, seed

    best_event_id = None
    best_score = float("-inf")
    best_seed = None
    for seed in lookup.values():
        overlap = len(question_tokens & seed["tokens"])
        category_bonus = 1.5 if seed["category"] == query_spec.get("category_hint") else 0.0
        days_delta = abs((created_date - seed["event_date"]).days)
        time_score = 1.5 if created_date <= seed["event_date"] else -2.0
        score = overlap + category_bonus + time_score - min(days_delta / 365.0, 2.0)
        if score > best_score:
            best_event_id = seed["event_id"]
            best_score = score
            best_seed = seed
    if best_score < 1.5:
        return None, 0.0, None
    return best_event_id, best_score, best_seed


def candidate_history_summary(market_id: str, raw_dir: Path, refresh: bool = False) -> tuple[bool, int]:
    bets = fetch_manifold_bets(market_id, raw_dir, refresh=refresh)
    return bool(bets), len(bets)


def _extract_float(value) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _resolution_value(market: dict) -> str | None:
    resolution = market.get("resolution") or market.get("resolvedOutcome")
    if resolution in {"YES", "NO"}:
        return str(resolution)
    return None


def collect_catalog_hits(
    queries: list[dict],
    seeds: list[dict],
    raw_dir: Path,
    refresh: bool = False,
    limit: int = 15,
) -> list[dict]:
    market_hits: dict[str, dict] = {}
    for query_spec in queries:
        results = fetch_manifold_search_markets(
            query_spec["query"],
            raw_dir,
            refresh=refresh,
            limit=limit,
        )
        for rank, market in enumerate(results, start=1):
            market_id = str(market["id"])
            question = str(market["question"])
            question_tokens = tokenize(question)
            category_guess, category_score = infer_category(question_tokens, query_spec)
            created_date = epoch_millis_to_date(int(market["createdTime"]))
            event_id_guess, event_link_score, seed_match = infer_event_link(question_tokens, created_date, query_spec, seeds)
            hit = market_hits.setdefault(
                market_id,
                {
                    "market_id": market_id,
                    "question": question,
                    "question_normalized": normalize_question(question),
                    "url_slug": market.get("slug") or market.get("url") or "",
                    "created_date": format_date(created_date),
                    "close_date": format_date(epoch_millis_to_date(int(market["closeTime"])))
                    if market.get("closeTime")
                    else None,
                    "resolution_date": format_date(epoch_millis_to_date(int(market["resolutionTime"])))
                    if market.get("resolutionTime")
                    else None,
                    "resolved_outcome": _resolution_value(market),
                    "query": query_spec["query"],
                    "category_guess": category_guess,
                    "event_id_guess": event_id_guess,
                    "analysis_bucket_guess": seed_match["analysis_bucket"] if seed_match else None,
                    "event_link_score": event_link_score,
                    "category_score": category_score,
                    "search_rank": rank,
                    "matched_terms": set(),
                    "query_sources": set(),
                    "binary_market": str(market.get("outcomeType") or "BINARY") == "BINARY",
                    "liquidity": _extract_float(market.get("liquidity") or market.get("totalLiquidity")),
                    "volume": _extract_float(market.get("volume")),
                },
            )
            hit["matched_terms"].add(query_spec["query"])
            hit["query_sources"].add(query_spec["query_source"])
            if rank < hit["search_rank"]:
                hit["search_rank"] = rank
                hit["query"] = query_spec["query"]
            if event_link_score > hit["event_link_score"]:
                hit["event_id_guess"] = event_id_guess
                hit["analysis_bucket_guess"] = seed_match["analysis_bucket"] if seed_match else None
                hit["event_link_score"] = event_link_score
            if category_score > hit["category_score"]:
                hit["category_guess"] = category_guess
                hit["category_score"] = category_score
    return list(market_hits.values())


def collapse_duplicate_candidates(candidates: list[dict]) -> list[dict]:
    collapsed: dict[str, dict] = {}
    for candidate in candidates:
        key = candidate["question_normalized"]
        existing = collapsed.get(key)
        if existing is None:
            candidate["duplicate_market_ids"] = []
            collapsed[key] = candidate
            continue

        current_score = existing["event_link_score"] + (1.0 / max(existing["search_rank"], 1))
        new_score = candidate["event_link_score"] + (1.0 / max(candidate["search_rank"], 1))
        if new_score > current_score:
            candidate["duplicate_market_ids"] = [existing["market_id"], *existing.get("duplicate_market_ids", [])]
            candidate["matched_terms"] = set(candidate["matched_terms"]) | set(existing["matched_terms"])
            candidate["query_sources"] = set(candidate["query_sources"]) | set(existing["query_sources"])
            collapsed[key] = candidate
        else:
            existing["duplicate_market_ids"].append(candidate["market_id"])
            existing["matched_terms"] = set(existing["matched_terms"]) | set(candidate["matched_terms"])
            existing["query_sources"] = set(existing["query_sources"]) | set(candidate["query_sources"])
    return list(collapsed.values())


def apply_curated_decisions(
    candidates: list[dict],
    seeds: list[dict],
    shortlist: list[dict],
    overrides: list[dict],
    raw_dir: Path,
    refresh: bool = False,
) -> list[dict]:
    seed_context = seed_lookup(seeds)
    shortlist_by_id = {entry["market_id"]: entry for entry in shortlist}
    overrides_by_id = {entry["market_id"]: entry for entry in overrides}
    resolved_rows: list[dict] = []

    for candidate in candidates:
        row = candidate.copy()
        row["matched_terms"] = " | ".join(sorted(row["matched_terms"]))
        row["query_sources"] = " | ".join(sorted(row["query_sources"]))
        row["duplicate_market_ids"] = " | ".join(sorted(row.get("duplicate_market_ids", [])))
        row["candidate_score"] = 0.0
        row["status"] = "pending"
        row["reject_reason"] = ""
        row["selection_reason"] = ""
        row["pre_event_eligible"] = False
        row["has_history"] = False
        row["bet_count"] = 0

        override = overrides_by_id.get(row["market_id"])
        if override:
            if override.get("forced_category"):
                row["category_guess"] = override["forced_category"]
            if override.get("forced_event_id"):
                row["event_id_guess"] = override["forced_event_id"]
                seed = seed_context.get(row["event_id_guess"])
                row["analysis_bucket_guess"] = override.get("forced_analysis_bucket") or (seed["analysis_bucket"] if seed else None)

        has_history, bet_count = candidate_history_summary(row["market_id"], raw_dir, refresh=refresh)
        row["has_history"] = has_history
        row["bet_count"] = bet_count

        pre_event_eligible = False
        eligibility_reason = ""
        if not row["binary_market"]:
            eligibility_reason = "non_binary_market"
        elif row["event_id_guess"] and row["event_id_guess"] in seed_context:
            event_date = seed_context[row["event_id_guess"]]["event_date"]
            created_date = parse_date(row["created_date"])
            if created_date > event_date:
                eligibility_reason = "created_after_event_window"
            elif not has_history:
                eligibility_reason = "empty_bet_history"
            else:
                pre_event_eligible = True
        else:
            eligibility_reason = "no_event_link_guess"
        row["pre_event_eligible"] = pre_event_eligible

        relevance_score = row["event_link_score"] + row["category_score"] + (1.0 / max(int(row["search_rank"]), 1))
        volume_score = min(math.log10(max(row["volume"], 0.0) + 1.0), 4.0) / 4.0
        liquidity_score = min(math.log10(max(row["liquidity"], 0.0) + 1.0), 4.0) / 4.0
        proxy_quality = (1.5 if pre_event_eligible else -1.0) + (1.0 if has_history else -1.0) + volume_score + liquidity_score
        row["candidate_score"] = round(relevance_score + proxy_quality, 6)

        if override and override.get("approved") is False:
            row["status"] = "rejected"
            row["reject_reason"] = override.get("reject_reason") or "manual_override_reject"
        elif row["market_id"] in shortlist_by_id:
            if pre_event_eligible:
                row["status"] = "approved"
                row["selection_reason"] = shortlist_by_id[row["market_id"]].get("selection_reason", "Approved shortlist entry.")
            else:
                row["status"] = "rejected"
                row["reject_reason"] = eligibility_reason or "approved_but_ineligible"
        elif not row["binary_market"] or (row["event_id_guess"] and not pre_event_eligible):
            row["status"] = "rejected"
            row["reject_reason"] = eligibility_reason or "failed_eligibility_gate"
        elif override and override.get("approved") is True:
            row["status"] = "pending"
            row["selection_reason"] = "Override marked this candidate for approval review, but it is not yet in the curated shortlist."
        else:
            row["status"] = "pending"
            row["reject_reason"] = eligibility_reason if eligibility_reason == "no_event_link_guess" else ""

        resolved_rows.append(row)

    resolved_rows.sort(key=lambda row: (row["status"] != "approved", row["event_id_guess"] or "", -row["candidate_score"]))
    return resolved_rows


def build_selection_audit(seeds: list[dict], catalog_rows: list[dict], shortlist: list[dict]) -> list[dict]:
    shortlist_by_event: dict[str, list[dict]] = defaultdict(list)
    for entry in shortlist:
        shortlist_by_event[entry["event_id"]].append(entry)
    rows: list[dict] = []
    for seed in seeds:
        linked = [row for row in catalog_rows if row.get("event_id_guess") == seed["event_id"]]
        linked.sort(key=lambda row: (-row["candidate_score"], row["search_rank"]))
        approved_entries = shortlist_by_event.get(seed["event_id"], [])
        top = linked[0] if linked else None
        if approved_entries:
            status = "approved"
            approved_market_id = approved_entries[0]["market_id"]
            approved_market_ids = " | ".join(entry["market_id"] for entry in approved_entries)
            approved_market_count = len(approved_entries)
            selection_reason = " || ".join(
                f"{entry['market_id']}: {entry.get('selection_reason', '')}".strip()
                for entry in approved_entries
            )
            rejection_reason = ""
        elif not linked:
            status = "no_candidates"
            approved_market_id = None
            approved_market_ids = ""
            approved_market_count = 0
            selection_reason = ""
            rejection_reason = "no_candidates_found_for_event"
        elif any(row["status"] == "pending" for row in linked):
            status = "pending"
            approved_market_id = None
            approved_market_ids = ""
            approved_market_count = 0
            selection_reason = ""
            rejection_reason = top["reject_reason"] or "requires_manual_review"
        else:
            status = "rejected"
            approved_market_id = None
            approved_market_ids = ""
            approved_market_count = 0
            selection_reason = ""
            rejection_reason = top["reject_reason"] or "all_candidates_rejected"
        rows.append(
            {
                "event_id": seed["event_id"],
                "category": seed["category"],
                "search_terms": " | ".join(seed.get("manifold_search_terms", [])),
                "candidate_count": len(linked),
                "approved_market_id": approved_market_id,
                "approved_market_ids": approved_market_ids,
                "approved_market_count": approved_market_count,
                "top_market_id": top["market_id"] if top else None,
                "top_question": top["question"] if top else None,
                "category_guess": top["category_guess"] if top else None,
                "event_link_guess": top["event_id_guess"] if top else None,
                "pre_event_eligible": top["pre_event_eligible"] if top else False,
                "search_rank": top["search_rank"] if top else None,
                "candidate_score": top["candidate_score"] if top else None,
                "status": status,
                "selection_reason": selection_reason,
                "rejection_reason": rejection_reason,
            }
        )
    return rows


def build_catalog_summary(queries: list[dict], catalog_rows: list[dict], selection_audit_rows: list[dict]) -> dict:
    summary = {
        "query_count": len(queries),
        "catalog_candidate_count": len(catalog_rows),
        "approved_count": sum(1 for row in catalog_rows if row["status"] == "approved"),
        "rejected_count": sum(1 for row in catalog_rows if row["status"] == "rejected"),
        "pending_count": sum(1 for row in catalog_rows if row["status"] == "pending"),
        "by_category": {},
        "by_year": {},
        "kill_list_coverage": selection_audit_rows,
    }
    for row in catalog_rows:
        category = row["category_guess"]
        created_year = row["created_date"][:4]
        summary["by_category"][category] = summary["by_category"].get(category, 0) + 1
        summary["by_year"][created_year] = summary["by_year"].get(created_year, 0) + 1
    return summary


def discover_manifold_catalog(
    config: dict,
    seeds: list[dict],
    shortlist_path: Path,
    overrides_path: Path,
    raw_dir: Path,
    refresh: bool = False,
) -> dict:
    queries = build_query_pack(config, seeds)
    shortlist = load_curated_shortlist(shortlist_path)
    overrides = load_overrides(overrides_path)
    raw_hits = collect_catalog_hits(queries, seeds, raw_dir, refresh=refresh)
    sample_start = parse_date(config["sample"]["start"])
    sample_end = parse_date(config["sample"]["end"])
    raw_hits = [
        row
        for row in raw_hits
        if sample_start <= parse_date(row["created_date"]) <= sample_end
    ]
    deduped_hits = collapse_duplicate_candidates(raw_hits)
    catalog_rows = apply_curated_decisions(deduped_hits, seeds, shortlist, overrides, raw_dir, refresh=refresh)
    selection_audit_rows = build_selection_audit(seeds, catalog_rows, shortlist)
    summary = build_catalog_summary(queries, catalog_rows, selection_audit_rows)
    return {
        "queries": queries,
        "catalog_rows": catalog_rows,
        "selection_audit_rows": selection_audit_rows,
        "summary": summary,
    }
