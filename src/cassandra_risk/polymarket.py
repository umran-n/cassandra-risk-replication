from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .clients import fetch_polymarket_events_page, fetch_polymarket_price_history
from .taxonomy import VALID_STRUCTURAL_THEMES
from .utils import ensure_dir, format_date


NOISE_CATEGORIES = {
    "",
    "none",
    "sports",
    "nba",
    "nfl",
    "mlb",
    "nhl",
    "soccer",
    "champions league",
    "pop culture",
    "entertainment",
    "gaming",
    "weather",
}

KEYWORDS = {
    "geopolitical": {
        "war", "invasion", "invade", "ukraine", "russia", "taiwan", "china", "israel",
        "iran", "gaza", "military", "missile", "conflict", "strait", "ceasefire", "nato",
    },
    "monetary_policy": {
        "fed", "fomc", "rate", "rates", "hike", "cut", "inflation", "yield", "treasury",
        "ecb", "recession", "higher", "longer", "soft landing", "cpi",
    },
    "fiscal_debt": {
        "debt", "ceiling", "default", "shutdown", "sovereign", "downgrade", "budget",
        "deficit", "treasury", "x-date", "rating",
    },
    "electoral": {
        "election", "elections", "vote", "voter", "nominee", "president", "senate",
        "house", "parliament", "prime minister", "pm", "polling", "ballot",
    },
    "systemic_credit": {
        "bank", "banking", "credit", "svb", "credit suisse", "contagion", "liquidity",
        "bailout", "collapse", "crisis", "run", "deposit", "commercial real estate",
    },
    "trade_technology": {
        "tariff", "trade", "sanction", "export", "import", "chip", "chips",
        "semiconductor", "ai", "artificial intelligence", "tiktok", "regulation",
        "export control", "technology", "tech",
    },
}

POSITIVE_OUTCOME_LABELS = {
    "yes", "over", "higher", "increase", "pass", "win", "up",
}

NEGATIVE_OUTCOME_LABELS = {
    "no", "under", "lower", "decrease", "fail", "lose", "down",
}

RAW_CATEGORY_THEME_HINTS = {
    "politics": {"electoral", "fiscal_debt"},
    "world": {"geopolitical"},
    "business": {"monetary_policy", "systemic_credit", "trade_technology", "fiscal_debt"},
    "economy": {"monetary_policy", "fiscal_debt", "systemic_credit"},
    "crypto": {"trade_technology"},
    "technology": {"trade_technology"},
}


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = str(value).strip().replace("Z", "+00:00")
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def jsonish_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value).strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    if isinstance(payload, list):
        return [str(item) for item in payload]
    return [str(payload)]


def tokenize_text(*values: str | None) -> set[str]:
    text = " ".join(value or "" for value in values).lower()
    tokens: set[str] = set()
    current = []
    for char in text:
        if char.isalnum():
            current.append(char)
        else:
            if current:
                tokens.add("".join(current))
                current.clear()
    if current:
        tokens.add("".join(current))
    return tokens


def infer_theme_and_category(raw_category: str | None, question: str, event_title: str | None) -> tuple[str, str, str, float]:
    raw_lower = (raw_category or "").strip().lower()
    tokens = tokenize_text(question, event_title, raw_category)

    theme_scores: dict[str, float] = defaultdict(float)
    for theme, keywords in KEYWORDS.items():
        score = float(len(tokens & keywords))
        if raw_lower in RAW_CATEGORY_THEME_HINTS and theme in RAW_CATEGORY_THEME_HINTS[raw_lower]:
            score += 0.5
        theme_scores[theme] = score

    best_theme = max(theme_scores, key=theme_scores.get)
    best_score = theme_scores[best_theme]
    if raw_lower in NOISE_CATEGORIES and best_score < 2.0:
        return "noise", "Noise", raw_lower or "noise", 0.0
    if best_score <= 0.0:
        return "noise", "Noise", raw_lower or "noise", 0.0

    if best_theme == "geopolitical":
        category = "Kinetic"
    elif best_theme == "monetary_policy":
        category = "Monetary"
    elif best_theme in {"fiscal_debt", "electoral", "systemic_credit"}:
        category = "Sovereign"
    else:
        tech_hits = len(tokens & {"technology", "tech", "chip", "chips", "semiconductor", "ai"})
        trade_hits = len(tokens & {"tariff", "trade", "sanction", "export", "import"})
        category = "Technology" if tech_hits > trade_hits else "Trade"

    confidence = min(best_score / 4.0, 1.0)
    return best_theme, category, raw_lower or "unknown", confidence


def choose_probability_token(market: dict) -> tuple[str | None, str | None, list[str], list[str]]:
    outcomes = jsonish_list(market.get("outcomes"))
    token_ids = jsonish_list(market.get("clobTokenIds"))
    if len(outcomes) != 2 or len(token_ids) != 2:
        return None, None, outcomes, token_ids

    normalized_outcomes = [label.strip().lower() for label in outcomes]
    if normalized_outcomes[0] in POSITIVE_OUTCOME_LABELS:
        return token_ids[0], outcomes[0], outcomes, token_ids
    if normalized_outcomes[1] in POSITIVE_OUTCOME_LABELS:
        return token_ids[1], outcomes[1], outcomes, token_ids
    if normalized_outcomes[0] in NEGATIVE_OUTCOME_LABELS:
        return token_ids[1], outcomes[1], outcomes, token_ids
    if normalized_outcomes[1] in NEGATIVE_OUTCOME_LABELS:
        return token_ids[0], outcomes[0], outcomes, token_ids
    return token_ids[0], outcomes[0], outcomes, token_ids


def parse_resolution_value(market: dict, positive_label: str | None, outcomes: list[str]) -> tuple[str | None, float | None]:
    prices = []
    for value in jsonish_list(market.get("outcomePrices")):
        try:
            prices.append(float(value))
        except ValueError:
            prices.append(0.0)
    if not prices or len(prices) != len(outcomes):
        return None, None

    winning_index = max(range(len(prices)), key=lambda index: prices[index])
    resolved_value = outcomes[winning_index]
    if positive_label is None:
        return resolved_value, None
    positive_index = outcomes.index(positive_label)
    resolved_yes_value = 1.0 if winning_index == positive_index else 0.0
    return resolved_value, resolved_yes_value


def select_history_fidelities(days_to_resolution: int) -> list[int]:
    if days_to_resolution <= 7:
        return [1, 5, 15, 60]
    if days_to_resolution <= 30:
        return [60, 15, 240]
    if days_to_resolution <= 90:
        return [240, 60, 1440]
    return [1440, 240, 60]


def compress_history_daily(history: list[dict]) -> list[dict]:
    by_day: dict[str, float] = {}
    for point in history:
        timestamp = int(point["t"])
        current_day = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        by_day[format_date(current_day)] = round(float(point["p"]), 6)
    return [{"date": day, "probability": by_day[day]} for day in sorted(by_day)]


def informative_probability_stats(history: list[dict]) -> tuple[bool, int, float | None, float | None]:
    if not history:
        return False, 0, None, None
    probabilities = [float(point["probability"]) for point in history]
    informative_points = sum(1 for value in probabilities if 0.15 <= value <= 0.85)
    return informative_points > 0, informative_points, min(probabilities), max(probabilities)


def quality_score(
    *,
    category_confidence: float,
    informative_share: float,
    movement: float,
    history_density: float,
    volume: float,
    liquidity: float,
) -> float:
    volume_score = min(math.log10(volume + 1.0) / 6.0, 1.0)
    liquidity_score = min(math.log10(liquidity + 1.0) / 6.0, 1.0)
    return round(
        0.20 * category_confidence
        + 0.25 * informative_share
        + 0.20 * movement
        + 0.15 * history_density
        + 0.10 * volume_score
        + 0.10 * liquidity_score,
        6,
    )


def record_fetch_error(errors: list[dict[str, str]], stage: str, identifier: str, error: Exception) -> None:
    errors.append(
        {
            "stage": stage,
            "identifier": identifier,
            "error_type": error.__class__.__name__,
            "message": str(error),
        }
    )


def iterate_resolved_events(
    raw_dir: Path,
    start_date: datetime,
    end_date: datetime,
    refresh: bool = False,
    page_size: int = 100,
    errors: list[dict[str, str]] | None = None,
) -> list[dict]:
    events: list[dict] = []
    offset = 0
    while True:
        try:
            page = fetch_polymarket_events_page(
                raw_dir,
                refresh=refresh,
                limit=page_size,
                offset=offset,
                closed=True,
                active=False,
                order="closedTime",
                ascending=True,
            )
        except Exception as error:  # pragma: no cover - exercised via live network calls
            if errors is not None:
                record_fetch_error(errors, "events_page", f"offset={offset}", error)
            offset += page_size
            continue
        if not page:
            break

        stop = False
        for event in page:
            closed_dt = parse_iso_datetime(event.get("closedTime") or event.get("endDate"))
            if closed_dt is None:
                continue
            if closed_dt < start_date:
                continue
            if closed_dt > end_date:
                stop = True
                break
            events.append(event)
        if stop:
            break
        offset += page_size
    return events


def flatten_event_markets(events: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for event in events:
        event_title = event.get("title")
        event_slug = event.get("slug")
        event_category = event.get("category")
        event_closed_dt = parse_iso_datetime(event.get("closedTime") or event.get("endDate"))
        for market in event.get("markets", []):
            row = dict(market)
            row["_event_title"] = event_title
            row["_event_slug"] = event_slug
            row["_event_category"] = event_category
            row["_event_closed_dt"] = event_closed_dt.isoformat() if event_closed_dt else None
            rows.append(row)
    return rows


def build_polymarket_candidates(
    sample_start: str,
    sample_end: str,
    raw_dir: Path,
    refresh: bool = False,
) -> tuple[list[dict], dict, list[dict[str, str]]]:
    start_dt = datetime.fromisoformat(f"{sample_start}T00:00:00+00:00")
    end_dt = datetime.fromisoformat(f"{sample_end}T23:59:59+00:00")
    errors: list[dict[str, str]] = []
    events = iterate_resolved_events(raw_dir, start_dt, end_dt, refresh=refresh, errors=errors)
    markets = flatten_event_markets(events)

    eligible: list[dict] = []
    counts = {
        "event_count": len(events),
        "market_count": len(markets),
        "non_noise_market_count": 0,
        "time_gate_pass_count": 0,
        "probability_gate_pass_count": 0,
        "eligible_count": 0,
        "assumption_probability_gate": "interpreted as 0.15 <= P <= 0.85 for at least one history point",
    }

    for market in markets:
        question = str(market.get("question") or "")
        event_title = str(market.get("_event_title") or "")
        raw_category = market.get("category") or market.get("_event_category")
        structural_theme, category, raw_category_label, category_confidence = infer_theme_and_category(
            raw_category,
            question,
            event_title,
        )
        gate_category_pass = structural_theme != "noise"
        if gate_category_pass:
            counts["non_noise_market_count"] += 1

        created_dt = parse_iso_datetime(market.get("createdAt") or market.get("startDate"))
        resolution_dt = parse_iso_datetime(
            market.get("closedTime")
            or market.get("endDate")
            or market.get("_event_closed_dt")
        )
        if created_dt is None or resolution_dt is None:
            continue

        days_to_resolution = max((resolution_dt.date() - created_dt.date()).days, 0)
        gate_time_pass = days_to_resolution <= 180
        if gate_time_pass:
            counts["time_gate_pass_count"] += 1

        token_id, probability_label, outcomes, token_ids = choose_probability_token(market)
        if token_id is None:
            continue

        history_points: list[dict] = []
        fidelity_used = None
        if gate_category_pass and gate_time_pass:
            for fidelity in select_history_fidelities(days_to_resolution):
                try:
                    raw_history = fetch_polymarket_price_history(token_id, raw_dir, refresh=refresh, fidelity=fidelity)
                except Exception as error:  # pragma: no cover - exercised via live network calls
                    record_fetch_error(errors, "price_history", f"market_id={market.get('id')};token_id={token_id};fidelity={fidelity}", error)
                    continue
                if raw_history:
                    history_points = compress_history_daily(raw_history)
                    fidelity_used = fidelity
                    break

        gate_probability_pass, informative_points, min_probability, max_probability = informative_probability_stats(history_points)
        if gate_probability_pass:
            counts["probability_gate_pass_count"] += 1

        if not (gate_category_pass and gate_time_pass and gate_probability_pass):
            continue

        counts["eligible_count"] += 1
        resolved_value, resolved_yes_value = parse_resolution_value(market, probability_label, outcomes)
        movement = 0.0 if min_probability is None or max_probability is None else min((max_probability - min_probability) / 0.70, 1.0)
        informative_share = informative_points / max(len(history_points), 1)
        history_density = min(len(history_points) / max(days_to_resolution, 1), 1.0)
        volume = float(market.get("volumeNum") or market.get("volume") or 0.0)
        liquidity = float(market.get("liquidityNum") or market.get("liquidity") or 0.0)
        candidate_quality = quality_score(
            category_confidence=category_confidence,
            informative_share=informative_share,
            movement=movement,
            history_density=history_density,
            volume=volume,
            liquidity=liquidity,
        )

        candidate = {
            "market_id": str(market.get("id")),
            "source": "Polymarket",
            "question": question,
            "title": question,
            "event_title": event_title,
            "slug": market.get("slug"),
            "event_slug": market.get("_event_slug"),
            "category": category,
            "original_category": raw_category_label,
            "structural_theme": structural_theme if structural_theme in VALID_STRUCTURAL_THEMES else None,
            "event_id": None,
            "event_date": None,
            "resolution_date": format_date(resolution_dt.date()),
            "resolved_value": resolved_value,
            "resolved_outcome": resolved_yes_value,
            "probability_label": probability_label,
            "probability_timeseries": history_points,
            "probability_timeseries_fidelity": fidelity_used,
            "peak_probability": max_probability,
            "min_probability": min_probability,
            "informative_probability_points": informative_points,
            "days_to_resolution": days_to_resolution,
            "gate_probability_pass": gate_probability_pass,
            "gate_horizon_pass": gate_time_pass,
            "gate_category_pass": gate_category_pass,
            "eligible": True,
            "analysis_bucket": None,
            "provenance": "polymarket_historical_candidate",
            "proxy_family_id": f"polymarket_{market.get('id')}",
            "proxy_relation": "substitute",
            "aggregation_policy": "weighted_average",
            "event_window_start": format_date(created_dt.date()),
            "event_window_end": format_date(resolution_dt.date()),
            "quality_score": candidate_quality,
            "category_confidence": round(category_confidence, 6),
            "history_point_count": len(history_points),
            "binary_market": len(token_ids) == 2,
            "outcomes": outcomes,
            "clob_token_ids": token_ids,
            "yes_token_id": token_id,
            "volume": volume,
            "liquidity": liquidity,
            "notes": (
                "Phase 5 historical Polymarket candidate. Probability gate interpreted as "
                "0.15 <= P <= 0.85 for at least one history point."
            ),
        }
        eligible.append(candidate)

    eligible.sort(key=lambda row: (-float(row["quality_score"]), row["resolution_date"], row["market_id"]))
    return eligible, counts, errors


def write_polymarket_candidates(path: Path, payload: list[dict]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_fetch_errors(path: Path, errors: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    if not errors:
        path.write_text("No fetch errors encountered.\n", encoding="utf-8")
        return
    lines = []
    for error in errors:
        lines.append(
            "[{stage}] {identifier} :: {error_type}: {message}".format(
                stage=error.get("stage", "unknown"),
                identifier=error.get("identifier", "unknown"),
                error_type=error.get("error_type", "Exception"),
                message=error.get("message", ""),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def theme_counts(candidates: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for candidate in candidates:
        theme = candidate.get("structural_theme") or "unclassified"
        counts[str(theme)] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def build_fetch_summary_markdown(
    *,
    sample_start: str,
    sample_end: str,
    summary: dict[str, Any],
    candidates: list[dict],
    errors: list[dict[str, Any]],
) -> str:
    lines = [
        "# Phase 5a Polymarket Historical Ingestion",
        "",
        f"- Sample window: `{sample_start}` to `{sample_end}`",
        f"- Events scanned: `{summary['event_count']}`",
        f"- Markets scanned: `{summary['market_count']}`",
        f"- Category gate pass (`category != noise`): `{summary['non_noise_market_count']}`",
        f"- Horizon gate pass (`days_to_resolution <= 180`): `{summary['time_gate_pass_count']}`",
        f"- Probability gate pass: `{summary['probability_gate_pass_count']}`",
        f"- Eligible candidates written: `{summary['eligible_count']}`",
        f"- Fetch errors logged: `{len(errors)}`",
        "",
        "## Gate Assumption",
        "",
        f"- Probability gate interpreted as: `{summary['assumption_probability_gate']}`",
        "",
        "## Structural Theme Counts",
        "",
    ]

    for theme, count in theme_counts(candidates).items():
        lines.append(f"- `{theme}`: `{count}`")

    lines.extend(
        [
            "",
            "## Top 10 Candidates by Quality Score",
            "",
            "| Rank | market_id | structural_theme | category | quality_score | question |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for index, candidate in enumerate(candidates[:10], start=1):
        question = str(candidate.get("question", "")).replace("|", "\\|")
        lines.append(
            f"| {index} | `{candidate['market_id']}` | `{candidate.get('structural_theme')}` | "
            f"`{candidate.get('category')}` | {float(candidate.get('quality_score', 0.0)):.6f} | {question} |"
        )

    return "\n".join(lines) + "\n"
