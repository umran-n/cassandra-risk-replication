from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import ensure_dir, epoch_seconds, format_date, hash_key, parse_date


DEFAULT_TIMEOUT = 30


def _headers(user_agent: str, accept: str) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept": accept,
    }


def _cache_path(base_dir: Path, cache_key: str, suffix: str) -> Path:
    ensure_dir(base_dir)
    return base_dir / f"{hash_key(cache_key)}{suffix}"


def _fetch_bytes(
    url: str,
    cache_dir: Path,
    user_agent: str,
    accept: str,
    refresh: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> bytes:
    cache_path = _cache_path(cache_dir, url, ".bin")
    if cache_path.exists() and not refresh:
        return cache_path.read_bytes()
    request = urllib.request.Request(url, headers=_headers(user_agent, accept))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    ensure_dir(cache_path.parent)
    cache_path.write_bytes(payload)
    time.sleep(0.1)
    return payload


def fetch_json_url(url: str, cache_dir: Path, user_agent: str, refresh: bool = False) -> Any:
    payload = _fetch_bytes(url, cache_dir, user_agent, "application/json", refresh=refresh)
    return json.loads(payload.decode("utf-8"))


def fetch_text_url(url: str, cache_dir: Path, user_agent: str, refresh: bool = False) -> str:
    payload = _fetch_bytes(url, cache_dir, user_agent, "text/html, text/plain, application/json", refresh=refresh)
    return payload.decode("utf-8", "ignore")


def build_sec_document_url(cik: str, accession: str, filename: str) -> str:
    cik_number = str(int(cik))
    accession_digits = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_number}/{accession_digits}/{filename}"


def fetch_sec_submissions(cik: str, raw_dir: Path, user_agent: str, refresh: bool = False) -> list[dict]:
    base_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    payload = fetch_json_url(base_url, raw_dir / "sec" / "submissions", user_agent, refresh=refresh)
    payloads = [payload]
    for item in payload.get("filings", {}).get("files", []):
        older_url = f"https://data.sec.gov/submissions/{item['name']}"
        try:
            payloads.append(fetch_json_url(older_url, raw_dir / "sec" / "submissions", user_agent, refresh=refresh))
        except urllib.error.HTTPError:
            continue
    return payloads


def fetch_sec_company_facts(cik: str, raw_dir: Path, user_agent: str, refresh: bool = False) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    return fetch_json_url(url, raw_dir / "sec" / "companyfacts", user_agent, refresh=refresh)


def fetch_sec_filing_index(cik: str, accession: str, raw_dir: Path, user_agent: str, refresh: bool = False) -> dict:
    cik_number = str(int(cik))
    accession_digits = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_number}/{accession_digits}/index.json"
    return fetch_json_url(url, raw_dir / "sec" / "filing_index", user_agent, refresh=refresh)


def fetch_sec_document(url: str, raw_dir: Path, user_agent: str, refresh: bool = False) -> str:
    return fetch_text_url(url, raw_dir / "sec" / "documents", user_agent, refresh=refresh)


def fetch_yahoo_chart(symbol: str, start: str, end: str, raw_dir: Path, chart_url_template: str, refresh: bool = False) -> dict:
    start_date = parse_date(start)
    end_date = parse_date(end)
    period1 = epoch_seconds(start_date)
    period2 = epoch_seconds(end_date) + 86400
    url = chart_url_template.format(
        symbol=urllib.parse.quote(symbol),
        period1=period1,
        period2=period2,
    )
    payload = fetch_json_url(url, raw_dir / "yahoo" / "charts", "Mozilla/5.0 (compatible; QCA Replication)", refresh=refresh)
    result = payload["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    adjclose_values = result.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
    rows: list[dict] = []
    for idx, timestamp in enumerate(timestamps):
        current = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        close = quote.get("close", [None])[idx]
        adjclose = adjclose_values[idx] if idx < len(adjclose_values) else close
        if close is None or adjclose is None:
            continue
        rows.append(
            {
                "date": format_date(current),
                "close": float(close),
                "adjclose": float(adjclose),
            }
        )

    dividend_rows: list[dict] = []
    for item in (result.get("events", {}) or {}).get("dividends", {}).values():
        amount = item.get("amount")
        timestamp = item.get("date")
        if amount is None or timestamp is None:
            continue
        current = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        dividend_rows.append({"date": format_date(current), "amount": float(amount)})

    split_rows: list[dict] = []
    for item in (result.get("events", {}) or {}).get("splits", {}).values():
        timestamp = item.get("date")
        if timestamp is None:
            continue
        current = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        split_rows.append(
            {
                "date": format_date(current),
                "numerator": item.get("numerator"),
                "denominator": item.get("denominator"),
                "split_ratio": item.get("splitRatio"),
            }
        )
    return {"rows": rows, "dividends": dividend_rows, "splits": split_rows}


def fetch_yahoo_options_chain(symbol: str, expiry_epoch: int, raw_dir: Path, options_url_template: str, refresh: bool = False) -> dict | None:
    url = options_url_template.format(symbol=urllib.parse.quote(symbol), expiry_epoch=expiry_epoch)
    try:
        return fetch_json_url(url, raw_dir / "yahoo" / "options", "Mozilla/5.0 (compatible; QCA Replication)", refresh=refresh)
    except urllib.error.HTTPError:
        return None
