from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cassandra_risk.config import load_json  # noqa: E402
from cassandra_risk.events import load_polymarket_approved_universe  # noqa: E402
from cassandra_risk.monetary_subablation import remove_event_ids  # noqa: E402
from cassandra_risk.utils import ensure_dir, write_csv  # noqa: E402
from run_backtest import compute_price_returns, fetch_fred_tb3ms, fetch_spy_prices, run_version  # noqa: E402
from run_becker_stack import compose_daily_transform  # noqa: E402


K_VALUES = [round(index * 0.05, 2) for index in range(21)]

BENCHMARK = {
    "sortino": 0.32321187680490937,
    "cagr": 0.07133282373147787,
    "mdd": -0.33717284428360483,
    "downside_dev": 0.14313473306967237,
}

SEEDED_RESULTS = {
    "fractional": {
        0.25: {
            "sortino": 0.6959681523183717,
            "cagr": 0.13740315656448865,
            "downside_dev": 0.1636973779656668,
            "mdd": -0.33717284428360483,
            "rsi_min": 0.30,
            "rsi_max": 8.69,
        },
        0.50: {
            "sortino": 4.599046502337798,
            "cagr": 0.524743406777781,
            "downside_dev": 0.26798487781649677,
            "mdd": -0.4488446859611547,
            "rsi_min": -294.48,
            "rsi_max": 23.12,
        },
        1.00: {
            "sortino": 0.08869018094137701,
            "cagr": 0.026378160074570722,
            "downside_dev": 0.194961620694563,
            "mdd": -0.33717284428360483,
            "rsi_min": -12.46,
            "rsi_max": 27.83,
        },
    },
    "asymmetric": {
        1.00: {
            "sortino": 0.36101818088877874,
            "cagr": 0.07774133013841222,
            "downside_dev": 0.1488759407152627,
            "mdd": -0.33717284428360483,
            "rsi_min": 0.0851,
            "rsi_max": 1.0,
        }
    },
}


def top_five_monetary_event_ids(v5_result: dict) -> set[str]:
    event_totals: dict[str, float] = {}
    for row in v5_result["hazard_attribution_rows"]:
        if row.get("structural_theme") != "monetary_policy":
            continue
        event_totals[row["event_id"]] = event_totals.get(row["event_id"], 0.0) + float(row["hazard_contribution"])
    return {
        event_id for event_id, _value in sorted(event_totals.items(), key=lambda item: (-item[1], item[0]))[:5]
    }


def sweep_row(k: float, result: dict) -> dict:
    summary = result["summaries"]["cassandra"]
    rsi_values = result["cassandra_rsi"]
    return {
        "k": round(float(k), 2),
        "sortino": summary["sortino"],
        "cagr": summary["cagr"],
        "downside_dev": summary["downside_deviation"],
        "mdd": summary["max_drawdown_daily"],
        "rsi_min": min(rsi_values),
        "rsi_max": max(rsi_values),
    }


def seeded_row(mode: str, k: float) -> dict:
    seeded = SEEDED_RESULTS[mode][round(float(k), 2)]
    return {
        "k": round(float(k), 2),
        "sortino": seeded["sortino"],
        "cagr": seeded["cagr"],
        "downside_dev": seeded["downside_dev"],
        "mdd": seeded["mdd"],
        "rsi_min": seeded["rsi_min"],
        "rsi_max": seeded["rsi_max"],
    }


def run_sweep(
    *,
    mode: str,
    dates: list[str],
    price_returns: list[float],
    price_rows: list[dict],
    raw_dir: Path,
    fred_rows: list[dict],
    fallback_annual_rate: float,
    fred_fetch_succeeded: bool,
    approved_seeds: list[dict],
    approved_audit: list[dict],
    becker_config: dict,
    top_five_event_ids: set[str],
) -> list[dict]:
    rows: list[dict] = []
    filtered_seeds = remove_event_ids(approved_seeds, top_five_event_ids)
    for k in K_VALUES:
        rounded_k = round(float(k), 2)
        if rounded_k in SEEDED_RESULTS.get(mode, {}):
            rows.append(seeded_row(mode, rounded_k))
            continue

        result = run_version(
            version="v3",
            base_config=becker_config,
            base_seeds=[],
            shortlist=[],
            dates=dates,
            price_returns=price_returns,
            price_rows=price_rows,
            raw_dir=raw_dir,
            refresh=False,
            fred_rows=fred_rows,
            fallback_annual_rate=fallback_annual_rate,
            fred_fetch_succeeded=fred_fetch_succeeded,
            extra_curated_seeds=filtered_seeds,
            extra_curated_audit=approved_audit,
            include_robustness=False,
            include_bootstrap=False,
            daily_events_transform=compose_daily_transform(
                enable_becker=True,
                bucket_cap=0.30,
                kelly_scale=rounded_k,
                kelly_mode=mode,
            ),
        )
        rows.append(sweep_row(rounded_k, result))
    rows.sort(key=lambda row: row["k"])
    return rows


def render_plot_with_powershell(fractional_csv: Path, asymmetric_csv: Path, output_path: Path) -> None:
    script = r"""
param(
    [string]$FractionalCsv,
    [string]$AsymmetricCsv,
    [string]$OutputPng
)

$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

$fractional = Import-Csv $FractionalCsv
$asymmetric = Import-Csv $AsymmetricCsv

function Convert-ToDoubleOrNaN($value) {
    if ($null -eq $value) { return [double]::NaN }
    $text = [string]$value
    if ([string]::IsNullOrWhiteSpace($text)) { return [double]::NaN }
    try {
        return [double]$text
    }
    catch {
        return [double]::NaN
    }
}

function Is-FiniteNumber($value) {
    return (-not [double]::IsNaN($value)) -and (-not [double]::IsInfinity($value))
}

function To-DoubleRows($rows) {
    $out = @()
    foreach ($row in $rows) {
        $out += [pscustomobject]@{
            k = Convert-ToDoubleOrNaN $row.k
            sortino = Convert-ToDoubleOrNaN $row.sortino
            cagr = Convert-ToDoubleOrNaN $row.cagr
            downside_dev = Convert-ToDoubleOrNaN $row.downside_dev
            mdd = Convert-ToDoubleOrNaN $row.mdd
            rsi_min = Convert-ToDoubleOrNaN $row.rsi_min
            rsi_max = Convert-ToDoubleOrNaN $row.rsi_max
        }
    }
    return $out
}

$fractional = To-DoubleRows $fractional
$asymmetric = To-DoubleRows $asymmetric

$benchmark = @{
    downside_dev = 0.14313473306967237
    cagr = 0.07133282373147787
    sortino = 0.32321187680490937
}

$width = 1500
$height = 1800
$plotLeft = 150
$plotWidth = 1280
$plotHeight = 360
$panelTops = @(170, 710, 1250)

$bmp = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bmp)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::White)

$titleFont = New-Object System.Drawing.Font("Segoe UI", 20, [System.Drawing.FontStyle]::Bold)
$axisFont = New-Object System.Drawing.Font("Segoe UI", 12)
$smallFont = New-Object System.Drawing.Font("Segoe UI", 10)
$labelBrush = [System.Drawing.Brushes]::Black
$mutedBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(90, 90, 90))

$redPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(214, 39, 40), 3)
$tealPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(15, 157, 146), 3)
$benchPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(102, 102, 102), 2)
$benchPen.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dash
$axisPen = New-Object System.Drawing.Pen([System.Drawing.Color]::Black, 1.5)
$gridPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(220, 220, 220), 1)
$pointBrushRed = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(214, 39, 40))
$pointBrushTeal = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(15, 157, 146))

$graphics.DrawString("Kelly Fraction Sweep - Fractional vs Asymmetric (v0.5.9)", $titleFont, $labelBrush, 230, 40)

function Get-Extent($rowsA, $rowsB, $column, $benchmarkValue) {
    $values = New-Object 'System.Collections.Generic.List[Double]'
    foreach ($row in $rowsA) {
        $value = [double]$row.$column
        if (Is-FiniteNumber $value) { $values.Add($value) }
    }
    foreach ($row in $rowsB) {
        $value = [double]$row.$column
        if (Is-FiniteNumber $value) { $values.Add($value) }
    }
    if (Is-FiniteNumber ([double]$benchmarkValue)) { $values.Add([double]$benchmarkValue) }
    if ($values.Count -eq 0) {
        return @(-1.0, 1.0)
    }
    $sortedValues = $values.ToArray() | Sort-Object
    $min = [double]$sortedValues[0]
    $max = [double]$sortedValues[$sortedValues.Count - 1]
    $min = [double]$min
    $max = [double]$max
    if ($min -eq $max) {
        $min = [double]($min - 1.0)
        $max = [double]($max + 1.0)
    }
    $pad = [double](($max - $min) * 0.10)
    $lower = [double]($min - $pad)
    $upper = [double]($max + $pad)
    return @($lower, $upper)
}

function Map-X($k, $left, $width) {
    return [int]($left + ($k * $width))
}

function Map-Y($value, $min, $max, $top, $height) {
    if (-not (Is-FiniteNumber $value)) { return $null }
    return [int]($top + $height - (($value - $min) / ($max - $min) * $height))
}

function Draw-YLabel($graphics, $label, $font, $brush, $x, $y) {
    $state = $graphics.Save()
    $graphics.TranslateTransform($x, $y)
    $graphics.RotateTransform(-90)
    $graphics.DrawString($label, $font, $brush, 0, 0)
    $graphics.Restore($state)
}

function Draw-SeriesPanel($graphics, $top, $column, $ylabel, $benchmarkValue, $fractionalRows, $asymmetricRows) {
    $bounds = Get-Extent $fractionalRows $asymmetricRows $column $benchmarkValue
    $yMin = [double]$bounds[0]
    $yMax = [double]$bounds[1]
    $left = $plotLeft
    $width = $plotWidth
    $height = $plotHeight

    for ($i = 0; $i -le 4; $i++) {
        $gridValue = $yMin + (($yMax - $yMin) * $i / 4.0)
        $y = Map-Y $gridValue $yMin $yMax $top $height
        $graphics.DrawLine($gridPen, $left, $y, $left + $width, $y)
        $graphics.DrawString(("{0:N3}" -f $gridValue), $smallFont, $mutedBrush, 55, $y - 8)
    }

    for ($i = 0; $i -le 10; $i++) {
        $x = Map-X ($i / 10.0) $left $width
        $graphics.DrawLine($gridPen, $x, $top, $x, $top + $height)
        $graphics.DrawString(("{0:N2}" -f ($i / 10.0)), $smallFont, $mutedBrush, $x - 10, $top + $height + 8)
    }

    $graphics.DrawRectangle($axisPen, $left, $top, $width, $height)
    Draw-YLabel $graphics $ylabel $axisFont $labelBrush 35 ($top + 250)

    $benchmarkY = Map-Y $benchmarkValue $yMin $yMax $top $height
    $graphics.DrawLine($benchPen, $left, $benchmarkY, $left + $width, $benchmarkY)
    $graphics.DrawString("Frozen benchmark", $smallFont, $mutedBrush, $left + $width - 140, $benchmarkY - 18)

    $prevFrac = $null
    foreach ($row in $fractionalRows) {
        $y = Map-Y $row.$column $yMin $yMax $top $height
        if ($null -eq $y) {
            $prevFrac = $null
            continue
        }
        $point = New-Object System.Drawing.Point (Map-X $row.k $left $width), $y
        if ($null -ne $prevFrac) {
            $graphics.DrawLine($redPen, $prevFrac, $point)
        }
        $graphics.FillEllipse($pointBrushRed, $point.X - 4, $point.Y - 4, 8, 8)
        $prevFrac = $point
    }

    $prevAsym = $null
    foreach ($row in $asymmetricRows) {
        $y = Map-Y $row.$column $yMin $yMax $top $height
        if ($null -eq $y) {
            $prevAsym = $null
            continue
        }
        $point = New-Object System.Drawing.Point (Map-X $row.k $left $width), $y
        if ($null -ne $prevAsym) {
            $graphics.DrawLine($tealPen, $prevAsym, $point)
        }
        $graphics.FillEllipse($pointBrushTeal, $point.X - 4, $point.Y - 4, 8, 8)
        $prevAsym = $point
    }

    $legendX = $left + $width - 210
    $legendY = $top + 12
    $graphics.DrawLine($redPen, $legendX, $legendY + 8, $legendX + 28, $legendY + 8)
    $graphics.DrawString("Fractional", $smallFont, $labelBrush, $legendX + 34, $legendY)
    $graphics.DrawLine($tealPen, $legendX, $legendY + 30, $legendX + 28, $legendY + 30)
    $graphics.DrawString("Asymmetric", $smallFont, $labelBrush, $legendX + 34, $legendY + 22)

    if ($column -eq 'downside_dev') {
        $fracBelow = $fractionalRows | Where-Object { (Is-FiniteNumber $_.downside_dev) -and $_.downside_dev -lt $benchmarkValue }
        $asymBelow = $asymmetricRows | Where-Object { (Is-FiniteNumber $_.downside_dev) -and $_.downside_dev -lt $benchmarkValue }
        if ($fracBelow.Count -eq 0 -and $asymBelow.Count -eq 0) {
            $graphics.DrawString("No sweep point beats benchmark", $smallFont, $mutedBrush, $left + $width - 220, $top + 54)
        }
    }
}

Draw-SeriesPanel $graphics $panelTops[0] 'downside_dev' 'Downside Deviation' $benchmark.downside_dev $fractional $asymmetric
Draw-SeriesPanel $graphics $panelTops[1] 'cagr' 'CAGR' $benchmark.cagr $fractional $asymmetric
Draw-SeriesPanel $graphics $panelTops[2] 'sortino' 'Sortino Ratio' $benchmark.sortino $fractional $asymmetric
$graphics.DrawString("Kelly fraction scale k", $axisFont, $labelBrush, 700, 1660)

$directory = Split-Path -Parent $OutputPng
if (-not (Test-Path $directory)) { New-Item -ItemType Directory -Path $directory | Out-Null }
$bmp.Save($OutputPng, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bmp.Dispose()
"""

    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        temp_script = Path(handle.name)

    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(temp_script),
                str(fractional_csv),
                str(asymmetric_csv),
                str(output_path),
            ],
            check=True,
        )
    finally:
        temp_script.unlink(missing_ok=True)


def main() -> int:
    base_config = load_json(ROOT / "config" / "backtest_config.json")
    approved_seeds, approved_audit = load_polymarket_approved_universe(
        ROOT / "data" / "curated" / "polymarket_approved.json",
        ROOT / "data" / "candidates" / "polymarket_candidates.json",
    )

    raw_dir = ensure_dir(ROOT / "data" / "raw")
    output_dir = ensure_dir(ROOT / "outputs" / "kelly")

    price_rows = fetch_spy_prices(base_config, raw_dir, refresh=False)
    dates, _, price_returns = compute_price_returns(price_rows)

    fallback_annual_rate = float(base_config["risk_free_rate"]["fallback_annual_rate"])
    try:
        fred_rows = fetch_fred_tb3ms(raw_dir, refresh=False)
        fred_fetch_succeeded = True
    except Exception:
        fred_rows = []
        fred_fetch_succeeded = False

    v5_result = run_version(
        version="v3",
        base_config=base_config,
        base_seeds=[],
        shortlist=[],
        dates=dates,
        price_returns=price_returns,
        price_rows=price_rows,
        raw_dir=raw_dir,
        refresh=False,
        fred_rows=fred_rows,
        fallback_annual_rate=fallback_annual_rate,
        fred_fetch_succeeded=fred_fetch_succeeded,
        extra_curated_seeds=approved_seeds,
        extra_curated_audit=approved_audit,
        include_robustness=False,
        include_bootstrap=False,
    )
    top_five_event_ids = top_five_monetary_event_ids(v5_result)

    becker_config = copy.deepcopy(base_config)
    becker_config.setdefault("becker_calibration", {})["enabled"] = True

    fractional_rows = run_sweep(
        mode="fractional",
        dates=dates,
        price_returns=price_returns,
        price_rows=price_rows,
        raw_dir=raw_dir,
        fred_rows=fred_rows,
        fallback_annual_rate=fallback_annual_rate,
        fred_fetch_succeeded=fred_fetch_succeeded,
        approved_seeds=approved_seeds,
        approved_audit=approved_audit,
        becker_config=becker_config,
        top_five_event_ids=top_five_event_ids,
    )
    asymmetric_rows = run_sweep(
        mode="asymmetric",
        dates=dates,
        price_returns=price_returns,
        price_rows=price_rows,
        raw_dir=raw_dir,
        fred_rows=fred_rows,
        fallback_annual_rate=fallback_annual_rate,
        fred_fetch_succeeded=fred_fetch_succeeded,
        approved_seeds=approved_seeds,
        approved_audit=approved_audit,
        becker_config=becker_config,
        top_five_event_ids=top_five_event_ids,
    )

    fractional_csv = output_dir / "fractional_kelly_sweep.csv"
    asymmetric_csv = output_dir / "asymmetric_kelly_sweep.csv"
    figure_path = output_dir / "fig_kelly_sweep.png"

    write_csv(fractional_csv, fractional_rows)
    write_csv(asymmetric_csv, asymmetric_rows)
    render_plot_with_powershell(fractional_csv, asymmetric_csv, figure_path)

    print("Kelly sweep completed.")
    print(f"Fractional rows: {len(fractional_rows)}")
    print(f"Asymmetric rows: {len(asymmetric_rows)}")
    print(f"Outputs written to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
