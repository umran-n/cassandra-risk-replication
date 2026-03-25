from __future__ import annotations

import copy
from collections import defaultdict
from pathlib import Path

from .utils import mean, parse_date


def filter_out_theme(entries: list[dict], theme_removed: str) -> list[dict]:
    return [copy.deepcopy(entry) for entry in entries if entry.get("structural_theme") != theme_removed]


def quarter_key(day_string: str) -> str:
    day = parse_date(day_string)
    quarter = ((day.month - 1) // 3) + 1
    return f"{day.year}Q{quarter}"


def quarter_sort_key(quarter_label: str) -> tuple[int, int]:
    return int(quarter_label[:4]), int(quarter_label[-1])


def theme_ablation_row(theme_removed: str, result: dict) -> dict:
    summary = result["summaries"]["cassandra"]
    return {
        "theme_removed": theme_removed,
        "n_events": len(result["resolved_seeds"]),
        "sortino": summary["sortino"],
        "cagr": summary["cagr"],
        "mdd": summary["max_drawdown_daily"],
        "avg_position": summary["avg_position"],
    }


def monetary_concentration_rows(attribution_rows: list[dict]) -> list[dict]:
    total_hazard = sum(float(row.get("hazard_contribution", 0.0)) for row in attribution_rows)
    rows = [row for row in attribution_rows if row.get("structural_theme") == "monetary_policy"]
    totals_by_event: dict[str, dict] = {}
    theme_total = 0.0

    for row in rows:
        event_id = row["event_id"]
        hazard = float(row.get("hazard_contribution", 0.0))
        theme_total += hazard
        entry = totals_by_event.setdefault(
            event_id,
            {
                "event_id": event_id,
                "question": row.get("question", ""),
                "cumulative_hazard": 0.0,
                "active_days": 0,
                "first_date": row["date"],
                "last_date": row["date"],
            },
        )
        entry["cumulative_hazard"] += hazard
        entry["active_days"] += 1
        entry["first_date"] = min(entry["first_date"], row["date"])
        entry["last_date"] = max(entry["last_date"], row["date"])

    ranked = sorted(
        totals_by_event.values(),
        key=lambda item: (-item["cumulative_hazard"], item["event_id"]),
    )
    output_rows: list[dict] = []
    for index, entry in enumerate(ranked, start=1):
        output_rows.append(
            {
                "rank": index,
                "event_id": entry["event_id"],
                "question": entry["question"],
                "cumulative_hazard": entry["cumulative_hazard"],
                "hazard_share_within_theme": 0.0 if theme_total == 0 else entry["cumulative_hazard"] / theme_total,
                "hazard_share_total": 0.0 if total_hazard == 0 else entry["cumulative_hazard"] / total_hazard,
                "active_days": entry["active_days"],
                "first_date": entry["first_date"],
                "last_date": entry["last_date"],
            }
        )
    return output_rows


def quarterly_drag_rows(
    dates: list[str],
    decomposition_rows: list[dict],
    positions: list[float],
    price_returns: list[float],
    cassandra_daily_returns: list[float],
    *,
    start_quarter: str,
    end_quarter: str,
    missed_recovery_position_cap: float = 0.85,
    missed_recovery_gap: float = 0.03,
) -> list[dict]:
    grouped_indices: dict[str, list[int]] = defaultdict(list)
    for index, day in enumerate(dates):
        quarter = quarter_key(day)
        if quarter_sort_key(start_quarter) <= quarter_sort_key(quarter) <= quarter_sort_key(end_quarter):
            grouped_indices[quarter].append(index)

    rows: list[dict] = []
    for quarter in sorted(grouped_indices, key=quarter_sort_key):
        indices = grouped_indices[quarter]
        spy_curve = 1.0
        cassandra_curve = 1.0
        for index in indices:
            spy_curve *= 1.0 + float(price_returns[index])
            cassandra_curve *= 1.0 + float(cassandra_daily_returns[index])

        avg_rsi = mean([float(decomposition_rows[index]["rsi"]) for index in indices])
        avg_position = mean([float(positions[index]) for index in indices])
        spy_total_return = spy_curve - 1.0
        cassandra_total_return = cassandra_curve - 1.0
        return_gap_vs_spy = spy_total_return - cassandra_total_return
        missed_recovery_flag = (
            spy_total_return > 0.0
            and avg_position < missed_recovery_position_cap
            and return_gap_vs_spy > missed_recovery_gap
        )
        rows.append(
            {
                "quarter": quarter,
                "avg_rsi": avg_rsi,
                "avg_position": avg_position,
                "spy_total_return": spy_total_return,
                "cassandra_total_return": cassandra_total_return,
                "return_gap_vs_spy": return_gap_vs_spy,
                "missed_recovery_flag": missed_recovery_flag,
            }
        )
    return rows


def render_diagnostic_report(
    path: Path,
    *,
    baseline_result: dict,
    approved_audit: list[dict],
    theme_rows: list[dict],
    monetary_rows: list[dict],
    quarter_rows: list[dict],
) -> None:
    baseline_summary = baseline_result["summaries"]["cassandra"]
    vol_target_sortino = baseline_result["summaries"]["vol_target"]["sortino"]
    loaded_count = sum(1 for row in approved_audit if row.get("status") == "loaded_polymarket_history")
    skipped_count = sum(1 for row in approved_audit if row.get("status") == "skipped_no_history")
    best_theme_row = max(theme_rows, key=lambda row: row["sortino"])
    flagged_quarters = [row for row in quarter_rows if row["missed_recovery_flag"]]
    top_flagged = sorted(flagged_quarters, key=lambda row: row["return_gap_vs_spy"], reverse=True)[:6]
    top_monetary = monetary_rows[:5]

    lines = [
        "# Expansion Diagnostic Report",
        "",
        "## Scope",
        "",
        f"- Baseline V5 approved universe: `38` approved events, with `{loaded_count}` active Polymarket histories and `{skipped_count}` Metaculus placeholders skipped for lack of time series.",
        f"- V5 baseline Cassandra metrics: Sortino `{baseline_summary['sortino']:.3f}`, CAGR `{baseline_summary['cagr'] * 100:.2f}%`, daily MDD `{baseline_summary['max_drawdown_daily'] * 100:.2f}%`, avg position `{baseline_summary['avg_position'] * 100:.2f}%`.",
        f"- Same-run Vol Target Sortino reference: `{vol_target_sortino:.3f}`.",
        "",
        "## Theme-Level Ablation",
        "",
        "| Theme Removed | Active Events | Sortino | CAGR | MDD | Avg Position |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in theme_rows:
        lines.append(
            f"| {row['theme_removed']} | {row['n_events']} | {row['sortino']:.3f} | {row['cagr'] * 100:.2f}% | "
            f"{row['mdd'] * 100:.2f}% | {row['avg_position'] * 100:.2f}% |"
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            f"- Removing `{best_theme_row['theme_removed']}` produced the strongest Sortino recovery, which is the cleanest first-pass test of the over-warning hypothesis.",
            "",
            "## Monetary Concentration",
            "",
            "Top monetary-policy contributors ranked by cumulative hazard contribution across the V5 backtest window.",
            "",
            "| Rank | Event | Cum Hazard | Theme Share | Total Share | Active Days |",
            "| ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in top_monetary:
        lines.append(
            f"| {row['rank']} | {row['event_id']} | {row['cumulative_hazard']:.3f} | "
            f"{row['hazard_share_within_theme'] * 100:.2f}% | {row['hazard_share_total'] * 100:.2f}% | {row['active_days']} |"
        )

    lines.extend(
        [
            "",
            "## RSI Drag By Quarter",
            "",
            "Flagged quarters are positive-SPY quarters where average position stayed below 85% and the Cassandra quarter return lagged SPY by more than 3 percentage points.",
            "",
            "| Quarter | Avg RSI | Avg Position | SPY Return | Cassandra Return | Gap vs SPY | Flagged |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in quarter_rows:
        lines.append(
            f"| {row['quarter']} | {row['avg_rsi']:.3f} | {row['avg_position'] * 100:.2f}% | "
            f"{row['spy_total_return'] * 100:.2f}% | {row['cassandra_total_return'] * 100:.2f}% | "
            f"{row['return_gap_vs_spy'] * 100:.2f}% | {'YES' if row['missed_recovery_flag'] else 'no'} |"
        )

    lines.extend(["", "## Findings", ""])
    if top_flagged:
        lines.append("- The clearest missed-recovery quarters were:")
        for row in top_flagged:
            lines.append(
                f"  - `{row['quarter']}`: avg position `{row['avg_position'] * 100:.2f}%`, SPY `{row['spy_total_return'] * 100:.2f}%`, "
                f"Cassandra `{row['cassandra_total_return'] * 100:.2f}%`, gap `{row['return_gap_vs_spy'] * 100:.2f}%`."
            )
    else:
        lines.append("- No quarter met the missed-recovery flag threshold.")
    lines.append(
        f"- The top monetary-policy event was `{top_monetary[0]['event_id']}` at `{top_monetary[0]['hazard_share_within_theme'] * 100:.2f}%` "
        "of the theme hazard, which indicates whether the damage is concentrated or spread across the rate-cycle stack."
        if top_monetary
        else "- No monetary-policy events were active in the loaded V5 history."
    )
    lines.append(
        "- If monetary removal improves Sortino materially while geopolitical and electoral removal do not, the degradation is best explained as chronic macro over-warning rather than broad event-universe failure."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
