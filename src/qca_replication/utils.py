from __future__ import annotations

import csv
import json
import math
import re
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha1
from html import unescape
from pathlib import Path
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DATE_FMT = "%Y-%m-%d"
UTC = timezone.utc
try:
    EASTERN = ZoneInfo("America/New_York")
except ZoneInfoNotFoundError:
    EASTERN = timezone(timedelta(hours=-5))

MONEY_RE = re.compile(
    r"\$?\s*(\d+(?:\.\d+)?)\s*(trillion|billion|million|thousand|tn|bn|b|m|k)?",
    re.IGNORECASE,
)
DIVIDEND_RE = re.compile(
    r"\$?\s*(\d+(?:\.\d+)?)\s*(?:per\s+share|/share)",
    re.IGNORECASE,
)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FMT).date()


def format_date(value: date) -> str:
    return value.strftime(DATE_FMT)


def parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def epoch_seconds(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp())


def ensure_json_serializable(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return format_date(value)
    if isinstance(value, list):
        return [ensure_json_serializable(item) for item in value]
    if isinstance(value, dict):
        return {key: ensure_json_serializable(item) for key, item in value.items()}
    return value


def write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(ensure_json_serializable(payload), handle, indent=2)


def write_csv(path: Path, rows: Sequence[dict]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    normalized_rows: list[dict] = []
    for row in rows:
        normalized = {}
        for key, value in row.items():
            if key not in fieldnames:
                fieldnames.append(key)
            if isinstance(value, (list, dict)):
                normalized[key] = json.dumps(ensure_json_serializable(value))
            elif isinstance(value, (datetime, date, Path)):
                normalized[key] = ensure_json_serializable(value)
            else:
                normalized[key] = value
        normalized_rows.append(normalized)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(normalized_rows)


def mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def stddev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    variance = sum((value - mu) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(variance, 0.0))


def percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = max(0.0, min(1.0, q)) * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def tanh_score(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.5
    return clamp(0.5 + 0.5 * math.tanh(value / scale), 0.0, 1.0)


def correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mean_x = mean(xs)
    mean_y = mean(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return 0.0
    return clamp(num / (den_x * den_y), -1.0, 1.0)


def rolling_std(values: Sequence[float]) -> float:
    return stddev(values)


def strip_html(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def hash_key(value: str) -> str:
    return sha1(value.encode("utf-8")).hexdigest()


def parse_money_token(number: str, suffix: str | None) -> float:
    amount = float(number)
    suffix = (suffix or "").lower()
    if suffix in {"trillion", "tn"}:
        return amount * 1_000_000_000_000.0
    if suffix in {"billion", "bn", "b"}:
        return amount * 1_000_000_000.0
    if suffix in {"million", "m"}:
        return amount * 1_000_000.0
    if suffix in {"thousand", "k"}:
        return amount * 1_000.0
    return amount


def extract_contextual_money(text: str, keywords: Sequence[str]) -> float | None:
    lowered = text.lower()
    best_value: float | None = None
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword.lower()), lowered):
            start = max(0, match.start() - 120)
            end = min(len(text), match.end() + 120)
            window = text[start:end]
            for money in MONEY_RE.finditer(window):
                value = parse_money_token(money.group(1), money.group(2))
                if value >= 1_000_000:
                    best_value = max(best_value or 0.0, value)
    return best_value


def extract_dividend_per_share(text: str) -> float | None:
    match = DIVIDEND_RE.search(text)
    if not match:
        return None
    return float(match.group(1))


def annualize_volatility(returns: Sequence[float], trading_days: int = 252) -> float:
    return stddev(returns) * math.sqrt(trading_days)


def closest_previous_date(values: Sequence[date], target: date) -> date | None:
    candidates = [value for value in values if value <= target]
    if not candidates:
        return None
    return max(candidates)


def closest_next_date(values: Sequence[date], target: date) -> date | None:
    candidates = [value for value in values if value >= target]
    if not candidates:
        return None
    return min(candidates)


def map_announcement_to_t0(announcement_ts: datetime, trading_dates: Sequence[date]) -> date | None:
    if announcement_ts.tzinfo is None:
        announcement_ts = announcement_ts.replace(tzinfo=UTC)
    local = announcement_ts.astimezone(EASTERN)
    trading_set = set(trading_dates)
    current_day = local.date()
    if current_day not in trading_set:
        return closest_next_date(trading_dates, current_day)
    if local.time() >= time(16, 0):
        next_day = current_day + timedelta(days=1)
        return closest_next_date(trading_dates, next_day)
    return current_day


def serialize_list(value: Sequence[object]) -> str:
    return json.dumps(ensure_json_serializable(list(value)))
