from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceStatus:
    source: str
    display_name: str
    enabled: bool
    has_credentials: bool
    reachable: bool
    auth_mode: str
    quality_tier: str
    role: str
    notes: str = ""
    market_count: int = 0
    fetched_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceMarket:
    source: str
    market_id: str
    title: str
    url: str
    status: str
    outcome_type: str
    structural_theme: str
    category: str
    current_probability: float | None = None
    volume_usd: float | None = None
    liquidity_usd: float | None = None
    num_traders: int | None = None
    open_time: str | None = None
    close_time: str | None = None
    resolution_time: str | None = None
    raw_category: str = ""
    quality_score: float = 0.0
    source_priority: int = 999
    link_key: str = ""
    matched_terms: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EventFamily:
    event_family_id: str
    title: str
    structural_theme: str
    category: str
    governance_source: str
    proxy_family_id: str
    source_candidates: list[dict[str, Any]] = field(default_factory=list)
    discovered: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SignalSnapshot:
    asof: str
    event_family_id: str
    title: str
    structural_theme: str
    category: str
    selected_source: str
    selected_market_id: str
    selected_probability_raw: float
    selected_probability_governed: float
    quality_score: float
    source_priority: int
    candidate_count: int
    source_options: list[str]
    calibration_applied: str = "none"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RSISnapshot:
    asof: str
    rsi: float
    total_hazard: float
    event_count: int
    dominant_theme: str
    dominant_event_family_id: str
    theme_hazard_shares: dict[str, float]
    signal_count_by_source: dict[str, int]
    events: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
