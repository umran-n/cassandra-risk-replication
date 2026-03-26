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


def fetch_kalshi_catalog(settings: dict, raw_dir: Path, limit: int | None = None, refresh: bool = False) -> tuple[list[dict], dict]:
    requested = int(limit or settings.get("default_limit", 200))
    cache_path = raw_dir / "signal_kalshi_catalog.json"
    has_credentials, notes = adapter_credentials_state(settings)

    try:
        if cache_path.exists() and not refresh:
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        else:
            url = query_url(
                str(settings["api_base_url"]),
                "/events",
                {"status": "open", "limit": requested, "with_nested_markets": "true"},
            )
            payload = fetch_json(url)
            cache_json(cache_path, payload)
    except Exception as error:
        status = status_record("kalshi", settings, reachable=False, has_credentials=has_credentials, notes=str(error))
        return [], status.to_dict()

    source_priority = int(settings.get("priority", 999))
    rows = []
    for event in list(payload.get("events", [])):
        event_title = str(event.get("title") or "")
        event_subtitle = str(event.get("sub_title") or "")
        event_category = str(event.get("category") or "")
        for market in list(event.get("markets", [])):
            item = dict(market)
            item["_event_title"] = event_title
            item["_event_subtitle"] = event_subtitle
            item["_event_category"] = event_category
            rows.append(item)
    normaliser = DefaultContractNormaliser()
    markets = []
    for item in rows:
        market_type = str(item.get("market_type") or item.get("marketType") or "binary").lower()
        if "binary" not in market_type:
            continue
        title = str(item.get("title") or item.get("_event_title") or "").strip()
        if not title:
            continue
        theme, category, raw_category, confidence = infer_theme_and_category(item.get("_event_category"), title, item.get("subtitle") or item.get("_event_subtitle"))
        if theme == "noise":
            continue
        yes_price = safe_float(item.get("yes_price")) or safe_float(item.get("yes_bid_dollars")) or safe_float(item.get("last_price_dollars"))
        if yes_price is None:
            yes_price = safe_float(item.get("last_price"))
        probability = None if yes_price is None else yes_price / 100.0 if yes_price > 1.0 else yes_price
        volume = safe_float(item.get("volume")) or safe_float(item.get("volume_fp"))
        liquidity = safe_float(item.get("open_interest")) or safe_float(item.get("open_interest_fp")) or safe_float(item.get("liquidity_dollars"))
        ticker = str(item.get("ticker") or "")
        market = SourceMarket(
            source="kalshi",
            market_id=ticker,
            title=title,
            url=f"https://kalshi.com/markets/{ticker}" if ticker else "",
            status=str(item.get("status") or "open").lower(),
            outcome_type="BINARY",
            structural_theme=theme,
            category=category,
            current_probability=probability,
            volume_usd=volume,
            liquidity_usd=liquidity,
            open_time=day_string(item.get("open_time")),
            close_time=day_string(item.get("close_time") or item.get("expiration_time")),
            resolution_time=day_string(item.get("expiration_time")),
            raw_category=raw_category,
            source_priority=source_priority,
            link_key=" ".join(sorted(normalize_tokens(title, item.get("subtitle")))),
            metadata={
                "event_ticker": item.get("event_ticker"),
                "subtitle": item.get("subtitle"),
                "series_ticker": item.get("series_ticker"),
                "event_category": item.get("_event_category"),
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
        "kalshi",
        settings,
        reachable=True,
        has_credentials=has_credentials,
        notes=notes or "Public live catalog fetched from Kalshi /trade-api/v2/events with nested markets.",
        market_count=len(markets),
    )
    return markets, status.to_dict()
