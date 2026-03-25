from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .utils import ensure_dir


KEEP_ISRAEL_TITLES = {
    "Israel x Hezbollah Ceasefire in 2024?",
    "Will Israel invade Syria in 2024?",
    "Israel x Hamas ceasefire in 2024?",
    "Another Iran strike on Israel in October?",
    "Israel military action against Iran by end of 2024?",
}

ISRAEL_ARC_PATTERNS = (
    "israel",
    "hezbollah",
    "hamas",
    "lebanon",
    "iran",
    "gaza",
)


MANUAL_METACULUS_EVENTS = [
    {
        "event_id": "metaculus_debt_ceiling_2023",
        "title": "US debt ceiling resolution risk in 2023",
        "theme": "fiscal_debt",
        "resolution_date": "2023-06-01",
        "peak_probability": None,
        "total_volume_usd": None,
        "approval_status": "APPROVED",
        "approval_reason": "Manual Metaculus fiscal-debt anchor requested for 2023 debt-ceiling coverage.",
        "proxy_family_id": "metaculus_debt_ceiling_2023",
        "source": "metaculus",
    },
    {
        "event_id": "metaculus_debt_default_risk_2023",
        "title": "US debt default risk in 2023",
        "theme": "fiscal_debt",
        "resolution_date": "2023-06-30",
        "peak_probability": None,
        "total_volume_usd": None,
        "approval_status": "APPROVED",
        "approval_reason": "Manual Metaculus fiscal-debt anchor requested for debt-default risk monitoring.",
        "proxy_family_id": "metaculus_debt_default_risk_2023",
        "source": "metaculus",
    },
    {
        "event_id": "metaculus_government_shutdown_2025",
        "title": "US government shutdown risk in 2025",
        "theme": "fiscal_debt",
        "resolution_date": "2025-12-31",
        "peak_probability": None,
        "total_volume_usd": None,
        "approval_status": "APPROVED",
        "approval_reason": "Manual Metaculus fiscal-debt anchor requested for 2025 shutdown coverage.",
        "proxy_family_id": "metaculus_government_shutdown_2025",
        "source": "metaculus",
    },
    {
        "event_id": "metaculus_eu_ai_act_enforcement_2024",
        "title": "EU AI Act enforcement in 2024",
        "theme": "trade_technology",
        "resolution_date": "2024-08-01",
        "peak_probability": None,
        "total_volume_usd": None,
        "approval_status": "APPROVED",
        "approval_reason": "Manual Metaculus trade-technology anchor requested for EU AI Act enforcement coverage.",
        "proxy_family_id": "metaculus_eu_ai_act_enforcement_2024",
        "source": "metaculus",
    },
    {
        "event_id": "metaculus_sec_crypto_action_2024",
        "title": "SEC crypto enforcement action in 2024",
        "theme": "trade_technology",
        "resolution_date": "2024-12-31",
        "peak_probability": None,
        "total_volume_usd": None,
        "approval_status": "APPROVED",
        "approval_reason": "Manual Metaculus trade-technology anchor requested for US crypto-regulatory enforcement coverage.",
        "proxy_family_id": "metaculus_sec_crypto_action_2024",
        "source": "metaculus",
    },
    {
        "event_id": "metaculus_svb_contagion_2023",
        "title": "SVB contagion risk in 2023",
        "theme": "systemic_credit",
        "resolution_date": "2023-03-31",
        "peak_probability": None,
        "total_volume_usd": None,
        "approval_status": "APPROVED",
        "approval_reason": "Manual Metaculus systemic-credit anchor added to restore theme balance and land the final universe inside the 38-42 target range.",
        "proxy_family_id": "metaculus_svb_contagion_2023",
        "source": "metaculus",
    },
]


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    text = re.sub(r"_+", "_", text)
    return text[:80]


def normalize_title(value: str) -> str:
    return " ".join((value or "").split())


def load_curated_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def is_israel_arc_row(row: dict[str, str]) -> bool:
    if row.get("theme") != "geopolitical":
        return False
    title = normalize_title(row.get("title", "")).lower()
    return any(pattern in title for pattern in ISRAEL_ARC_PATTERNS)


def apply_israel_arc_cap(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    kept: list[dict[str, str]] = []
    dropped: list[dict[str, str]] = []
    for row in rows:
        normalized = normalize_title(row.get("title", ""))
        row = dict(row)
        row["title"] = normalized
        if is_israel_arc_row(row) and normalized not in KEEP_ISRAEL_TITLES:
            dropped.append(row)
            continue
        kept.append(row)
    return kept, dropped


def to_float(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def approval_reason(row: dict[str, str]) -> str:
    title = normalize_title(row.get("title", ""))
    theme = row.get("theme", "")
    if title in KEEP_ISRAEL_TITLES:
        return "Retained under the Israel-arc cap as one of five anchor geopolitical contracts."
    if theme == "monetary_policy":
        return "Approved from the final curated Polymarket universe for liquid macro-policy coverage."
    if theme == "electoral":
        return "Approved from the final curated Polymarket universe as a capped electoral governance signal."
    if theme == "fiscal_debt":
        return "Approved from the final curated Polymarket universe for fiscal-debt stress coverage."
    if theme == "trade_technology":
        return "Approved from the final curated Polymarket universe for trade-technology regime coverage."
    return "Approved from the final curated Polymarket universe after Phase 5 manual review."


def polymarket_event_id(row: dict[str, str]) -> str:
    title = normalize_title(row.get("title", ""))
    theme = row.get("theme", "")
    resolution_date = str(row.get("resolution_date", ""))
    year = resolution_date[:4] if resolution_date else "na"
    return f"{theme}_{slugify(title)}_{year}"


def build_polymarket_approved(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    approved: list[dict[str, Any]] = []
    for row in rows:
        title = normalize_title(row.get("title", ""))
        theme = row.get("theme", "")
        event_id = polymarket_event_id(row)
        approved.append(
            {
                "event_id": event_id,
                "title": title,
                "theme": theme,
                "resolution_date": row.get("resolution_date", ""),
                "peak_probability": to_float(row.get("peak_probability")),
                "total_volume_usd": to_float(row.get("total_volume_usd")),
                "approval_status": "APPROVED",
                "approval_reason": approval_reason(row),
                "proxy_family_id": f"polymarket_{event_id}",
                "source": "polymarket",
            }
        )
    return approved


def build_final_universe(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    capped_rows, dropped_rows = apply_israel_arc_cap(rows)
    approved = build_polymarket_approved(capped_rows)
    approved.extend(MANUAL_METACULUS_EVENTS)
    approved.sort(key=lambda row: (str(row["theme"]), str(row["source"]), str(row["resolution_date"]), str(row["title"])))
    return approved, dropped_rows


def write_approved_json(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def build_universe_summary(
    *,
    source_rows: list[dict[str, str]],
    approved_rows: list[dict[str, Any]],
    dropped_rows: list[dict[str, str]],
) -> str:
    source_theme_counts = Counter(row.get("theme") for row in source_rows)
    approved_theme_counts = Counter(str(row.get("theme")) for row in approved_rows)
    source_counts = Counter(str(row.get("source")) for row in approved_rows)

    lines = [
        "# Phase 5 Final Universe Summary",
        "",
        f"- Source curated rows loaded: `{len(source_rows)}`",
        f"- Rows dropped by Israel-arc cap: `{len(dropped_rows)}`",
        f"- Manual Metaculus additions: `{len(MANUAL_METACULUS_EVENTS)}`",
        f"- Final approved universe size: `{len(approved_rows)}`",
        "",
        "## Assumptions",
        "",
        "- Added one manual Metaculus `systemic_credit` anchor (`SVB contagion risk in 2023`) to restore theme coverage and bring the final approved universe into the requested 38-42 range.",
        "",
        "## Theme Counts",
        "",
        "| Theme | Source CSV | Final Approved |",
        "| --- | ---: | ---: |",
    ]

    all_themes = sorted(set(source_theme_counts) | set(approved_theme_counts))
    for theme in all_themes:
        lines.append(f"| {theme} | {source_theme_counts.get(theme, 0)} | {approved_theme_counts.get(theme, 0)} |")

    lines.extend(
        [
            "",
            "## Source Counts",
            "",
            "| Source | Count |",
            "| --- | ---: |",
        ]
    )
    for source, count in sorted(source_counts.items()):
        lines.append(f"| {source} | {count} |")

    lines.extend(
        [
            "",
            "## Retained Israel-Arc Anchors",
            "",
        ]
    )
    for title in sorted(KEEP_ISRAEL_TITLES):
        lines.append(f"- {title}")

    lines.extend(
        [
            "",
            "## Dropped Israel-Arc Variants",
            "",
        ]
    )
    for row in dropped_rows:
        lines.append(f"- {normalize_title(row.get('title', ''))}")

    return "\n".join(lines) + "\n"


def write_universe_summary(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
