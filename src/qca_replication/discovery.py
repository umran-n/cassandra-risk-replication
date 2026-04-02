from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .clients import (
    build_sec_document_url,
    fetch_sec_document,
    fetch_sec_filing_index,
    fetch_sec_submissions,
)
from .config import load_json
from .utils import (
    clamp,
    extract_contextual_money,
    extract_dividend_per_share,
    format_date,
    normalize_whitespace,
    parse_date,
    parse_datetime,
    strip_html,
)


EX99_RE = re.compile(r"(?:^|[^a-z])(?:ex[-_ ]?99|99(?:\.|_|-)?1)(?:[^a-z]|$)", re.IGNORECASE)


def _firm_lookup(config: dict) -> dict[str, dict]:
    return {item["ticker"]: item for item in config["firms"]}


def _sample_window(config: dict) -> tuple[str, str]:
    return config["sample"]["start"], config["sample"]["end"]


def expand_submission_rows(payloads: Iterable[dict], allowed_forms: set[str], start: str, end: str) -> list[dict]:
    rows: list[dict] = []
    for payload in payloads:
        recent = payload.get("filings", {}).get("recent", {})
        filing_dates = recent.get("filingDate", [])
        total = len(filing_dates)
        for idx in range(total):
            form = recent.get("form", [None])[idx]
            filing_date = filing_dates[idx]
            if form not in allowed_forms or filing_date < start or filing_date > end:
                continue
            rows.append(
                {
                    "accession_number": recent.get("accessionNumber", [None])[idx],
                    "filing_date": filing_date,
                    "acceptance_datetime": recent.get("acceptanceDateTime", [None])[idx],
                    "primary_document": recent.get("primaryDocument", [None])[idx],
                    "primary_doc_description": recent.get("primaryDocDescription", [None])[idx],
                    "form": form,
                    "report_date": recent.get("reportDate", [None])[idx],
                }
            )
    deduped: dict[str, dict] = {}
    for row in rows:
        accession = row["accession_number"]
        if accession and accession not in deduped:
            deduped[accession] = row
    return sorted(deduped.values(), key=lambda item: (item["filing_date"], item["accession_number"]))


def _document_priority(name: str, primary_document: str) -> tuple[int, str]:
    lowered = name.lower()
    if lowered == primary_document.lower():
        return (2, lowered)
    if EX99_RE.search(lowered):
        return (0, lowered)
    return (1, lowered)


def fetch_filing_text_bundle(
    cik: str,
    filing_row: dict,
    raw_dir: Path,
    user_agent: str,
    refresh: bool = False,
) -> list[dict]:
    accession = filing_row["accession_number"]
    try:
        index_payload = fetch_sec_filing_index(cik, accession, raw_dir, user_agent, refresh=refresh)
    except Exception:
        return []
    documents = index_payload.get("directory", {}).get("item", [])
    primary_document = filing_row["primary_document"] or ""
    selected_names: list[str] = []
    for item in sorted(documents, key=lambda entry: _document_priority(entry.get("name", ""), primary_document)):
        name = item.get("name", "")
        if not name.endswith((".htm", ".html", ".txt")):
            continue
        if name in selected_names:
            continue
        if len(selected_names) >= 3:
            break
        if EX99_RE.search(name.lower()) or name.lower() == primary_document.lower():
            selected_names.append(name)
    if primary_document and primary_document not in selected_names:
        selected_names.append(primary_document)

    bundle: list[dict] = []
    for name in selected_names:
        url = build_sec_document_url(cik, accession, name)
        try:
            text = fetch_sec_document(url, raw_dir, user_agent, refresh=refresh)
        except Exception:
            continue
        source_type = "ir_press_release" if EX99_RE.search(name.lower()) else "sec_primary_filing"
        bundle.append(
            {
                "name": name,
                "url": url,
                "source_type": source_type,
                "text": strip_html(text),
            }
        )
    return bundle


def classify_filing_event(ticker: str, firm_config: dict, filing_row: dict, text_bundle: list[dict], keyword_groups: dict) -> dict | None:
    combined_text = " ".join(item["text"] for item in text_bundle if item["text"])
    lowered = combined_text.lower()
    if not lowered:
        return None

    match_counts = {
        name: sum(lowered.count(keyword.lower()) for keyword in keywords)
        for name, keywords in keyword_groups.items()
    }
    authorization_amount = extract_contextual_money(combined_text, keyword_groups.get("buyback", []))
    dividend_per_share = extract_dividend_per_share(combined_text)

    if ticker == "AMZN" and match_counts.get("internal_reallocation", 0) > 0:
        event_family = "internal_reallocation"
    else:
        buyback = match_counts.get("buyback", 0) > 0 or authorization_amount is not None
        dividend = match_counts.get("dividend", 0) > 0 or dividend_per_share is not None
        split = match_counts.get("split", 0) > 0
        if buyback and dividend:
            event_family = "dual_announcement"
        elif buyback:
            event_family = "buyback_authorization"
        elif dividend:
            event_family = "dividend_announcement"
        elif split:
            event_family = "signal_reset"
        else:
            return None

    score = 0
    if authorization_amount is not None:
        score += 4
    if dividend_per_share is not None:
        score += 2
    score += match_counts.get("buyback", 0) * 2
    score += match_counts.get("dividend", 0) * 2
    score += match_counts.get("split", 0)
    score += match_counts.get("internal_reallocation", 0) * 2
    if any(item["source_type"] == "ir_press_release" for item in text_bundle):
        score += 1

    raw_title = next((item["text"][:180] for item in text_bundle if item["text"]), filing_row["primary_doc_description"] or filing_row["form"])
    event_title = normalize_whitespace(raw_title)[:180]
    announcement_ts = filing_row["acceptance_datetime"]
    if announcement_ts:
        announcement_dt = parse_datetime(announcement_ts)
    else:
        fallback = f"{filing_row['filing_date']}T20:05:00+00:00"
        announcement_dt = parse_datetime(fallback)

    return {
        "event_id": f"{ticker}-{filing_row['filing_date'].replace('-', '')}-{event_family}",
        "ticker": ticker,
        "company_name": firm_config["name"],
        "firm": ticker,
        "archetype": firm_config["archetype"],
        "event_family": event_family,
        "particle_variant": firm_config["particle_variant"],
        "announcement_date": filing_row["filing_date"],
        "announcement_ts": announcement_dt.isoformat(),
        "source_urls": [item["url"] for item in text_bundle],
        "event_title": event_title,
        "authorization_amount": authorization_amount,
        "dividend_per_share": dividend_per_share,
        "data_tier": "public_proxy",
        "reconstruction_status": "auto_discovered",
        "exclusion_reason": "",
        "discovery_score": score,
        "matched_keywords": {name: count for name, count in match_counts.items() if count > 0},
        "filing_form": filing_row["form"],
        "filing_accession": filing_row["accession_number"],
    }


def _merge_manual_event(row: dict, manual_event: dict) -> dict:
    merged = dict(row)
    if manual_event.get("event_title"):
        merged["event_title"] = manual_event["event_title"]
    if manual_event.get("event_family"):
        merged["event_family"] = manual_event["event_family"]
    if manual_event.get("authorization_amount") is not None:
        merged["authorization_amount"] = manual_event["authorization_amount"]
    if manual_event.get("dividend_per_share") is not None:
        merged["dividend_per_share"] = manual_event["dividend_per_share"]
    if manual_event.get("manual_source_urls"):
        merged["source_urls"] = manual_event["manual_source_urls"]
    merged["reconstruction_status"] = "manual_enriched"
    return merged


def apply_manual_overlay(candidates: list[dict], config: dict) -> tuple[list[dict], list[dict]]:
    overlay_path = Path(config["discovery"]["manual_overlay_path"])
    overlay = load_json(overlay_path)
    manual_events = overlay.get("manual_events", [])
    exclusions = {
        (item["ticker"], item["announcement_date"]): item.get("reason", "manual_exclusion")
        for item in overlay.get("exclusions", [])
    }

    by_key: dict[tuple[str, str], dict] = {}
    for row in candidates:
        key = (row["ticker"], row["announcement_date"])
        existing = by_key.get(key)
        if existing is None or row["discovery_score"] > existing["discovery_score"]:
            by_key[key] = row

    for manual in manual_events:
        key = (manual["ticker"], manual["announcement_date"])
        if key in by_key:
            by_key[key] = _merge_manual_event(by_key[key], manual)
            continue
        firm = _firm_lookup(config)[manual["ticker"]]
        fallback_ts = f"{manual['announcement_date']}T20:05:00+00:00"
        by_key[key] = {
            "event_id": f"{manual['ticker']}-{manual['announcement_date'].replace('-', '')}-{manual['event_family']}",
            "ticker": manual["ticker"],
            "company_name": firm["name"],
            "firm": manual["ticker"],
            "archetype": firm["archetype"],
            "event_family": manual["event_family"],
            "particle_variant": firm["particle_variant"],
            "announcement_date": manual["announcement_date"],
            "announcement_ts": fallback_ts,
            "source_urls": manual.get("manual_source_urls", []),
            "event_title": manual.get("event_title", manual["event_family"].replace("_", " ").title()),
            "authorization_amount": manual.get("authorization_amount"),
            "dividend_per_share": manual.get("dividend_per_share"),
            "data_tier": "public_proxy",
            "reconstruction_status": "manual_seed",
            "exclusion_reason": "",
            "discovery_score": 100,
            "matched_keywords": {"manual_seed": 1},
            "filing_form": "MANUAL",
            "filing_accession": "",
        }

    selected: list[dict] = []
    gap_rows: list[dict] = []
    by_ticker: dict[str, list[dict]] = {}
    for row in by_key.values():
        key = (row["ticker"], row["announcement_date"])
        if key in exclusions:
            row["exclusion_reason"] = exclusions[key]
            continue
        by_ticker.setdefault(row["ticker"], []).append(row)

    firms = _firm_lookup(config)
    for ticker, firm in firms.items():
        target_count = int(firm["target_count"])
        rows = sorted(
            by_ticker.get(ticker, []),
            key=lambda item: (
                0 if item["reconstruction_status"].startswith("manual") else 1,
                -item.get("discovery_score", 0),
                item["announcement_date"],
            ),
        )
        kept = rows[:target_count]
        kept = sorted(kept, key=lambda item: item["announcement_date"])
        selected.extend(kept)
        achieved = len(kept)
        gap_rows.append(
            {
                "ticker": ticker,
                "company_name": firm["name"],
                "target_count": target_count,
                "achieved_count": achieved,
                "gap": max(target_count - achieved, 0),
                "overflow": max(achieved - target_count, 0),
                "data_tier": "public_proxy",
            }
        )
    return selected, gap_rows


def build_event_ledger(config: dict, raw_dir: Path, refresh: bool = False) -> tuple[list[dict], list[dict]]:
    user_agent = config["sec"]["user_agent"]
    start, end = _sample_window(config)
    allowed_forms = set(config["discovery"]["forms"])
    keyword_groups = config["discovery"]["keyword_groups"]
    selection_threshold = int(config["discovery"]["selection_score_threshold"])
    candidates: list[dict] = []

    for firm in config["firms"]:
        try:
            submissions = fetch_sec_submissions(firm["cik"], raw_dir, user_agent, refresh=refresh)
        except Exception:
            continue
        filing_rows = expand_submission_rows(submissions, allowed_forms, start, end)
        for filing_row in filing_rows:
            text_bundle = fetch_filing_text_bundle(firm["cik"], filing_row, raw_dir, user_agent, refresh=refresh)
            if not text_bundle:
                continue
            candidate = classify_filing_event(
                firm["ticker"],
                firm,
                filing_row,
                text_bundle,
                keyword_groups,
            )
            if candidate is None or candidate["discovery_score"] < selection_threshold:
                continue
            candidates.append(candidate)

    return apply_manual_overlay(candidates, config)
