from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from .clients import fetch_manifold_bets, fetch_manifold_market
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
