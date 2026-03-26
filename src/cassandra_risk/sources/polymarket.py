from __future__ import annotations

import json
from pathlib import Path

from ..polymarket import infer_theme_and_category
from ..signal_contract import DefaultContractNormaliser
from ..signal_types import SourceMarket
from .base import (
    adapter_credentials_state,
    cache_json,
    day_string,
    fetch_json,
    generic_quality_score,
    normalize_tokens,
    query_url,
    safe_float,
    status_record,
)


def fetch_polymarket_catalog(settings: dict, raw_dir: Path, limit: int | None = None, refresh: bool = False) -> tuple[list[dict], dict]:
    requested = int(limit or settings.get("default_limit", 200))
    cache_path = raw_dir / "signal_polymarket_catalog.json"
    has_credentials, notes = adapter_credentials_state(settings)

    try:
        if cache_path.exists() and not refresh:
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        else:
            url = query_url(
                str(settings["api_base_url"]),
                "/events",
                {"active": "true", "closed": "false", "order": "volume24hr", "ascending": "false", "limit": requested},
            )
            payload = fetch_json(url)
            cache_json(cache_path, payload)
    except Exception as error:
        status = status_record("polymarket", settings, reachable=False, has_credentials=has_credentials, notes=str(error))
        return [], status.to_dict()

    normaliser = DefaultContractNormaliser()
    markets = []
    source_priority = int(settings.get("priority", 999))
    for event in list(payload):
        event_title = str(event.get("title") or "")
        event_category = event.get("category")
        for item in list(event.get("markets", [])):
            outcomes = item.get("outcomes")
            if outcomes is None:
                continue
            title = str(item.get("question") or item.get("title") or event_title).strip()
            if not title:
                continue
            theme, category, raw_category, confidence = infer_theme_and_category(event_category, title, event_title)
            if theme == "noise":
                continue
            probability = safe_float(item.get("probability"))
            if probability is None:
                probability = safe_float(item.get("lastTradePrice"))
            if probability is None:
                try:
                    outcome_prices = json.loads(str(item.get("outcomePrices") or "[]"))
                    probability = safe_float(outcome_prices[0]) if outcome_prices else None
                except (json.JSONDecodeError, IndexError, TypeError):
                    probability = None
            volume = safe_float(item.get("volume")) or safe_float(event.get("volume"))
            liquidity = safe_float(item.get("liquidity")) or safe_float(event.get("liquidity"))
            market = SourceMarket(
                source="polymarket",
                market_id=str(item.get("id") or item.get("marketId") or ""),
                title=title,
                url=f"https://polymarket.com/event/{event.get('slug')}" if event.get("slug") else "",
                status="open" if bool(item.get("active", True)) and not bool(item.get("closed", False)) else "resolved",
                outcome_type="BINARY",
                structural_theme=theme,
                category=category,
                current_probability=probability,
                volume_usd=volume,
                liquidity_usd=liquidity,
                open_time=day_string(item.get("startDateIso") or item.get("startDate") or event.get("startDate")),
                close_time=day_string(item.get("endDateIso") or item.get("endDate") or event.get("endDate")),
                resolution_time=day_string(item.get("closedTime")),
                raw_category=raw_category,
                source_priority=source_priority,
                link_key=" ".join(sorted(normalize_tokens(title))),
                metadata={
                    "event_slug": event.get("slug"),
                    "slug": item.get("slug"),
                    "clob_token_ids": item.get("clobTokenIds"),
                },
            )
            market.quality_score = generic_quality_score(
                theme_confidence=confidence,
                volume_usd=market.volume_usd,
                liquidity_usd=market.liquidity_usd,
                probability=market.current_probability,
                source_priority=source_priority,
            )
            markets.append(normaliser.normalise(market))

    status = status_record(
        "polymarket",
        settings,
        reachable=True,
        has_credentials=has_credentials,
        notes=notes or "Public live catalog fetched from Gamma /events ordered by 24h volume.",
        market_count=len(markets),
    )
    return markets, status.to_dict()
