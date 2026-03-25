from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cassandra_risk.api_service import (
    build_live_signal_artifacts,
    get_event_family_detail,
    list_source_markets,
    registry_meta,
)


class APIServiceTests(unittest.TestCase):
    def test_list_source_markets_filters_and_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
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

    def test_get_event_family_detail_merges_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
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

    def test_registry_meta_summarizes_sources_and_policies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
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

    def test_build_live_signal_artifacts_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
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


if __name__ == "__main__":
    unittest.main()
