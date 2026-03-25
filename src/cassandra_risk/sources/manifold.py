from __future__ import annotations

import json
from pathlib import Path

from ..polymarket import infer_theme_and_category
from ..signal_types import SourceMarket
from .base import (
    adapter_credentials_state,
    cache_json,
    day_string,
    fetch_json,
    generic_quality_score,
    normalize_tokens,
    query_url,
    status_record,
)


def fetch_manifold_catalog(settings: dict, raw_dir: Path, limit: int | None = None, refresh: bool = False) -> tuple[list[dict], dict]:
    requested = int(limit or settings.get("default_limit", 200))
    cache_path = raw_dir / "signal_manifold_catalog.json"
    has_credentials, notes = adapter_credentials_state(settings)

    try:
        if cache_path.exists() and not refresh:
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        else:
            url = query_url(
                str(settings["api_base_url"]),
                "/markets",
                {"limit": requested, "sort": "last-bet-time", "order": "desc"},
            )
            payload = fetch_json(url)
            cache_json(cache_path, payload)
    except Exception as error:
        status = status_record("manifold", settings, reachable=False, has_credentials=has_credentials, notes=str(error))
        return [], status.to_dict()

    markets: list[dict] = []
    source_priority = int(settings.get("priority", 999))
    for item in list(payload):
        if str(item.get("outcomeType", "")).upper() != "BINARY":
            continue
        title = str(item.get("question") or "").strip()
        if not title:
            continue
        theme, category, raw_category, confidence = infer_theme_and_category("", title, None)
        if theme == "noise":
            continue
        probability = item.get("probability")
        volume = item.get("volume")
        liquidity = item.get("totalLiquidity")
        market = SourceMarket(
            source="manifold",
            market_id=str(item.get("id")),
            title=title,
            url=str(item.get("url") or ""),
            status="resolved" if bool(item.get("isResolved")) else "open",
            outcome_type="BINARY",
            structural_theme=theme,
            category=category,
            current_probability=float(probability) if probability is not None else None,
            volume_usd=float(volume) if volume is not None else None,
            liquidity_usd=float(liquidity) if liquidity is not None else None,
            open_time=day_string(item.get("createdTime")),
            close_time=day_string(item.get("closeTime")),
            resolution_time=day_string(item.get("resolutionTime")),
            raw_category=raw_category,
            source_priority=source_priority,
            link_key=" ".join(sorted(normalize_tokens(title))),
        )
        market.quality_score = generic_quality_score(
            theme_confidence=confidence,
            volume_usd=market.volume_usd,
            liquidity_usd=market.liquidity_usd,
            probability=market.current_probability,
            source_priority=source_priority,
        )
        markets.append(market.to_dict())

    status = status_record(
        "manifold",
        settings,
        reachable=True,
        has_credentials=has_credentials,
        notes=notes or "Public live catalog fetched from /v0/markets.",
        market_count=len(markets),
    )
    return markets, status.to_dict()
