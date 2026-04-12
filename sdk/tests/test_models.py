from cassandra_risk.models import FamilySignal, RegistryEntry, RSIResponse, SignalContract, SourceStatus, ThemeSignal


def test_signal_contract_from_snapshot_dict():
    item = SignalContract.from_dict(
        {
            "event_family_id": "family-1",
            "title": "Question 1",
            "structural_theme": "geopolitical",
            "selected_source": "polymarket",
            "selected_probability_governed": 0.7,
            "quality_score": 0.6,
            "asof": "2026-03-26",
        }
    )
    assert item.contract_id == "family-1"
    assert item.question_text == "Question 1"
    assert item.probability_calibrated == 0.7


def test_theme_signal_from_enterprise_dict():
    item = ThemeSignal.from_dict(
        {
            "theme": "geopolitical",
            "asof": "2026-03-26",
            "theme_hazard_share": 0.9,
            "total_hazard": 4.2,
            "event_count": 2,
            "families": [
                {"selected_probability_governed": 0.8},
                {"selected_probability_governed": 0.4},
            ],
        }
    )
    assert item.theme == "geopolitical"
    assert round(item.probability, 2) == 0.6
    assert item.contract_count == 2


def test_family_signal_from_breakdown_dict():
    item = FamilySignal.from_dict(
        {
            "event_family_id": "family-1",
            "title": "Question 1",
            "selected_source": "polymarket",
            "selected_probability_governed": 0.55,
            "aggregation_policy": "max",
        }
    )
    assert item.family_id == "family-1"
    assert item.aggregate_probability == 0.55
    assert len(item.contracts) == 1


def test_registry_entry_from_governed_registry():
    item = RegistryEntry.from_dict(
        {
            "event_family_id": "family-1",
            "title": "Question 1",
            "structural_theme": "geopolitical",
            "proxy_family_id": "proxy-1",
            "governance_source": "signal_registry_bootstrap",
            "approval_reason": "Approved",
            "source_candidates": [{"source": "polymarket", "quality_score": 0.8}],
        }
    )
    assert item.contract_id == "family-1"
    assert item.source == "polymarket"
    assert item.decision_reason == "Approved"


def test_source_status_from_live_status():
    item = SourceStatus.from_dict(
        {"source": "polymarket", "reachable": True, "market_count": 25, "fetched_at": "2026-03-26T12:48:29Z"}
    )
    assert item.status == "reachable"
    assert item.contract_count == 25


def test_rsi_response_from_live_snapshot():
    item = RSIResponse.from_dict({"asof": "2026-03-26", "rsi": 0.42, "total_hazard": 1.23})
    assert item.timestamp == "2026-03-26"
    assert item.position_pct == 42.0
