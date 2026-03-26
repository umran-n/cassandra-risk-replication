from __future__ import annotations

import json
import os
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


def extract_probability(post: dict) -> float | None:
    aggregations = post.get("question", {}).get("aggregations") or post.get("aggregations") or {}
    for key in ("recency_weighted", "latest", "community_prediction", "prediction"):
        value = aggregations.get(key)
        if isinstance(value, dict):
            center = value.get("center") or value.get("median") or value.get("mean")
            numeric = safe_float(center)
            if numeric is not None:
                if numeric > 1.0:
                    return numeric / 100.0
                return numeric
        numeric = safe_float(value)
        if numeric is not None:
            if numeric > 1.0:
                return numeric / 100.0
            return numeric
    return None


def fetch_metaculus_catalog(settings: dict, raw_dir: Path, limit: int | None = None, refresh: bool = False) -> tuple[list[dict], dict]:
    requested = int(limit or settings.get("default_limit", 100))
    cache_path = raw_dir / "signal_metaculus_catalog.json"
    has_credentials, notes = adapter_credentials_state(settings)
    if not has_credentials:
        status = status_record("metaculus", settings, reachable=False, has_credentials=False, notes=notes)
        return [], status.to_dict()

    token = os.environ.get(str(settings.get("token_env_var")), "").strip()
    headers = {"Authorization": f"Token {token}"}

    try:
        if cache_path.exists() and not refresh:
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        else:
            url = query_url(
                str(settings["api_base_url"]),
                "/posts/",
                {"limit": requested},
            )
            payload = fetch_json(url, headers=headers)
            cache_json(cache_path, payload)
    except Exception as error:
        status = status_record("metaculus", settings, reachable=False, has_credentials=True, notes=str(error))
        return [], status.to_dict()

    rows = list(payload.get("results", payload if isinstance(payload, list) else []))
    source_priority = int(settings.get("priority", 999))
    normaliser = DefaultContractNormaliser()
    markets = []
    for item in rows:
        question = item.get("question") or {}
        title = str(item.get("title") or question.get("title") or "").strip()
        if not title:
            continue
        theme, category, raw_category, confidence = infer_theme_and_category(item.get("category"), title, item.get("description"))
        if theme == "noise":
            continue
        probability = extract_probability(item)
        post_id = str(item.get("id") or question.get("id") or "")
        market = SourceMarket(
            source="metaculus",
            market_id=post_id,
            title=title,
            url=f"https://www.metaculus.com/posts/{post_id}/" if post_id else "",
            status="open",
            outcome_type="BINARY",
            structural_theme=theme,
            category=category,
            current_probability=probability,
            volume_usd=None,
            liquidity_usd=None,
            close_time=day_string(question.get("close_time") or item.get("close_time")),
            resolution_time=day_string(question.get("resolve_time") or item.get("resolve_time")),
            raw_category=raw_category,
            source_priority=source_priority,
            link_key=" ".join(sorted(normalize_tokens(title, item.get("description")))),
            metadata={
                "question_id": question.get("id"),
                "status": question.get("status"),
            },
        )
        market.quality_score = generic_quality_score(
            theme_confidence=confidence,
            volume_usd=None,
            liquidity_usd=None,
            probability=market.current_probability,
            source_priority=source_priority,
        )
        markets.append(normaliser.normalise(market))

    status = status_record(
        "metaculus",
        settings,
        reachable=True,
        has_credentials=True,
        notes="Authenticated feed fetched from /api/posts/.",
        market_count=len(markets),
    )
    return markets, status.to_dict()
