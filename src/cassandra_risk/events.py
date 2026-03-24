from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from .clients import fetch_manifold_bets, fetch_manifold_market, fetch_manifold_search_markets
from .utils import date_range, epoch_millis_to_date, format_date, parse_date, smoothstep


def normalize_proxy_metadata(seed: dict) -> dict:
    normalized = seed.copy()
    normalized["proxy_family_id"] = normalized.get("proxy_family_id") or normalized["event_id"]
    normalized["proxy_relation"] = normalized.get("proxy_relation") or "substitute"
    normalized["aggregation_policy"] = normalized.get("aggregation_policy") or ""
    normalized["event_window_start"] = (
        normalized.get("event_window_start")
        or normalized.get("start_date")
        or normalized.get("event_date")
    )
    normalized["event_window_end"] = (
        normalized.get("event_window_end")
        or normalized.get("end_date")
        or normalized.get("event_date")
    )
    default_quality = 0.5 if normalized.get("source") == "Manual" else 1.0
    normalized["quality_score"] = float(normalized.get("quality_score", default_quality))
    normalized["market_id"] = normalized.get("market_id")
    return normalized


def build_event_panel(config: dict, seeds: list[dict], raw_dir: Path, refresh: bool = False) -> list[dict]:
    rows: list[dict] = []
    for seed in seeds:
        seed = normalize_proxy_metadata(seed)
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
    return [normalize_proxy_metadata(entry) for entry in payload]


def merge_seeds_with_shortlist(seeds: list[dict], shortlist: list[dict]) -> tuple[list[dict], list[dict]]:
    seeds_by_event: dict[str, dict] = {seed["event_id"]: seed.copy() for seed in seeds}
    shortlist_by_event: dict[str, list[dict]] = defaultdict(list)
    for entry in shortlist:
        shortlist_by_event[entry["event_id"]].append(entry.copy())

    merged_rows: list[dict] = []
    merge_audit: list[dict] = []
    base_event_ids = set(seeds_by_event)

    for event_id, seed in sorted(seeds_by_event.items()):
        approved_entries = shortlist_by_event.get(event_id, [])
        if not approved_entries:
            merged_rows.append(seed.copy())
            merge_audit.append(
                {
                    "event_id": event_id,
                    "merge_action": "manual_retained",
                    "source": seed["source"],
                    "market_id": seed.get("market_id"),
                    "selection_reason": "No approved curated shortlist entry for this event.",
                }
            )
            continue

        for index, entry in enumerate(approved_entries):
            merged_rows.append(entry.copy())
            merge_audit.append(
                {
                    "event_id": event_id,
                    "merge_action": "replaced_existing_event" if index == 0 else "added_parallel_proxy",
                    "source": entry["source"],
                    "market_id": entry.get("market_id"),
                    "selection_reason": entry.get("selection_reason", "Approved curated shortlist entry."),
                }
            )

    for event_id, approved_entries in sorted(shortlist_by_event.items()):
        if event_id in base_event_ids:
            continue
        for index, entry in enumerate(approved_entries):
            merged_rows.append(entry.copy())
            merge_audit.append(
                {
                    "event_id": event_id,
                    "merge_action": "added_curated_event" if index == 0 else "added_parallel_proxy",
                    "source": entry["source"],
                    "market_id": entry.get("market_id"),
                    "selection_reason": entry.get("selection_reason", "Approved curated shortlist entry."),
                }
            )

    merged_rows.sort(key=lambda item: (item["event_id"], item.get("market_id") or "", item["source"]))
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
                "source_brier": 0.25,
                "market_id": seed.get("market_id"),
                "proxy_family_id": seed["proxy_family_id"],
                "proxy_relation": seed["proxy_relation"],
                "aggregation_policy": seed["aggregation_policy"],
                "event_window_start": seed["event_window_start"],
                "event_window_end": seed["event_window_end"],
                "quality_score": seed["quality_score"],
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
                "source_brier": float(config["cassandra"]["source_brier_scores"]["Manifold"]),
                "market_id": seed.get("market_id"),
                "proxy_family_id": seed["proxy_family_id"],
                "proxy_relation": seed["proxy_relation"],
                "aggregation_policy": seed["aggregation_policy"],
                "event_window_start": seed["event_window_start"],
                "event_window_end": seed["event_window_end"],
                "quality_score": seed["quality_score"],
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


def resolve_proxy_aggregation_policy(rows: list[dict], config: dict | None = None) -> str:
    explicit = {row["aggregation_policy"] for row in rows if row.get("aggregation_policy")}
    if len(explicit) > 1:
        raise ValueError(f"Conflicting aggregation policies for proxy family: {sorted(explicit)}")
    if explicit:
        return next(iter(explicit))

    config = config or {}
    cassandra = config.get("cassandra", {})
    global_default = cassandra.get("multi_proxy_aggregation", "weighted_average")
    if not any(row.get("proxy_relation") for row in rows):
        return global_default
    relation_defaults = cassandra.get(
        "proxy_relation_aggregation_defaults",
        {
            "orthogonal": "max",
            "nested": "weighted_average",
            "substitute": "weighted_average",
        },
    )
    proxy_relation = rows[0].get("proxy_relation") or "substitute"
    return relation_defaults.get(proxy_relation, global_default)


def aggregate_probability_rows(rows: list[dict], policy: str, level: str) -> dict:
    if policy == "max":
        dominant = max(
            rows,
            key=lambda row: (float(row["probability"]), float(row.get("quality_score", 0.0))),
        )
        template = dominant.copy()
        template["probability"] = max(float(row["probability"]) for row in rows)
    elif policy == "weighted_average":
        dominant = max(
            rows,
            key=lambda row: (float(row["probability"]), float(row.get("quality_score", 0.0))),
        )
        numerator = 0.0
        denominator = 0.0
        for row in rows:
            brier = max(float(row.get("source_brier", 0.25)), 1e-6)
            weight = 1.0 / brier
            numerator += weight * float(row["probability"])
            denominator += weight
        template = dominant.copy()
        template["probability"] = numerator / denominator if denominator else 0.0
    else:
        raise ValueError(f"Unsupported aggregation policy: {policy}")

    dominant = max(
        rows,
        key=lambda row: (float(row["probability"]), float(row.get("quality_score", 0.0))),
    )
    template[f"{level}_aggregation_policy"] = policy
    template[f"{level}_proxy_count"] = len(rows)
    template[f"{level}_quality_score"] = max(float(row.get("quality_score", 0.0)) for row in rows)
    template[f"dominant_{level}_market_id"] = dominant.get("market_id")
    template[f"dominant_{level}_question"] = dominant.get("question")
    template[f"dominant_{level}_probability"] = float(dominant["probability"])
    template[f"dominant_{level}_quality_score"] = float(dominant.get("quality_score", 0.0))
    template[f"{level}_market_ids"] = " | ".join(sorted(str(row.get("market_id") or "") for row in rows if row.get("market_id")))
    return template


def aggregate_daily_probabilities(rows: list[dict], config: dict | None = None) -> dict[str, dict[str, dict]]:
    grouped: dict[str, dict[str, dict[str, list[dict]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in rows:
        grouped[row["date"]][row["event_id"]][row.get("proxy_family_id") or row["event_id"]].append(row)

    daily: dict[str, dict[str, dict]] = {}
    for day, events in grouped.items():
        daily[day] = {}
        for event_id, family_groups in events.items():
            family_rows: list[dict] = []
            for proxy_family_id, proxy_rows in family_groups.items():
                family_policy = resolve_proxy_aggregation_policy(proxy_rows, config)
                aggregated_family = aggregate_probability_rows(proxy_rows, family_policy, "family")
                aggregated_family["proxy_family_id"] = proxy_family_id
                family_rows.append(aggregated_family)

            cassandra = (config or {}).get("cassandra", {})
            event_policy = cassandra.get("multi_family_aggregation", cassandra.get("multi_proxy_aggregation", "weighted_average"))
            aggregated_event = aggregate_probability_rows(family_rows, event_policy, "event")
            aggregated_event["proxy_family_count"] = len(family_rows)
            aggregated_event["family_rows"] = family_rows
            daily[day][event_id] = aggregated_event
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
                "event_date": row["event_date"],
                "proxy_family_id": row.get("proxy_family_id"),
                "proxy_relation": row.get("proxy_relation"),
                "aggregation_policy": row.get("aggregation_policy"),
                "event_window_start": row.get("event_window_start"),
                "event_window_end": row.get("event_window_end"),
                "quality_score": row.get("quality_score"),
            }
        )
    return metadata
