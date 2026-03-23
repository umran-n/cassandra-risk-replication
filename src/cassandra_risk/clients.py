from __future__ import annotations

import json
import csv
import hashlib
import io
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import ensure_dir, epoch_seconds, format_date, parse_date


USER_AGENT = "Mozilla/5.0 (compatible; Codex Cassandra-Risk Replication)"


def _fetch_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_spy_prices(config: dict, raw_dir: Path, refresh: bool = False) -> list[dict]:
    output_path = raw_dir / "spy_prices.json"
    if output_path.exists() and not refresh:
        with output_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    symbol = config["market_data"]["symbol"]
    start = parse_date(config["sample"]["start"])
    end = parse_date(config["sample"]["end"])
    period1 = epoch_seconds(start)
    period2 = epoch_seconds(end) + 86400
    url = config["market_data"]["chart_url_template"].format(
        symbol=symbol,
        period1=period1,
        period2=period2,
    )
    payload = _fetch_json(url)
    result = payload["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    adjclose = result["indicators"]["adjclose"][0]["adjclose"]
    rows: list[dict] = []
    for idx, timestamp in enumerate(timestamps):
        current = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        close = quote["close"][idx]
        adjusted = adjclose[idx]
        if close is None or adjusted is None:
            continue
        rows.append(
            {
                "date": format_date(current),
                "close": round(float(close), 6),
                "adjclose": round(float(adjusted), 6),
            }
        )
    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)
    return rows


def fetch_manifold_market(market_id: str, raw_dir: Path, refresh: bool = False) -> dict:
    output_path = raw_dir / f"manifold_market_{market_id}.json"
    if output_path.exists() and not refresh:
        with output_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    payload = _fetch_json(f"https://api.manifold.markets/v0/market/{market_id}")
    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return payload


def fetch_manifold_search_markets(
    term: str,
    raw_dir: Path,
    refresh: bool = False,
    limit: int = 10,
    sort: str = "score",
    contract_type: str = "BINARY",
) -> list[dict]:
    term_hash = hashlib.sha1(term.encode("utf-8")).hexdigest()[:12]
    output_path = raw_dir / f"manifold_search_{term_hash}.json"
    if output_path.exists() and not refresh:
        with output_path.open("r", encoding="utf-8") as handle:
            cached = json.load(handle)
        return list(cached.get("results", []))

    params = {
        "term": term,
        "sort": sort,
        "limit": str(limit),
        "contractType": contract_type,
    }
    url = "https://api.manifold.markets/v0/search-markets?" + urllib.parse.urlencode(params)
    payload = _fetch_json(url)
    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump({"term": term, "results": payload}, handle, indent=2)
    return list(payload)


def fetch_manifold_bets(market_id: str, raw_dir: Path, refresh: bool = False) -> list[dict]:
    output_path = raw_dir / f"manifold_bets_{market_id}.json"
    if output_path.exists() and not refresh:
        with output_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    payload: list[dict] = []
    after: str | None = None
    while True:
        params = {
            "contractId": market_id,
            "limit": "1000",
            "order": "asc",
        }
        if after:
            params["after"] = after
        url = "https://api.manifold.markets/v0/bets?" + urllib.parse.urlencode(params)
        page = list(_fetch_json(url))
        if not page:
            break
        payload.extend(page)
        if len(page) < 1000:
            break
        after = str(page[-1]["id"])

    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return payload


def fetch_fred_tb3ms(raw_dir: Path, refresh: bool = False) -> list[dict]:
    output_path = raw_dir / "fred_tb3ms.json"
    if output_path.exists() and not refresh:
        with output_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    request = urllib.request.Request(
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=TB3MS",
        headers={"User-Agent": USER_AGENT, "Accept": "text/csv"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")

    rows = []
    for row in csv.DictReader(io.StringIO(body)):
        value = row.get("TB3MS", ".")
        if not value or value == ".":
            continue
        rows.append({"date": row["DATE"], "annual_rate": float(value) / 100.0})

    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)
    return rows
