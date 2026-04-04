from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from cassandra_risk.api_service import (
    build_live_signal_artifacts,
    get_event_family_detail,
    list_family_breakdown,
    list_latest_theme_decomposition,
    list_rsi_history,
    list_source_markets,
    list_theme_decomposition_history,
    registry_meta,
)


def _workspace_tempdir() -> Path:
    root = Path(__file__).resolve().parents[1] / ".tmp_tests"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"service_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class APIServiceTests(unittest.TestCase):
    def test_list_source_markets_filters_and_limits(self) -> None:
        root = _workspace_tempdir()
        try:
            output_dir = root / "outputs" / "signals"
            output_dir.mkdir(parents=True, exist_ok=True)
            payload = [
                {"source": "polymarket", "structural_theme": "geopolitical", "status": "open", "quality_score": 0.9, "market_id": "a"},
                {"source": "polymarket", "structural_theme": "monetary_policy", "status": "open", "quality_score": 0.8, "market_id": "b"},
                {"source": "kalshi", "structural_theme": "geopolitical", "status": "closed", "quality_score": 0.95, "market_id": "c"},
            ]
            (output_dir / "source_markets.json").write_text(json.dumps(payload), encoding="utf-8")

            rows = list_source_markets(root, source="polymarket", theme="geopolitical", status="open", min_quality=0.85, limit=1)
            self.assertEqual(1, len(rows))
            self.assertEqual("a", rows[0]["market_id"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_get_event_family_detail_merges_artifacts(self) -> None:
        root = _workspace_tempdir()
        try:
            output_dir = root / "outputs" / "signals"
            output_dir.mkdir(parents=True, exist_ok=True)
            event_family_id = "geo_family_1"
            (output_dir / "canonical_event_families.json").write_text(
                json.dumps([{"event_family_id": event_family_id, "linked_markets": [{"market_id": "m1"}]}]),
                encoding="utf-8",
            )
            (output_dir / "family_signal_book.json").write_text(
                json.dumps([{"event_family_id": event_family_id, "selection_state": "selected"}]),
                encoding="utf-8",
            )
            (output_dir / "signal_snapshots.json").write_text(
                json.dumps([{"event_family_id": event_family_id, "selected_source": "polymarket"}]),
                encoding="utf-8",
            )
            (output_dir / "link_audit.json").write_text(
                json.dumps([{"event_family_id": event_family_id, "link_status": "explicit_market_id"}]),
                encoding="utf-8",
            )

            detail = get_event_family_detail(root, event_family_id)
            assert detail is not None
            self.assertEqual(event_family_id, detail["event_family_id"])
            self.assertEqual("selected", detail["summary"]["selection_state"])
            self.assertEqual("polymarket", detail["snapshot"]["selected_source"])
            self.assertEqual(1, len(detail["link_audit"]))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_registry_meta_summarizes_sources_and_policies(self) -> None:
        root = _workspace_tempdir()
        try:
            config_dir = root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            registry = {
                "sources": {
                    "polymarket": {
                        "display_name": "Polymarket",
                        "enabled": True,
                        "priority": 3,
                        "quality_tier": "B",
                        "role": "liquidity_coverage",
                        "auth_mode": "public",
                    }
                },
                "theme_policies": {"geopolitical": {"bucket_cap": 0.25}},
                "selection_policy": {"minimum_quality_score": 0.4},
            }
            (config_dir / "source_registry.json").write_text(json.dumps(registry), encoding="utf-8")

            meta = registry_meta(root)
            self.assertEqual("polymarket", meta["sources"][0]["source"])
            self.assertEqual(0.25, meta["theme_policies"]["geopolitical"]["bucket_cap"])
            self.assertEqual(0.4, meta["selection_policy"]["minimum_quality_score"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_build_live_signal_artifacts_writes_outputs(self) -> None:
        root = _workspace_tempdir()
        try:
            with (
                patch("cassandra_risk.api_service.collect_source_catalogs") as collect,
                patch("cassandra_risk.api_service.write_source_outputs") as write_outputs,
                patch("cassandra_risk.api_service.load_governed_event_families") as load_families,
                patch("cassandra_risk.api_service.build_event_graph") as build_graph,
                patch("cassandra_risk.api_service.build_signal_book") as build_book,
            ):
                collect.return_value = (
                    {"theme_policies": {}, "selection_policy": {}},
                    [{"source": "polymarket", "market_id": "m1"}],
                    [{"source": "polymarket", "reachable": True, "market_count": 1, "notes": ""}],
                )
                load_families.return_value = [{"event_family_id": "f1"}]
                build_graph.return_value = ([{"event_family_id": "f1", "linked_markets": []}], [{"event_family_id": "f1"}])
                build_book.return_value = (
                    [{"event_family_id": "f1", "selection_state": "selected", "discovered": False}],
                    [{"event_family_id": "f1", "structural_theme": "geopolitical", "selected_source": "polymarket", "selected_probability_governed": 0.4, "calibration_applied": "none"}],
                    {"rsi": 0.5, "total_hazard": 1.0, "dominant_theme": "geopolitical", "dominant_event_family_id": "f1"},
                )

                payload = build_live_signal_artifacts(root, refresh=True)

            self.assertEqual(0.5, payload["rsi_snapshot"]["rsi"])
            self.assertTrue((root / "outputs" / "signals" / "family_signal_book.json").exists())
            self.assertTrue((root / "outputs" / "signals" / "signal_summary.md").exists())
            write_outputs.assert_called_once()
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_list_rsi_history_filters_by_date_and_limit(self) -> None:
        root = _workspace_tempdir()
        try:
            latest_dir = root / "outputs" / "latest"
            latest_dir.mkdir(parents=True, exist_ok=True)
            (latest_dir / "daily_rsi_decomposition.csv").write_text(
                "\n".join(
                    [
                        "date,total_hazard,rsi,rsi_drag,active_event_count,dominant_event_id,dominant_category,dominant_theme,probability_component_hazard,severity_component_hazard,velocity_component_hazard,persistence_component_hazard,probability_share_of_hazard,severity_share_of_hazard,velocity_share_of_hazard,persistence_share_of_hazard",
                        "2026-03-24,1.2,0.9,0.1,2,event_a,Kinetic,geopolitical,0.1,0.3,0.4,0.4,0.1,0.25,0.33,0.33",
                        "2026-03-25,2.4,0.7,0.3,3,event_b,Monetary,monetary_policy,0.2,0.6,0.7,0.9,0.08,0.25,0.29,0.38",
                    ]
                ),
                encoding="utf-8",
            )
            rows = list_rsi_history(root, start="2026-03-25", limit=1)
            self.assertEqual(1, len(rows))
            self.assertEqual("2026-03-25", rows[0]["date"])
            self.assertEqual("event_b", rows[0]["dominant_event_id"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_list_theme_decomposition_history_aggregates_by_theme(self) -> None:
        root = _workspace_tempdir()
        try:
            latest_dir = root / "outputs" / "latest"
            latest_dir.mkdir(parents=True, exist_ok=True)
            (latest_dir / "hazard_attribution.csv").write_text(
                "\n".join(
                    [
                        "date,event_id,category,structural_theme,question,event_probability,hazard_contribution,theme_hazard_share",
                        "2026-03-24,event_a,Kinetic,geopolitical,Question A,0.5,2.0,0.8",
                        "2026-03-24,event_b,Kinetic,geopolitical,Question B,0.4,1.0,0.8",
                        "2026-03-24,event_c,Monetary,monetary_policy,Question C,0.2,0.5,0.2",
                    ]
                ),
                encoding="utf-8",
            )
            rows = list_theme_decomposition_history(root, start="2026-03-24", end="2026-03-24")
            self.assertEqual(2, len(rows))
            self.assertEqual("geopolitical", rows[0]["theme"])
            self.assertEqual(3.0, rows[0]["total_hazard"])
            self.assertEqual("event_a", rows[0]["dominant_event_id"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_list_latest_theme_decomposition_groups_current_events(self) -> None:
        root = _workspace_tempdir()
        try:
            output_dir = root / "outputs" / "signals"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "rsi_snapshot.json").write_text(
                json.dumps(
                    {
                        "asof": "2026-03-26",
                        "theme_hazard_shares": {"geopolitical": 0.75, "monetary_policy": 0.25},
                        "events": [
                            {
                                "event_family_id": "geo_family",
                                "title": "Geo event",
                                "structural_theme": "geopolitical",
                                "category": "Kinetic",
                                "source": "polymarket",
                                "market_id": "m1",
                                "selected_probability_governed": 0.8,
                                "hazard_contribution": 3.0,
                                "theme_cap_applied": True,
                                "calibration_applied": "none",
                            },
                            {
                                "event_family_id": "mon_family",
                                "title": "Mon event",
                                "structural_theme": "monetary_policy",
                                "category": "Monetary",
                                "source": "polymarket",
                                "market_id": "m2",
                                "selected_probability_governed": 0.3,
                                "hazard_contribution": 1.0,
                                "theme_cap_applied": False,
                                "calibration_applied": "becker",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (output_dir / "signal_snapshots.json").write_text(
                json.dumps(
                    [
                        {"event_family_id": "geo_family", "quality_score": 0.7, "candidate_count": 2, "source_options": ["polymarket"]},
                        {"event_family_id": "mon_family", "quality_score": 0.8, "candidate_count": 1, "source_options": ["polymarket"]},
                    ]
                ),
                encoding="utf-8",
            )
            rows = list_latest_theme_decomposition(root)
            self.assertEqual(2, len(rows))
            self.assertEqual("geopolitical", rows[0]["theme"])
            self.assertEqual("geo_family", rows[0]["dominant_event_family_id"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_list_family_breakdown_merges_summary_snapshot_and_canonical(self) -> None:
        root = _workspace_tempdir()
        try:
            output_dir = root / "outputs" / "signals"
            output_dir.mkdir(parents=True, exist_ok=True)
            family_id = "geo_family"
            (output_dir / "family_signal_book.json").write_text(
                json.dumps(
                    [
                        {
                            "event_family_id": family_id,
                            "title": "Geo family",
                            "structural_theme": "geopolitical",
                            "category": "Kinetic",
                            "selection_state": "selected",
                            "discovered": False,
                            "governance_source": "signal_registry",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (output_dir / "canonical_event_families.json").write_text(
                json.dumps([{"event_family_id": family_id, "linked_markets": [{"market_id": "m1"}]}]),
                encoding="utf-8",
            )
            (output_dir / "signal_snapshots.json").write_text(
                json.dumps(
                    [
                        {
                            "event_family_id": family_id,
                            "selected_source": "polymarket",
                            "selected_market_id": "m1",
                            "selected_probability_governed": 0.8,
                            "selected_probability_raw": 0.82,
                            "quality_score": 0.75,
                            "candidate_count": 3,
                            "source_options": ["polymarket"],
                            "calibration_applied": "none",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            rows = list_family_breakdown(root, selection_state="selected")
            self.assertEqual(1, len(rows))
            self.assertEqual("polymarket", rows[0]["selected_source"])
            self.assertEqual(1, rows[0]["linked_market_count"])
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
