from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .utils import ensure_dir, write_csv


def to_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def suggested_action(candidate: dict[str, Any]) -> str:
    theme = str(candidate.get("structural_theme") or "")
    volume = to_float(candidate.get("volume"))
    flags: list[str] = []
    if theme == "electoral":
        flags.append("REVIEW_CAP")
    else:
        flags.append("REVIEW")
    if volume < 10000.0:
        flags.append("LOW_LIQUIDITY")
    return "|".join(flags)


def worksheet_row(candidate: dict[str, Any]) -> dict[str, Any]:
    volume = round(to_float(candidate.get("volume")), 2)
    peak_probability = to_float(candidate.get("peak_probability"))
    min_probability = to_float(candidate.get("min_probability"))
    probability_range = round(max(peak_probability - min_probability, 0.0), 6)

    num_traders = candidate.get("num_traders")
    if num_traders in (None, ""):
        num_traders = ""

    return {
        "event_id": candidate.get("event_id") or "",
        "title": candidate.get("title") or candidate.get("question") or "",
        "theme": candidate.get("structural_theme") or "",
        "resolution_date": candidate.get("resolution_date") or "",
        "peak_probability": round(peak_probability, 6),
        "min_probability": round(min_probability, 6),
        "probability_range": probability_range,
        "total_volume_usd": volume,
        "num_traders": num_traders,
        "num_history_points": int(candidate.get("history_point_count") or 0),
        "suggested_action": suggested_action(candidate),
    }


def build_curator_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [worksheet_row(candidate) for candidate in candidates]
    rows.sort(key=lambda row: (str(row["theme"]), -to_float(row["total_volume_usd"]), str(row["title"])))
    return rows


def load_candidates(path: Path) -> list[dict[str, Any]]:
    return list(json.loads(path.read_text(encoding="utf-8")))


def write_curator_worksheet(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    write_csv(path, rows)


def build_curator_markdown(rows: list[dict[str, Any]]) -> str:
    by_theme: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_theme[str(row["theme"])].append(row)

    lines = [
        "# Curator Worksheet Summary",
        "",
        "- Source: `data/candidates/polymarket_candidates.json`",
        "- Sorted by theme, then `total_volume_usd` descending",
        "- `suggested_action` defaults to `REVIEW`, uses `REVIEW_CAP` for electoral rows, and appends `LOW_LIQUIDITY` when `total_volume_usd < 10000`.",
        "- `num_traders` is left blank when unavailable in the source candidate payload.",
        "",
    ]

    for theme in sorted(by_theme):
        theme_rows = sorted(by_theme[theme], key=lambda row: (-to_float(row["total_volume_usd"]), str(row["title"])))[:20]
        lines.extend(
            [
                f"## {theme}",
                "",
                "| Rank | title | resolution_date | peak_probability | probability_range | total_volume_usd | num_history_points | suggested_action |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for index, row in enumerate(theme_rows, start=1):
            title = str(row["title"]).replace("|", "\\|")
            lines.append(
                f"| {index} | {title} | {row['resolution_date']} | "
                f"{to_float(row['peak_probability']):.6f} | {to_float(row['probability_range']):.6f} | "
                f"{to_float(row['total_volume_usd']):.2f} | {int(row['num_history_points'])} | {row['suggested_action']} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_curator_markdown(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
