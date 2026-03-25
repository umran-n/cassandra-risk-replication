from __future__ import annotations

from pathlib import Path

from .ablation_figures import BLACK, BLUE, GREEN, LIGHT_GRID, SLATE, WHITE, Canvas


def as_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_becker_delta(summary_rows: list[dict], path: Path) -> None:
    lookup = {row["version"]: row for row in summary_rows}
    v5 = lookup["V5"]
    v5_becker = lookup["V5_Becker"]
    metrics = [
        ("SORTINO", float(v5["sortino"]), float(v5_becker["sortino"]), max(float(v5["sortino"]), float(v5_becker["sortino"]), 0.5), False),
        ("CAGR", float(v5["cagr"]), float(v5_becker["cagr"]), max(float(v5["cagr"]), float(v5_becker["cagr"]), 0.01), True),
        ("MDD", abs(float(v5["mdd"])), abs(float(v5_becker["mdd"])), max(abs(float(v5["mdd"])), abs(float(v5_becker["mdd"])), 0.01), True),
        ("AVG POSITION", float(v5["avg_position"]), float(v5_becker["avg_position"]), max(float(v5["avg_position"]), float(v5_becker["avg_position"]), 0.01), True),
    ]

    canvas = Canvas(1500, 980, WHITE)
    canvas.draw_text(canvas.width // 2, 38, "BECKER CALIBRATION DELTA", BLACK, scale=4, align="center")
    canvas.draw_text(canvas.width // 2, 84, "V5 APPROVED UNIVERSE VERSUS V5 BECKER-CALIBRATED", SLATE, scale=2, align="center")

    left = 320
    right = 120
    top = 170
    row_gap = 180
    bar_height = 34
    max_width = canvas.width - left - right

    for index, (label, base_value, calibrated_value, scale_max, use_pct) in enumerate(metrics):
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

        base_width = int((base_value / scale_max) * max_width) if scale_max else 0
        calibrated_width = int((calibrated_value / scale_max) * max_width) if scale_max else 0
        canvas.draw_text(left - 18, y + 10, "V5", BLACK, scale=2, align="right")
        canvas.draw_text(left - 18, y + 58, "V5 BECKER", BLACK, scale=2, align="right")
        canvas.fill_rect(left, y, base_width, bar_height, BLUE)
        canvas.fill_rect(left, y + 48, calibrated_width, bar_height, GREEN)

        base_label = as_pct(base_value) if use_pct else f"{base_value:.3f}"
        calibrated_label = as_pct(calibrated_value) if use_pct else f"{calibrated_value:.3f}"
        canvas.draw_text(left + base_width + 16, y + 10, base_label, BLACK, scale=2, align="left")
        canvas.draw_text(left + calibrated_width + 16, y + 58, calibrated_label, BLACK, scale=2, align="left")

    canvas.save_png(path)
