from __future__ import annotations

import json
from pathlib import Path

from .final_curation import normalize_title, polymarket_event_id
from .utils import ensure_dir, write_csv


GEOPOLITICAL_EXPANSION_SELECTIONS = [
    {
        "market_id": "501863",
        "channel": "gaza_ceasefire_2024",
        "approval_reason": "Phase 5.6 targeted geopolitical expansion: add a high-volume Gaza ceasefire contract to broaden de-escalation coverage inside the 2024 conflict arc.",
    },
    {
        "market_id": "504664",
        "channel": "lebanon_escalation",
        "approval_reason": "Phase 5.6 targeted geopolitical expansion: add a Lebanon escalation contract to capture a distinct northern-front spillover channel.",
    },
    {
        "market_id": "511043",
        "channel": "israel_iran_escalation",
        "approval_reason": "Phase 5.6 targeted geopolitical expansion: add a high-volume Israel-Iran escalation contract to capture late-2024 strike follow-through risk.",
    },
    {
        "market_id": "507749",
        "channel": "us_iran_escalation",
        "approval_reason": "Phase 5.6 targeted geopolitical expansion: add a U.S.-Iran escalation contract to capture great-power intervention risk.",
    },
    {
        "market_id": "507115",
        "channel": "ukraine_ceasefire_2024",
        "approval_reason": "Phase 5.6 targeted geopolitical expansion: add a Russia-Ukraine ceasefire contract to capture de-escalation/endgame risk absent from the current approved set.",
    },
    {
        "market_id": "510132",
        "channel": "gaza_withdrawal_2024",
        "approval_reason": "Phase 5.6 targeted geopolitical expansion: add a Gaza withdrawal contract to capture military de-escalation and occupation unwind risk.",
    },
    {
        "market_id": "511520",
        "channel": "iran_retaliation",
        "approval_reason": "Phase 5.6 targeted geopolitical expansion: add an Iran retaliation contract to extend the October strike arc into late-2024 commodity and sanctions risk.",
    },
]


GEO_ADMISSION_POLICY = {
    "becker_correction": 0.0732,
    "longshot_threshold": (0.15, 0.85),
    "max_bucket_events": 8,
    "bucket_cap": 0.25,
    "min_volume_usd": 500000.0,
    "resolution_type": "binary",
    "macro_relevant": True,
}


def selected_market_ids() -> set[str]:
    return {item["market_id"] for item in GEOPOLITICAL_EXPANSION_SELECTIONS}


def build_geopolitical_expansion_rows(candidates: list[dict]) -> list[dict]:
    candidates_by_market_id = {str(candidate.get("market_id")): candidate for candidate in candidates}
    rows: list[dict] = []
    for selection in GEOPOLITICAL_EXPANSION_SELECTIONS:
        candidate = candidates_by_market_id.get(selection["market_id"])
        if candidate is None:
            raise KeyError(f"Selected geopolitical candidate not found: {selection['market_id']}")

        title = normalize_title(candidate.get("title") or candidate.get("question") or "")
        theme = candidate.get("structural_theme") or "geopolitical"
        resolution_date = str(candidate.get("resolution_date") or "")
        volume = float(candidate.get("volume") or 0.0)
        if volume < GEO_ADMISSION_POLICY["min_volume_usd"]:
            raise ValueError(f"Selected geopolitical candidate violates min_volume_usd policy: {selection['market_id']}")
        event_id = polymarket_event_id(
            {
                "title": title,
                "theme": theme,
                "resolution_date": resolution_date,
            }
        )
        rows.append(
            {
                "event_id": event_id,
                "title": title,
                "theme": theme,
                "resolution_date": resolution_date,
                "peak_probability": float(candidate.get("peak_probability") or 0.0),
                "total_volume_usd": volume,
                "approval_status": "APPROVED",
                "approval_reason": selection["approval_reason"],
                "proxy_family_id": f"polymarket_{event_id}",
                "source": "polymarket",
                "market_id": str(candidate.get("market_id")),
                "quality_score": float(candidate.get("quality_score") or 0.0),
                "channel": selection["channel"],
            }
        )
    rows.sort(key=lambda row: (row["resolution_date"], row["title"]))
    return rows


def write_geopolitical_expansion_json(path: Path, rows: list[dict]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def selection_audit_rows(rows: list[dict]) -> list[dict]:
    audit = []
    for row in rows:
        audit.append(
            {
                "event_id": row["event_id"],
                "title": row["title"],
                "channel": row["channel"],
                "resolution_date": row["resolution_date"],
                "peak_probability": row["peak_probability"],
                "total_volume_usd": row["total_volume_usd"],
                "quality_score": row["quality_score"],
                "approval_reason": row["approval_reason"],
            }
        )
    return audit


def write_selection_audit_csv(path: Path, rows: list[dict]) -> None:
    write_csv(path, selection_audit_rows(rows))


def render_geopolitical_expansion_summary(path: Path, rows: list[dict]) -> None:
    lines = [
        "# Phase 5.6 Geopolitical Expansion Summary",
        "",
        f"- Selected contracts: `{len(rows)}`",
        "- Policy: additive geopolitical expansion on top of the published `V5_Becker_top5_cap` stack, filtered through the geopolitical admission policy.",
        "- Motivation: test whether Becker's wider geopolitical efficiency gap can improve the stack more cleanly than further monetary tuning.",
        f"- Bucket cap: `{GEO_ADMISSION_POLICY['bucket_cap']:.2f}`",
        f"- Min volume floor: `${GEO_ADMISSION_POLICY['min_volume_usd']:,.0f}`",
        "",
        "| Event | Channel | Resolution Date | Peak Probability | Volume (USD) | Quality Score |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['title']} | {row['channel']} | {row['resolution_date']} | "
            f"{row['peak_probability']:.3f} | {row['total_volume_usd']:.2f} | {row['quality_score']:.3f} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
