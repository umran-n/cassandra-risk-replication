from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..signal_types import SourceStatus
from ..source_registry import source_has_credentials
from ..utils import ensure_dir


USER_AGENT = "Mozilla/5.0 (compatible; Codex Cassandra Unified Signal API)"

STOPWORDS = {
    "a", "an", "and", "are", "be", "before", "by", "for", "from", "in", "is", "of", "on",
    "or", "the", "to", "will", "with", "after", "over", "under", "at", "than", "this",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> Any:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def cache_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def normalize_tokens(*values: str | None) -> set[str]:
    joined = " ".join(value or "" for value in values).lower()
    cleaned = []
    current = []
    for char in joined:
        if char.isalnum():
            current.append(char)
        else:
            if current:
                cleaned.append("".join(current))
                current.clear()
    if current:
        cleaned.append("".join(current))
    return {token for token in cleaned if token not in STOPWORDS and len(token) > 2}


def jaccard_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def query_url(base_url: str, path: str, params: dict[str, Any] | None = None) -> str:
    encoded = "" if not params else "?" + urllib.parse.urlencode(params)
    return base_url.rstrip("/") + path + encoded


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def iso_from_epoch_ms(value: Any) -> str | None:
    numeric = safe_float(value)
    if numeric is None:
        return None
    return datetime.fromtimestamp(numeric / 1000.0, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def day_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    numeric = safe_float(value)
    if numeric is not None and len(str(int(numeric))) >= 10:
        return datetime.fromtimestamp(numeric / 1000.0 if numeric > 10_000_000_000 else numeric, tz=timezone.utc).date().isoformat()
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date().isoformat()


def generic_quality_score(
    *,
    theme_confidence: float,
    volume_usd: float | None,
    liquidity_usd: float | None,
    probability: float | None,
    source_priority: int,
) -> float:
    volume_component = 0.0 if volume_usd is None else min(1.0, max(0.0, (volume_usd / 1_000_000.0)))
    liquidity_component = 0.0 if liquidity_usd is None else min(1.0, max(0.0, (liquidity_usd / 500_000.0)))
    probability_component = 0.0
    if probability is not None:
        probability_component = 1.0 - min(abs(probability - 0.5) * 2.0, 1.0)
    priority_component = max(0.0, 1.0 - ((source_priority - 1) * 0.15))
    return round(
        0.35 * theme_confidence
        + 0.25 * volume_component
        + 0.15 * liquidity_component
        + 0.15 * probability_component
        + 0.10 * priority_component,
        6,
    )


def status_record(source: str, settings: dict, *, reachable: bool, has_credentials: bool, notes: str, market_count: int = 0) -> SourceStatus:
    return SourceStatus(
        source=source,
        display_name=str(settings.get("display_name", source.title())),
        enabled=bool(settings.get("enabled", True)),
        has_credentials=has_credentials,
        reachable=reachable,
        auth_mode=str(settings.get("auth_mode", "public")),
        quality_tier=str(settings.get("quality_tier", "")),
        role=str(settings.get("role", "")),
        notes=notes,
        market_count=market_count,
        fetched_at=utc_now_iso(),
    )


def adapter_credentials_state(settings: dict) -> tuple[bool, str]:
    has_credentials = source_has_credentials(settings)
    if has_credentials:
        return True, ""
    token_env = str(settings.get("token_env_var", ""))
    return False, f"Missing credentials in env var {token_env}."
