from __future__ import annotations

from unittest.mock import patch

import pytest

from cassandra_risk import CassandraClient
from cassandra_risk.exceptions import AuthError, CassandraAPIError, RateLimitError
from cassandra_risk.models import RSIResponse


class MockResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


@patch("requests.Session.get")
def test_health(mock_get):
    mock_get.return_value = MockResponse(200, {"status": "ok", "version": "0.6.4", "timestamp": "2026-04-13T00:00:00Z"})
    client = CassandraClient()
    result = client.health()
    assert result.status == "ok"
    assert result.version == "0.6.4"


@patch("requests.Session.get")
def test_meta(mock_get):
    mock_get.return_value = MockResponse(200, {"version": "0.6.4", "current_rsi": 0.12})
    client = CassandraClient()
    result = client.meta()
    assert result["version"] == "0.6.4"


@patch("requests.Session.get")
def test_rsi_latest(mock_get):
    mock_get.return_value = MockResponse(200, {"asof": "2026-03-26", "rsi": 0.81, "total_hazard": 0.2})
    client = CassandraClient()
    result = client.rsi_latest()
    assert result.value == 0.81
    assert result.regime == "STABLE"


@patch("requests.Session.get")
def test_signals_latest(mock_get):
    mock_get.return_value = MockResponse(
        200,
        [
            {
                "event_family_id": "family-1",
                "title": "Question 1",
                "structural_theme": "geopolitical",
                "selected_source": "polymarket",
                "selected_probability_governed": 0.4,
                "quality_score": 0.7,
            }
        ],
    )
    client = CassandraClient()
    result = client.signals_latest()
    assert len(result) == 1
    assert result[0].contract_id == "family-1"


@patch("requests.Session.get")
def test_signal_by_family(mock_get):
    mock_get.return_value = MockResponse(
        200,
        {
            "event_family_id": "family-1",
            "title": "Question 1",
            "structural_theme": "geopolitical",
            "selected_source": "polymarket",
            "selected_probability_governed": 0.4,
        },
    )
    client = CassandraClient()
    result = client.signal_by_family("family-1")
    assert result.contract_id == "family-1"


@patch("requests.Session.get")
def test_registry_governed(mock_get):
    mock_get.return_value = MockResponse(
        200,
        {
            "count": 1,
            "families": [
                {
                    "event_family_id": "family-1",
                    "title": "Question 1",
                    "structural_theme": "geopolitical",
                    "proxy_family_id": "proxy-1",
                    "governance_source": "signal_registry_bootstrap",
                    "source_candidates": [{"source": "polymarket", "quality_score": 0.5}],
                }
            ],
        },
    )
    client = CassandraClient()
    result = client.registry_governed()
    assert len(result) == 1
    assert result[0].proxy_family_id == "proxy-1"


@patch("requests.Session.get")
def test_sources_status(mock_get):
    mock_get.return_value = MockResponse(
        200,
        [{"source": "polymarket", "reachable": True, "market_count": 10, "fetched_at": "2026-03-26T12:48:29Z"}],
    )
    client = CassandraClient()
    result = client.sources_status()
    assert len(result) == 1
    assert result[0].status == "reachable"


@patch("requests.Session.get")
def test_enterprise_methods(mock_get):
    mock_get.side_effect = [
        MockResponse(200, [{"date": "2026-03-26", "rsi": 0.4, "total_hazard": 0.9}]),
        MockResponse(
            200,
            [{"theme": "geopolitical", "asof": "2026-03-26", "theme_hazard_share": 0.8, "total_hazard": 2.0, "event_count": 3}],
        ),
        MockResponse(
            200,
            [{"date": "2026-03-26", "theme": "geopolitical", "theme_hazard_share": 0.8, "total_hazard": 2.0, "event_count": 3}],
        ),
        MockResponse(
            200,
            [
                {
                    "event_family_id": "family-1",
                    "title": "Question 1",
                    "selected_source": "polymarket",
                    "selected_probability_governed": 0.6,
                    "aggregation_policy": "max",
                }
            ],
        ),
    ]
    client = CassandraClient(enterprise_key="ent-key")
    assert client.rsi_history(days=10)[0].value == 0.4
    assert client.themes_latest()[0].theme == "geopolitical"
    assert client.themes_history(days=10)[0].theme == "geopolitical"
    assert client.families_latest()[0].family_id == "family-1"


@patch("requests.Session.get")
def test_public_auth_error(mock_get):
    mock_get.return_value = MockResponse(401, {"message": "unauthorized"})
    client = CassandraClient()
    with pytest.raises(AuthError):
        client.rsi_latest()


def test_enterprise_key_required():
    client = CassandraClient()
    with pytest.raises(AuthError):
        client.rsi_history()


@patch("requests.Session.get")
def test_rate_limit_error(mock_get):
    mock_get.return_value = MockResponse(429, {"message": "slow down"}, headers={"Retry-After": "60"})
    client = CassandraClient()
    with pytest.raises(RateLimitError) as exc:
        client.rsi_latest()
    assert exc.value.retry_after == "60"


@patch("requests.Session.get")
def test_server_error(mock_get):
    mock_get.return_value = MockResponse(500, {"message": "server exploded"})
    client = CassandraClient()
    with pytest.raises(CassandraAPIError):
        client.rsi_latest()


def test_rsi_response_regime_boundaries():
    assert RSIResponse.from_dict({"rsi": 0.8}).regime == "STABLE"
    assert RSIResponse.from_dict({"rsi": 0.5}).regime == "CAUTIOUS"
    assert RSIResponse.from_dict({"rsi": 0.3}).regime == "FRAGILE"
    assert RSIResponse.from_dict({"rsi": 0.29}).regime == "CRITICAL"
