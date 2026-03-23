from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from .clients import fetch_manifold_bets, fetch_manifold_market, fetch_manifold_search_markets
from .utils import date_range, epoch_millis_to_date, format_date, parse_date, smoothstep


def build_event_panel(config: dict, seeds: list[dict], raw_dir: Path, refresh: bool = False) -> list[dict]:
    rows: list[dict] = []
    for seed in seeds:
        if seed["source"] == "Manifold" and seed.get("market_id"):
            rows.extend(build_manifold_event_rows(config, seed, raw_dir, refresh=refresh))
        else:
            rows.extend(build_manual_event_rows(seed))
    rows.sort(key=lambda row: (row["date"], row["event_id"], row["source"]))
    return rows


def load_curated_shortlist(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return list(payload)


def merge_seeds_with_shortlist(seeds: list[dict], shortlist: list[dict]) -> tuple[list[dict], list[dict]]:
    merged = {seed["event_id"]: seed.copy() for seed in seeds}
    merge_audit: list[dict] = []
    approved_event_ids = {entry["event_id"] for entry in shortlist}

    for seed in seeds:
        if seed["event_id"] in approved_event_ids:
            continue
        merge_audit.append(
            {
                "event_id": seed["event_id"],
                "merge_action": "manual_retained",
                "source": seed["source"],
                "market_id": seed.get("market_id"),
                "selection_reason": "No approved curated shortlist entry for this event.",
            }
        )

    for entry in shortlist:
        previous = merged.get(entry["event_id"])
        merged[entry["event_id"]] = entry.copy()
        merge_audit.append(
            {
                "event_id": entry["event_id"],
                "merge_action": "replaced_existing_event" if previous is not None else "added_curated_event",
                "source": entry["source"],
                "market_id": entry.get("market_id"),
                "selection_reason": entry.get("selection_reason", "Approved curated shortlist entry."),
            }
        )

    merged_rows = sorted(merged.values(), key=lambda item: item["event_id"])
    merge_audit.sort(key=lambda row: row["event_id"])
    return merged_rows, merge_audit


def resolve_event_sources(
    seeds: list[dict],
    raw_dir: Path,
    refresh: bool = False,
    enable_manifold_search: bool = False,
) -> tuple[list[dict], list[dict]]:
    resolved_seeds: list[dict] = []
    audit_rows: list[dict] = []
    for seed in seeds:
        resolved_seed = seed.copy()
        search_terms = collect_search_terms(seed)
        search_hits = collect_manifold_candidates(search_terms, raw_dir, refresh=refresh)
        selected_market_id = seed.get("market_id") or seed.get("manifold_selected_market_id")
        selected_hit = search_hits.get(selected_market_id) if selected_market_id else None
        event_date = parse_date(seed["event_date"])
        created_date = None
        pre_event_match = False
        if selected_hit is not None:
            created_date = epoch_millis_to_date(int(selected_hit["market"]["createdTime"]))
            pre_event_match = created_date <= event_date

        replacement_status = "manual_kept"
        selection_reason = "No vetted Manifold replacement configured for this seed."
        if seed["source"] == "Manifold" and seed.get("market_id"):
            replacement_status = "existing_manifold_seed"
            selection_reason = "Existing Manifold market retained."
        elif enable_manifold_search and selected_hit is not None and pre_event_match:
            resolved_seed["source"] = "Manifold"
            resolved_seed["market_id"] = selected_market_id
            resolved_seed["provenance"] = "archive_recovered"
            if selected_hit["matched_terms"]:
                resolved_seed["search_term"] = selected_hit["matched_terms"][0]
            replacement_status = "selected_pre_event_manifold_proxy"
            selection_reason = "Manual reconstruction replaced with a pre-event Manifold market recovered via search."
        elif enable_manifold_search and selected_hit is not None and not pre_event_match:
            replacement_status = "post_event_market_rejected"
            selection_reason = "A matching Manifold market exists, but it was created after the event window and was rejected."
        elif enable_manifold_search and search_hits:
            replacement_status = "search_results_reviewed_manual_kept"
            selection_reason = "Search returned candidates, but none were pre-vetted as acceptable replacements."
        elif enable_manifold_search:
            replacement_status = "no_manifold_match"
            selection_reason = "No usable Manifold market was found with the configured search terms."

        resolved_seeds.append(resolved_seed)
        audit_rows.append(
            build_search_audit_row(
                seed=seed,
                search_terms=search_terms,
                search_hits=search_hits,
                selected_market_id=selected_market_id,
                selected_hit=selected_hit,
                replacement_status=replacement_status,
                selection_reason=selection_reason,
                pre_event_match=pre_event_match,
            )
        )
    return resolved_seeds, audit_rows


def build_manual_event_rows(seed: dict) -> list[dict]:
    start = parse_date(seed["start_date"])
    peak = parse_date(seed["peak_date"])
    end = parse_date(seed["end_date"])
    baseline = float(seed["baseline_probability"])
    peak_probability = float(seed["peak_probability"])
    tail = float(seed["tail_probability"])
    rows: list[dict] = []

    for current in date_range(start, end):
        if current <= peak:
            total_days = max((peak - start).days, 1)
            progress = (current - start).days / total_days
            probability = baseline + (peak_probability - baseline) * smoothstep(progress)
        else:
            total_days = max((end - peak).days, 1)
            progress = (current - peak).days / total_days
            probability = peak_probability + (tail - peak_probability) * smoothstep(progress)
        rows.append(
            {
                "date": format_date(current),
                "event_id": seed["event_id"],
                "question": seed["question"],
                "source": seed["source"],
                "category": seed["category"],
                "probability": round(float(probability), 6),
                "resolution_date": seed["resolution_date"],
                "resolved_outcome": seed["resolved_outcome"],
                "provenance": seed["provenance"],
                "analysis_bucket": seed["analysis_bucket"],
                "event_date": seed["event_date"],
                "source_brier": 0.25
            }
        )
    return rows


def build_manifold_event_rows(config: dict, seed: dict, raw_dir: Path, refresh: bool = False) -> list[dict]:
    market = fetch_manifold_market(seed["market_id"], raw_dir, refresh=refresh)
    bets = fetch_manifold_bets(seed["market_id"], raw_dir, refresh=refresh)
    sample_start = parse_date(config["sample"]["start"])
    sample_end = parse_date(config["sample"]["end"])
    created = epoch_millis_to_date(int(market["createdTime"]))
    close_or_resolution = epoch_millis_to_date(
        int(market.get("resolutionTime") or market.get("closeTime") or market["createdTime"])
    )
    start = max(sample_start, created)
    end = min(sample_end, close_or_resolution)
    if not bets or start > end:
        return []

    running_probability = float(bets[0].get("probBefore", bets[0].get("probAfter", 0.5)))
    bet_index = 0
    while bet_index < len(bets) and epoch_millis_to_date(int(bets[bet_index]["createdTime"])) < start:
        running_probability = float(bets[bet_index].get("probAfter", running_probability))
        bet_index += 1

    rows: list[dict] = []
    current = start
    while current <= end:
        while bet_index < len(bets) and epoch_millis_to_date(int(bets[bet_index]["createdTime"])) == current:
            running_probability = float(bets[bet_index].get("probAfter", running_probability))
            bet_index += 1
        rows.append(
            {
                "date": format_date(current),
                "event_id": seed["event_id"],
                "question": market["question"],
                "source": "Manifold",
                "category": seed["category"],
                "probability": round(float(running_probability), 6),
                "resolution_date": seed["resolution_date"],
                "resolved_outcome": seed["resolved_outcome"],
                "provenance": seed["provenance"],
                "analysis_bucket": seed["analysis_bucket"],
                "event_date": seed["event_date"],
                "source_brier": float(config["cassandra"]["source_brier_scores"]["Manifold"])
            }
        )
        current += timedelta(days=1)
    return rows


def collect_search_terms(seed: dict) -> list[str]:
    terms = list(seed.get("manifold_search_terms", []))
    if seed.get("search_term") and seed["search_term"] not in terms:
        terms.append(seed["search_term"])
    return terms


def collect_manifold_candidates(search_terms: list[str], raw_dir: Path, refresh: bool = False) -> dict[str, dict]:
    hits: dict[str, dict] = {}
    for term in search_terms:
        results = fetch_manifold_search_markets(term, raw_dir, refresh=refresh)
        for rank, market in enumerate(results, start=1):
            hit = hits.setdefault(
                market["id"],
                {
                    "market": market,
                    "matched_terms": [],
                    "best_rank": rank,
                },
            )
            if term not in hit["matched_terms"]:
                hit["matched_terms"].append(term)
            hit["best_rank"] = min(hit["best_rank"], rank)
    return hits


def build_search_audit_row(
    seed: dict,
    search_terms: list[str],
    search_hits: dict[str, dict],
    selected_market_id: str | None,
    selected_hit: dict | None,
    replacement_status: str,
    selection_reason: str,
    pre_event_match: bool,
) -> dict:
    candidate_ids = sorted(
        search_hits.items(),
        key=lambda item: (item[1]["best_rank"], item[1]["market"]["createdTime"]),
    )
    top_candidates = []
    for market_id, hit in candidate_ids[:5]:
        market = hit["market"]
        created_date = format_date(epoch_millis_to_date(int(market["createdTime"])))
        top_candidates.append(f"{market_id}:{created_date}:{market['question']}")

    selected_created_date = None
    selected_question = None
    if selected_hit is not None:
        selected_created_date = format_date(epoch_millis_to_date(int(selected_hit["market"]["createdTime"])))
        selected_question = selected_hit["market"]["question"]

    return {
        "event_id": seed["event_id"],
        "category": seed["category"],
        "original_source": seed["source"],
        "search_terms": " | ".join(search_terms),
        "candidate_count": len(search_hits),
        "top_candidates": " || ".join(top_candidates),
        "selected_market_id": selected_market_id,
        "selected_question": selected_question,
        "selected_created_date": selected_created_date,
        "pre_event_match": pre_event_match,
        "replacement_status": replacement_status,
        "selection_reason": selection_reason,
    }


def aggregate_daily_probabilities(rows: list[dict]) -> dict[str, dict[str, dict]]:
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["date"]][row["event_id"]].append(row)

    daily: dict[str, dict[str, dict]] = {}
    for day, events in grouped.items():
        daily[day] = {}
        for event_id, event_rows in events.items():
            numerator = 0.0
            denominator = 0.0
            for row in event_rows:
                brier = max(float(row.get("source_brier", 0.25)), 1e-6)
                weight = 1.0 / brier
                numerator += weight * float(row["probability"])
                denominator += weight
            template = event_rows[0].copy()
            template["probability"] = numerator / denominator if denominator else 0.0
            daily[day][event_id] = template
    return daily


def build_event_metadata(rows: list[dict]) -> dict[str, dict]:
    metadata: dict[str, dict] = {}
    for row in rows:
        metadata.setdefault(
            row["event_id"],
            {
                "event_id": row["event_id"],
                "question": row["question"],
                "category": row["category"],
                "source": row["source"],
                "resolution_date": row["resolution_date"],
                "resolved_outcome": row["resolved_outcome"],
                "provenance": row["provenance"],
                "analysis_bucket": row["analysis_bucket"],
                "event_date": row["event_date"]
            }
        )
    return metadata
