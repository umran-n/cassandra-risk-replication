from __future__ import annotations

import csv
import copy
from collections import defaultdict
from pathlib import Path


def load_csv_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def apply_structural_theme_filter(entries: list[dict], structural_theme: str | None) -> list[dict]:
    if not structural_theme:
        return [copy.deepcopy(entry) for entry in entries]
    return [copy.deepcopy(entry) for entry in entries if entry.get("structural_theme") == structural_theme]


def apply_event_removals(entries: list[dict], removed_event_ids: set[str] | None) -> list[dict]:
    if not removed_event_ids:
        return [copy.deepcopy(entry) for entry in entries]
    return [copy.deepcopy(entry) for entry in entries if entry.get("event_id") not in removed_event_ids]


def apply_dominant_proxy_filter(entries: list[dict], dominant_proxy_by_event: dict[str, str]) -> list[dict]:
    if not dominant_proxy_by_event:
        return [copy.deepcopy(entry) for entry in entries]

    filtered: list[dict] = []
    for entry in entries:
        event_id = entry.get("event_id")
        required_market_id = dominant_proxy_by_event.get(event_id)
        if not required_market_id or not entry.get("market_id"):
            filtered.append(copy.deepcopy(entry))
            continue
        if entry["market_id"] == required_market_id:
            filtered.append(copy.deepcopy(entry))
    return filtered


def apply_forced_aggregation(entries: list[dict], policy: str | None) -> list[dict]:
    updated: list[dict] = []
    for entry in entries:
        item = copy.deepcopy(entry)
        if policy:
            item["aggregation_policy"] = policy
        updated.append(item)
    return updated


def prepare_ablation_inputs(
    base_seeds: list[dict],
    shortlist: list[dict],
    *,
    public_only: bool = False,
    structural_theme: str | None = None,
    removed_event_ids: set[str] | None = None,
    dominant_proxy_by_event: dict[str, str] | None = None,
    forced_aggregation: str | None = None,
) -> tuple[list[dict], list[dict]]:
    working_seeds = [] if public_only else [copy.deepcopy(seed) for seed in base_seeds]
    working_shortlist = [copy.deepcopy(entry) for entry in shortlist]

    working_seeds = apply_structural_theme_filter(working_seeds, structural_theme)
    working_shortlist = apply_structural_theme_filter(working_shortlist, structural_theme)

    working_seeds = apply_event_removals(working_seeds, removed_event_ids)
    working_shortlist = apply_event_removals(working_shortlist, removed_event_ids)

    if dominant_proxy_by_event:
        working_shortlist = apply_dominant_proxy_filter(working_shortlist, dominant_proxy_by_event)

    working_seeds = apply_forced_aggregation(working_seeds, forced_aggregation)
    working_shortlist = apply_forced_aggregation(working_shortlist, forced_aggregation)
    return working_seeds, working_shortlist


def force_config_aggregation(config: dict, policy: str | None) -> dict:
    updated = copy.deepcopy(config)
    if not policy:
        return updated
    updated["cassandra"]["multi_proxy_aggregation"] = policy
    updated["cassandra"]["multi_family_aggregation"] = policy
    updated["cassandra"]["proxy_relation_aggregation_defaults"] = {
        "orthogonal": policy,
        "nested": policy,
        "substitute": policy,
    }
    return updated


def dominant_proxy_by_event_from_attribution_rows(rows: list[dict]) -> dict[str, str]:
    by_event_market: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        event_id = row.get("event_id")
        market_id = row.get("dominant_event_market_id")
        if not event_id or not market_id:
            continue
        by_event_market[event_id][market_id] += float(row.get("hazard_contribution", 0.0))

    dominant: dict[str, str] = {}
    for event_id, market_scores in by_event_market.items():
        if not market_scores:
            continue
        dominant[event_id] = max(market_scores, key=market_scores.get)
    return dominant


def dominant_theme_from_attribution_rows(rows: list[dict]) -> str:
    scores: dict[str, float] = defaultdict(float)
    for row in rows:
        scores[row.get("structural_theme", "")] += float(row.get("hazard_contribution", 0.0))
    scores = {key: value for key, value in scores.items() if key}
    return max(scores, key=scores.get) if scores else "none"


def dominant_event_from_attribution_rows(rows: list[dict]) -> str:
    scores: dict[str, float] = defaultdict(float)
    for row in rows:
        scores[row.get("event_id", "")] += float(row.get("hazard_contribution", 0.0))
    scores = {key: value for key, value in scores.items() if key}
    return max(scores, key=scores.get) if scores else "none"


def multi_proxy_event_ids(shortlist: list[dict]) -> list[str]:
    counts: dict[str, set[str]] = defaultdict(set)
    for entry in shortlist:
        market_id = entry.get("market_id")
        if market_id:
            counts[entry["event_id"]].add(market_id)
    return sorted(event_id for event_id, market_ids in counts.items() if len(market_ids) > 1)


def summarize_ablation_run(run_id: str, result: dict, notes: str) -> dict:
    summary = result["summaries"]["cassandra"]
    attribution_rows = result["hazard_attribution_rows"]
    return {
        "run_id": run_id,
        "CAGR": summary["cagr"],
        "Sortino": summary["sortino"],
        "MDD": summary["max_drawdown_daily"],
        "avg_position": summary["avg_position"],
        "dominant_theme": dominant_theme_from_attribution_rows(attribution_rows),
        "dominant_event": dominant_event_from_attribution_rows(attribution_rows),
        "notes": notes,
    }


def render_ablation_report(
    path: Path,
    baseline_row: dict,
    ablation_rows: list[dict],
    buy_hold_sortino: float,
    vol_target_sortino: float,
) -> None:
    by_run_id = {row["run_id"]: row for row in ablation_rows}
    lines: list[str] = []
    lines.append("# Ablation Report")
    lines.append("")
    lines.append("## What Held")
    lines.append("")
    held_rows = [
        row for row in ablation_rows
        if row["Sortino"] >= vol_target_sortino
    ]
    if held_rows:
        for row in held_rows:
            lines.append(
                f"- `{row['run_id']}` kept Cassandra Sortino at {row['Sortino']:.3f}, above the Vol Target baseline of {vol_target_sortino:.3f}."
            )
    else:
        lines.append("- No ablation run stayed above the Vol Target baseline on Sortino.")
    lines.append("")
    lines.append("## What Broke")
    lines.append("")
    weakest = sorted(ablation_rows, key=lambda row: (row["Sortino"], row["CAGR"]))[:5]
    for row in weakest:
        lines.append(
            f"- `{row['run_id']}` fell to CAGR {row['CAGR'] * 100:.2f}% and Sortino {row['Sortino']:.3f}; dominant theme was `{row['dominant_theme']}`."
        )
    lines.append("")
    lines.append("## What Surprised")
    lines.append("")
    baseline_sortino = baseline_row["Sortino"]
    max_row = by_run_id.get("aggregation_max")
    weighted_row = by_run_id.get("aggregation_weighted_average")
    no_manual_row = by_run_id.get("no_manual_events")
    if max_row and weighted_row:
        lines.append(
            f"- Aggregation policy mattered by {abs(max_row['Sortino'] - weighted_row['Sortino']):.3f} Sortino points between forced `max` and forced `weighted_average`."
        )
    if no_manual_row:
        delta = no_manual_row["Sortino"] - baseline_sortino
        lines.append(
            f"- Removing manual events changed Sortino by {delta:+.3f} versus the per-family baseline, which directly quantifies public-data dependence."
        )
    lines.append(
        f"- The current per-family baseline remains `{baseline_row['run_id']}` with CAGR {baseline_row['CAGR'] * 100:.2f}%, Sortino {baseline_row['Sortino']:.3f}, and MDD {baseline_row['MDD'] * 100:.2f}%."
    )
    lines.append(
        f"- Buy & Hold and Vol Target reference Sortinos for the same window are {buy_hold_sortino:.3f} and {vol_target_sortino:.3f}, respectively."
    )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
