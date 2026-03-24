from __future__ import annotations

import csv
import math
import struct
import zlib
from pathlib import Path


WHITE = (255, 255, 255, 255)
BLACK = (20, 24, 35, 255)
SLATE = (88, 96, 120, 255)
LIGHT_GRID = (224, 228, 236, 255)
BLUE = (44, 94, 164, 255)
BLUE_LIGHT = (143, 186, 231, 255)
GREEN = (33, 128, 98, 255)
GREEN_LIGHT = (161, 215, 197, 255)
RED = (187, 67, 72, 255)
GOLD = (211, 153, 47, 255)
PURPLE = (108, 72, 152, 255)
TEAL = (48, 140, 146, 255)
GRAY_BAR = (190, 196, 209, 255)


FONT_5X7 = {
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "00110", "00110"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    "%": ["11001", "11010", "00100", "01000", "10110", "00110", "00000"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00001", "00001", "00001", "00001", "10001", "10001", "01110"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
}


FIGURE_1_RUNS = [
    ("aggregation_per_family", "PER FAMILY", BLUE),
    ("no_manual_events", "NO MANUAL", RED),
    ("top_event_removal_ukraine", "REMOVE UKRAINE", GREEN),
    ("top_event_removal_debt_ceiling", "REMOVE DEBT", GREEN_LIGHT),
    ("aggregation_max", "FORCE MAX", TEAL),
    ("aggregation_weighted_average", "FORCE WAVG", GOLD),
]

THEME_RUNS = [
    ("theme_geopolitical_only", "GEOPOLITICAL", BLUE_LIGHT),
    ("theme_monetary_policy_only", "MONETARY POLICY", TEAL),
    ("theme_fiscal_debt_only", "FISCAL DEBT", GOLD),
    ("theme_electoral_only", "ELECTORAL", GRAY_BAR),
    ("theme_systemic_credit_only", "SYSTEMIC CREDIT", BLUE),
    ("theme_trade_technology_only", "TRADE TECH", PURPLE),
]

PROXY_EVENT_RUNS = [
    ("china_taiwan_2024", "CHINA TAIWAN"),
    ("oct_selloff_2023", "OCT SELLOFF"),
    ("us_debt_ceiling_2023", "DEBT CEILING"),
]


class Canvas:
    def __init__(self, width: int, height: int, background: tuple[int, int, int, int] = WHITE) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(background * (width * height))

    def _set_pixel(self, x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            index = (y * self.width + x) * 4
            self.pixels[index : index + 4] = bytes(color)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: tuple[int, int, int, int]) -> None:
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + width)
        y1 = min(self.height, y + height)
        if x1 <= x0 or y1 <= y0:
            return
        for row in range(y0, y1):
            offset = (row * self.width + x0) * 4
            self.pixels[offset : offset + (x1 - x0) * 4] = bytes(color) * (x1 - x0)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int, int], thickness: int = 1) -> None:
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            for tx in range(-(thickness // 2), thickness - thickness // 2):
                for ty in range(-(thickness // 2), thickness - thickness // 2):
                    self._set_pixel(x0 + tx, y0 + ty, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def text_width(self, text: str, scale: int = 1) -> int:
        characters = [FONT_5X7.get(char, FONT_5X7[" "]) for char in text.upper()]
        return len(characters) * (5 * scale + scale) - scale

    def draw_text(
        self,
        x: int,
        y: int,
        text: str,
        color: tuple[int, int, int, int] = BLACK,
        scale: int = 1,
        align: str = "left",
    ) -> None:
        rendered = text.upper()
        if align == "center":
            x -= self.text_width(rendered, scale) // 2
        elif align == "right":
            x -= self.text_width(rendered, scale)

        cursor = x
        for char in rendered:
            pattern = FONT_5X7.get(char, FONT_5X7[" "])
            for row_index, row in enumerate(pattern):
                for col_index, value in enumerate(row):
                    if value == "1":
                        self.fill_rect(
                            cursor + col_index * scale,
                            y + row_index * scale,
                            scale,
                            scale,
                            color,
                        )
            cursor += 5 * scale + scale

    def save_png(self, path: Path) -> None:
        raw_rows = []
        row_bytes = self.width * 4
        for row in range(self.height):
            start = row * row_bytes
            raw_rows.append(b"\x00" + self.pixels[start : start + row_bytes])
        compressed = zlib.compress(b"".join(raw_rows), level=9)

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (
                struct.pack("!I", len(data))
                + tag
                + data
                + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        header = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack("!IIBBBBB", self.width, self.height, 8, 6, 0, 0, 0)
        payload = header + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
        path.write_bytes(payload)


def load_ablation_summary(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for column in ("CAGR", "Sortino", "MDD", "avg_position"):
            row[column] = float(row[column])
    return rows


def row_lookup(rows: list[dict]) -> dict[str, dict]:
    return {row["run_id"]: row for row in rows}


def figure1_rows(rows: list[dict]) -> list[dict]:
    lookup = row_lookup(rows)
    return [
        {
            "label": label,
            "sortino": lookup[run_id]["Sortino"],
            "color": color,
        }
        for run_id, label, color in FIGURE_1_RUNS
        if run_id in lookup
    ]


def figure2_rows(rows: list[dict]) -> list[dict]:
    lookup = row_lookup(rows)
    return [
        {
            "label": label,
            "sortino": lookup[run_id]["Sortino"],
            "cagr": lookup[run_id]["CAGR"],
            "color": color,
        }
        for run_id, label, color in THEME_RUNS
        if run_id in lookup
    ]


def figure3_rows(rows: list[dict]) -> list[dict]:
    lookup = row_lookup(rows)
    payload = []
    for event_id, label in PROXY_EVENT_RUNS:
        combined_key = f"single_proxy_{event_id}_all_combined"
        dominant_key = f"single_proxy_{event_id}_dominant_only"
        if combined_key not in lookup or dominant_key not in lookup:
            continue
        combined = lookup[combined_key]["Sortino"]
        dominant = lookup[dominant_key]["Sortino"]
        payload.append(
            {
                "label": label,
                "combined": combined,
                "dominant": dominant,
                "delta": dominant - combined,
            }
        )
    return payload


def nice_ticks(max_value: float, tick_count: int = 5) -> list[float]:
    if max_value <= 0:
        return [0.0]
    rough = max_value / tick_count
    power = 10 ** math.floor(math.log10(rough))
    normalized = rough / power
    if normalized <= 1:
        step = 1 * power
    elif normalized <= 2:
        step = 2 * power
    elif normalized <= 2.5:
        step = 2.5 * power
    elif normalized <= 5:
        step = 5 * power
    else:
        step = 10 * power
    count = int(math.ceil(max_value / step))
    return [step * index for index in range(count + 1)]


def sortino_ticks(max_value: float) -> list[float]:
    step = 0.2
    count = int(math.ceil(max_value / step))
    return [step * index for index in range(count + 1)]


def delta_ticks(max_abs_value: float) -> list[float]:
    max_abs = max(0.02, max_abs_value)
    step = 0.01 if max_abs <= 0.05 else 0.02
    count = int(math.ceil(max_abs / step))
    ticks = [step * index for index in range(-count, count + 1)]
    return ticks


def draw_horizontal_bar_chart(
    canvas: Canvas,
    rows: list[dict],
    *,
    title: str,
    subtitle: str,
    x_max: float,
    output_metric: str,
    label_formatter,
    reference_lines: list[tuple[float, tuple[int, int, int, int], str]] | None = None,
) -> None:
    left = 390
    right = 120
    top = 170
    bottom = 100
    chart_width = canvas.width - left - right
    chart_height = canvas.height - top - bottom

    canvas.draw_text(canvas.width // 2, 40, title, BLACK, scale=4, align="center")
    canvas.draw_text(canvas.width // 2, 88, subtitle, SLATE, scale=2, align="center")

    ticks = sortino_ticks(x_max)
    for tick in ticks:
        x = left + int((tick / x_max) * chart_width)
        canvas.line(x, top, x, top + chart_height, LIGHT_GRID, 1)
        canvas.draw_text(x, top + chart_height + 18, f"{tick:.1f}", SLATE, scale=2, align="center")

    canvas.line(left, top, left, top + chart_height, BLACK, 2)
    canvas.line(left, top + chart_height, left + chart_width, top + chart_height, BLACK, 2)

    if reference_lines:
        for value, color, label in reference_lines:
            x = left + int((value / x_max) * chart_width)
            canvas.line(x, top, x, top + chart_height, color, 2)
            canvas.draw_text(x, top - 24, label, color, scale=2, align="center")

    bar_step = chart_height // max(len(rows), 1)
    bar_height = min(58, bar_step - 18)
    for index, row in enumerate(rows):
        y = top + index * bar_step + (bar_step - bar_height) // 2
        bar_width = int((row[output_metric] / x_max) * chart_width)
        canvas.draw_text(left - 22, y + 16, row["label"], BLACK, scale=3, align="right")
        canvas.fill_rect(left, y, bar_width, bar_height, row["color"])
        canvas.fill_rect(left + bar_width, y, max(1, chart_width - bar_width), bar_height, (245, 247, 250, 255))
        label = label_formatter(row)
        label_x = left + bar_width + 16
        label_width = canvas.text_width(label, scale=3)
        if label_x + label_width > canvas.width - 24:
            canvas.draw_text(canvas.width - 24, y + 16, label, BLACK, scale=3, align="right")
        else:
            canvas.draw_text(label_x, y + 16, label, BLACK, scale=3, align="left")


def render_sortino_comparison(rows: list[dict], path: Path) -> None:
    figure_rows = figure1_rows(rows)
    canvas = Canvas(1600, 920)
    x_max = max(max(row["sortino"] for row in figure_rows), 1.25)
    draw_horizontal_bar_chart(
        canvas,
        figure_rows,
        title="FIGURE 1. SORTINO COMPARISON",
        subtitle="KEY STRUCTURAL ABLATIONS VERSUS THE CURRENT PER FAMILY BASELINE",
        x_max=x_max,
        output_metric="sortino",
        label_formatter=lambda row: f"{row['sortino']:.3f}",
        reference_lines=[
            (0.733, RED, "BH 0.733"),
            (0.836, GREEN, "VOL 0.836"),
        ],
    )
    canvas.save_png(path)


def render_theme_isolation(rows: list[dict], path: Path) -> None:
    figure_rows = figure2_rows(rows)
    canvas = Canvas(1600, 960)
    x_max = max(max(row["sortino"] for row in figure_rows), 1.25)
    draw_horizontal_bar_chart(
        canvas,
        figure_rows,
        title="FIGURE 2. THEME ISOLATION",
        subtitle="ISOLATED STRUCTURAL THEME SORTINOS WITH CAGR ANNOTATIONS",
        x_max=x_max,
        output_metric="sortino",
        label_formatter=lambda row: f"{row['sortino']:.3f}  CAGR {row['cagr'] * 100:.2f}%",
        reference_lines=[(0.836, GREEN, "VOL 0.836")],
    )
    canvas.save_png(path)


def render_proxy_delta(rows: list[dict], path: Path) -> None:
    figure_rows = figure3_rows(rows)
    canvas = Canvas(1500, 820)
    left = 300
    right = 120
    top = 170
    bottom = 110
    chart_width = canvas.width - left - right
    chart_height = canvas.height - top - bottom
    max_abs = max(abs(row["delta"]) for row in figure_rows) if figure_rows else 0.02

    canvas.draw_text(canvas.width // 2, 40, "FIGURE 3. PROXY DELTA", BLACK, scale=4, align="center")
    canvas.draw_text(canvas.width // 2, 88, "DOMINANT ONLY SORTINO MINUS ALL PROXIES COMBINED", SLATE, scale=2, align="center")

    ticks = delta_ticks(max_abs * 1.25)
    x_min = min(ticks)
    x_max = max(ticks)
    zero_x = left + int(((0 - x_min) / (x_max - x_min)) * chart_width)

    for tick in ticks:
        x = left + int(((tick - x_min) / (x_max - x_min)) * chart_width)
        canvas.line(x, top, x, top + chart_height, LIGHT_GRID, 1)
        label = f"{tick:+.2f}"
        if abs(tick) < 1e-9:
            label = "0.00"
        canvas.draw_text(x, top + chart_height + 18, label, SLATE, scale=2, align="center")

    canvas.line(zero_x, top, zero_x, top + chart_height, BLACK, 2)
    canvas.line(left, top + chart_height, left + chart_width, top + chart_height, BLACK, 2)

    bar_step = chart_height // max(len(figure_rows), 1)
    bar_height = min(74, bar_step - 18)
    for index, row in enumerate(figure_rows):
        y = top + index * bar_step + (bar_step - bar_height) // 2
        canvas.draw_text(left - 22, y + 22, row["label"], BLACK, scale=3, align="right")
        bar_color = GREEN if row["delta"] >= 0 else RED
        x_value = left + int(((row["delta"] - x_min) / (x_max - x_min)) * chart_width)
        x_start = min(zero_x, x_value)
        width = max(1, abs(x_value - zero_x))
        canvas.fill_rect(x_start, y, width, bar_height, bar_color)
        value_label = f"{row['delta']:+.3f}"
        canvas.draw_text(
            x_value + (16 if row["delta"] >= 0 else -16),
            y + 22,
            value_label,
            BLACK,
            scale=3,
            align="left" if row["delta"] >= 0 else "right",
        )
        detail = f"{row['dominant']:.3f} VS {row['combined']:.3f}"
        canvas.draw_text(left + chart_width - 8, y + 22, detail, SLATE, scale=2, align="right")

    canvas.save_png(path)


def render_ablation_figures(summary_path: Path, output_dir: Path) -> None:
    rows = load_ablation_summary(summary_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    render_sortino_comparison(rows, output_dir / "fig1_sortino_comparison.png")
    render_theme_isolation(rows, output_dir / "fig2_theme_isolation.png")
    render_proxy_delta(rows, output_dir / "fig3_proxy_delta.png")
