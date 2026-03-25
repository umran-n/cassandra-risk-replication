from __future__ import annotations

from pathlib import Path

from .ablation_figures import BLACK, BLUE, GREEN, LIGHT_GRID, SLATE, WHITE, Canvas


def as_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_expansion_delta(summary_rows: list[dict], path: Path) -> None:
    lookup = {row["version"]: row for row in summary_rows}
    v4 = lookup["V4"]
    v5 = lookup["V5"]
    metrics = [
        ("SORTINO", float(v4["sortino"]), float(v5["sortino"]), max(float(v4["sortino"]), float(v5["sortino"]), 1.0), False),
        ("CAGR", float(v4["cagr"]), float(v5["cagr"]), max(float(v4["cagr"]), float(v5["cagr"]), 0.01), True),
        ("MDD", abs(float(v4["mdd"])), abs(float(v5["mdd"])), max(abs(float(v4["mdd"])), abs(float(v5["mdd"])), 0.01), True),
        ("AVG POSITION", float(v4["avg_position"]), float(v5["avg_position"]), max(float(v4["avg_position"]), float(v5["avg_position"]), 0.01), True),
    ]

    canvas = Canvas(1500, 980, WHITE)
    canvas.draw_text(canvas.width // 2, 38, "FIGURE 5. EXPANSION DELTA", BLACK, scale=4, align="center")
    canvas.draw_text(canvas.width // 2, 84, "V4 BASELINE (9 EVENTS) VERSUS V5 APPROVED UNIVERSE (38 EVENTS)", SLATE, scale=2, align="center")

    left = 320
    right = 120
    top = 170
    row_gap = 180
    bar_height = 34
    max_width = canvas.width - left - right

    for index, (label, v4_value, v5_value, scale_max, use_pct) in enumerate(metrics):
        y = top + index * row_gap
        canvas.draw_text(120, y + 18, label, BLACK, scale=3, align="left")
        canvas.line(left, y + 4, left + max_width, y + 4, LIGHT_GRID, 1)
        canvas.line(left, y + 74, left + max_width, y + 74, LIGHT_GRID, 1)
        canvas.line(left, y + 120, left + max_width, y + 120, BLACK, 2)

        for tick_index in range(6):
            tick_value = scale_max * tick_index / 5.0
            x = left + int((tick_value / scale_max) * max_width)
            canvas.line(x, y - 8, x, y + 120, LIGHT_GRID, 1)
            tick_label = as_pct(tick_value) if use_pct else f"{tick_value:.2f}"
            canvas.draw_text(x, y + 132, tick_label, SLATE, scale=2, align="center")

        v4_width = int((v4_value / scale_max) * max_width) if scale_max else 0
        v5_width = int((v5_value / scale_max) * max_width) if scale_max else 0
        canvas.draw_text(left - 18, y + 10, "V4", BLACK, scale=2, align="right")
        canvas.draw_text(left - 18, y + 58, "V5", BLACK, scale=2, align="right")
        canvas.fill_rect(left, y, v4_width, bar_height, BLUE)
        canvas.fill_rect(left, y + 48, v5_width, bar_height, GREEN)

        v4_label = as_pct(v4_value) if use_pct else f"{v4_value:.3f}"
        v5_label = as_pct(v5_value) if use_pct else f"{v5_value:.3f}"
        canvas.draw_text(left + v4_width + 16, y + 10, v4_label, BLACK, scale=2, align="left")
        canvas.draw_text(left + v5_width + 16, y + 58, v5_label, BLACK, scale=2, align="left")

    canvas.save_png(path)
