from __future__ import annotations

from pathlib import Path

from .config import load_json
from .discovery import apply_manual_overlay, build_event_ledger
from .features import compute_feature_panel
from .models import run_analytics
from .reporting import render_report
from .utils import ensure_dir, write_csv, write_json


def _resolve_repo_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _resolve_config_paths(root: Path, config: dict) -> dict:
    updated = dict(config)
    discovery = dict(updated["discovery"])
    discovery["manual_overlay_path"] = str(_resolve_repo_path(root, discovery["manual_overlay_path"]))
    updated["discovery"] = discovery
    outputs = dict(updated["outputs"])
    outputs["latest_dir"] = str(_resolve_repo_path(root, outputs["latest_dir"]))
    updated["outputs"] = outputs
    if updated.get("fixtures", {}).get("path"):
        fixtures = dict(updated["fixtures"])
        fixtures["path"] = str(_resolve_repo_path(root, fixtures["path"]))
        updated["fixtures"] = fixtures
    return updated


def _load_fixture_data(config: dict) -> dict | None:
    fixture_path = config.get("fixtures", {}).get("path")
    if not fixture_path:
        return None
    return load_json(Path(fixture_path))


def run_pipeline(root: Path, config_path: Path, refresh: bool = False) -> dict:
    config = _resolve_config_paths(root, load_json(config_path))
    fixture_data = _load_fixture_data(config)
    raw_dir = ensure_dir(root / "data" / "qca" / "raw")
    output_dir = ensure_dir(Path(config["outputs"]["latest_dir"]))

    if fixture_data and config.get("fixtures", {}).get("disable_discovery"):
        ledger, gap_rows = apply_manual_overlay([], config)
    else:
        ledger, gap_rows = build_event_ledger(config, raw_dir, refresh=refresh)

    updated_ledger, feature_rows, return_rows = compute_feature_panel(
        ledger,
        config,
        raw_dir,
        refresh=refresh,
        fixture_data=fixture_data,
    )
    analytics = run_analytics(
        feature_rows,
        return_rows,
        config,
        raw_dir,
        refresh=refresh,
        fixture_data=fixture_data,
    )

    write_json(output_dir / "summary.json", analytics["summary"])
    write_csv(output_dir / "ledger.csv", updated_ledger)
    write_json(output_dir / "ledger.json", updated_ledger)
    write_csv(output_dir / "gap_report.csv", gap_rows)
    write_csv(output_dir / "feature_panel.csv", feature_rows)
    write_csv(output_dir / "event_returns.csv", return_rows)
    write_csv(output_dir / "model_summaries.csv", analytics["model_summaries"])
    write_csv(output_dir / "coefficients.csv", analytics["coefficient_rows"])
    write_csv(output_dir / "alternative_forms.csv", analytics["alternative_rows"])
    write_csv(output_dir / "robustness.csv", analytics["robustness_rows"])
    write_csv(output_dir / "oos_metrics.csv", analytics["oos_rows"])
    write_csv(output_dir / "coherence.csv", analytics["coherence_rows"])
    write_json(output_dir / "decay_law.json", analytics["decay_law"])
    write_csv(output_dir / "coherence_regimes.csv", analytics["coherence_regimes"])
    write_csv(output_dir / "entanglement.csv", analytics["entanglement_rows"])
    write_csv(output_dir / "tail_screen.csv", analytics["tail_screen_rows"])
    write_csv(output_dir / "contagion_edges.csv", analytics["contagion_edges"])
    render_report(
        output_dir / "report.md",
        summary=analytics["summary"],
        gap_rows=gap_rows,
        model_rows=analytics["model_summaries"],
        oos_rows=analytics["oos_rows"],
        coherence_rows=analytics["coherence_rows"],
        entanglement_rows=analytics["entanglement_rows"],
        contagion_rows=analytics["contagion_edges"],
        tail_screen_rows=analytics["tail_screen_rows"],
    )
    return {"output_dir": str(output_dir), "gap_rows": gap_rows, "summary": analytics["summary"]}
