from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from .aggregation_policy import VALID_AGGREGATION_POLICIES, theme_default_aggregation_policy
from .signal_types import SourceMarket
from .source_registry import theme_policy
from .utils import clamp


VALID_THEMES = {
    "monetary_policy",
    "geopolitical",
    "fiscal_debt",
    "electoral",
    "systemic_credit",
    "trade_technology",
}

VALID_PROVENANCE_TIERS = {
    "paper_seeded",
    "archive_recovered",
    "live_ingested",
}

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Source(str, Enum):
    POLYMARKET = "polymarket"
    KALSHI = "kalshi"
    METACULUS = "metaculus"
    MANIFOLD = "manifold"


def coerce_source(value: str | Source) -> Source:
    if isinstance(value, Source):
        return value
    lowered = str(value or "").strip().lower()
    for source in Source:
        if source.value == lowered:
            return source
    raise ValueError(f"Unsupported source: {value}")


def _parse_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return date.fromisoformat(text[:10])
    normalized = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date()


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if value in (None, ""):
        return datetime.now(timezone.utc).replace(microsecond=0)
    text = str(value).strip()
    normalized = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_date(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _format_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_probability(value: float | None) -> float | None:
    if value is None:
        return None
    return clamp(float(value), 0.0, 1.0)


def _macro_relevance_score(question_text: str, structural_theme: str) -> float:
    text = question_text.lower()
    base = {
        "monetary_policy": 0.55,
        "geopolitical": 0.55,
        "fiscal_debt": 0.5,
        "systemic_credit": 0.5,
        "trade_technology": 0.45,
        "electoral": 0.35,
    }.get(structural_theme, 0.25)
    keywords = {
        "monetary_policy": ["fed", "rate", "fomc", "ecb", "cpi", "inflation", "cut", "hike"],
        "geopolitical": ["war", "strike", "ceasefire", "iran", "israel", "ukraine", "taiwan", "nato", "military"],
        "fiscal_debt": ["debt", "default", "shutdown", "treasury", "ceiling", "bond"],
        "systemic_credit": ["bank", "credit", "svb", "contagion", "liquidity"],
        "trade_technology": ["tariff", "sanction", "chips", "crypto", "sec", "ai"],
        "electoral": ["election", "president", "senate", "house", "prime minister", "ballot"],
    }
    hits = sum(1 for keyword in keywords.get(structural_theme, []) if keyword in text)
    return min(base + 0.1 * hits, 1.0)


@dataclass
class SignalContract:
    contract_id: str
    source: Source
    provenance_tier: str
    question_text: str
    structural_theme: str
    proxy_family_id: str | None
    aggregation_policy: str
    probability_raw: float | None
    probability_calibrated: float | None
    efficiency_gap_applied: float
    created_at: date | str | None
    resolves_at: date | str | None
    resolved_outcome: bool | None
    volume_usd: float
    quality_score: float
    is_binary: bool
    is_macro_relevant: bool
    last_updated: datetime | str
    snapshot_timestamp: datetime | str
    category: str = ""
    native_id: str = ""
    url: str = ""
    status: str = ""
    liquidity_usd: float | None = None
    num_traders: int | None = None
    raw_category: str = ""
    source_priority: int = 999
    link_key: str = ""
    matched_terms: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    link_score: float = 0.0
    link_type: str = ""
    event_family_id: str = ""
    governance_source: str = ""
    discovered: bool = False
    notes: str = ""
    theme_bucket_selected: bool = True
    theme_bucket_drop_reason: str = ""
    calibration_applied: str = "none"
    theme_cap_applied: bool = False
    theme_cap_scale: float = 1.0

    def __post_init__(self) -> None:
        self.source = coerce_source(self.source)
        self.native_id = str(self.native_id or self.contract_id.split("::", 1)[1] if "::" in self.contract_id else "")
        self.contract_id = str(self.contract_id or f"{self.source.value}::{self.native_id}")
        if self.contract_id != f"{self.source.value}::{self.native_id}":
            raise ValueError(f"contract_id must be '{self.source.value}::native_id', got {self.contract_id!r}")

        self.provenance_tier = str(self.provenance_tier or "").strip()
        if self.provenance_tier not in VALID_PROVENANCE_TIERS:
            raise ValueError(f"Invalid provenance_tier: {self.provenance_tier}")

        self.structural_theme = str(self.structural_theme or "").strip()
        if self.structural_theme not in VALID_THEMES:
            raise ValueError(f"Invalid structural_theme: {self.structural_theme}")

        self.aggregation_policy = str(self.aggregation_policy or theme_default_aggregation_policy(self.structural_theme)).strip()
        if self.aggregation_policy not in VALID_AGGREGATION_POLICIES:
            raise ValueError(f"Invalid aggregation_policy: {self.aggregation_policy}")

        self.probability_raw = _coerce_probability(self.probability_raw)
        self.probability_calibrated = _coerce_probability(self.probability_calibrated if self.probability_calibrated is not None else self.probability_raw)
        self.efficiency_gap_applied = max(float(self.efficiency_gap_applied or 0.0), 0.0)
        if self.efficiency_gap_applied == 0.0 and self.probability_raw is not None:
            self.probability_calibrated = self.probability_raw

        self.created_at = _parse_date(self.created_at)
        self.resolves_at = _parse_date(self.resolves_at)
        if self.resolved_outcome not in (True, False, None):
            raise ValueError("resolved_outcome must be True, False, or None")

        self.volume_usd = max(float(self.volume_usd or 0.0), 0.0)
        self.quality_score = clamp(float(self.quality_score or 0.0), 0.0, 1.0)
        self.liquidity_usd = None if self.liquidity_usd is None else max(float(self.liquidity_usd), 0.0)
        self.last_updated = _parse_datetime(self.last_updated)
        self.snapshot_timestamp = _parse_datetime(self.snapshot_timestamp)
        self.theme_cap_scale = float(self.theme_cap_scale or 1.0)
        self.link_score = max(float(self.link_score or 0.0), 0.0)
        self.category = str(self.category or "")
        self.question_text = str(self.question_text or "").strip()
        self.status = str(self.status or "")
        self.matched_terms = [str(term) for term in self.matched_terms]
        self.metadata = dict(self.metadata or {})
        if self.created_at is not None and self.resolves_at is not None and self.resolves_at < self.created_at:
            self.metadata.setdefault("temporal_warning", "created_at_after_resolves_at")
            self.created_at = None

    @property
    def market_id(self) -> str:
        return self.native_id

    @property
    def title(self) -> str:
        return self.question_text

    @property
    def current_probability(self) -> float | None:
        return self.probability_raw

    @property
    def open_time(self) -> str | None:
        return _format_date(self.created_at)

    @property
    def close_time(self) -> str | None:
        return _format_date(self.resolves_at)

    @property
    def resolution_time(self) -> str | None:
        return _format_date(self.resolves_at)

    @property
    def outcome_type(self) -> str:
        return "BINARY" if self.is_binary else "OTHER"

    def with_updates(self, **kwargs: Any) -> "SignalContract":
        return replace(self, **kwargs)

    def to_dict(self, include_aliases: bool = False) -> dict[str, Any]:
        payload = {
            "contract_id": self.contract_id,
            "source": self.source.value,
            "provenance_tier": self.provenance_tier,
            "question_text": self.question_text,
            "structural_theme": self.structural_theme,
            "proxy_family_id": self.proxy_family_id,
            "aggregation_policy": self.aggregation_policy,
            "probability_raw": self.probability_raw,
            "probability_calibrated": self.probability_calibrated,
            "efficiency_gap_applied": self.efficiency_gap_applied,
            "created_at": _format_date(self.created_at),
            "resolves_at": _format_date(self.resolves_at),
            "resolved_outcome": self.resolved_outcome,
            "volume_usd": self.volume_usd,
            "quality_score": self.quality_score,
            "is_binary": self.is_binary,
            "is_macro_relevant": self.is_macro_relevant,
            "last_updated": _format_datetime(self.last_updated),
            "snapshot_timestamp": _format_datetime(self.snapshot_timestamp),
            "category": self.category,
            "native_id": self.native_id,
            "url": self.url,
            "status": self.status,
            "liquidity_usd": self.liquidity_usd,
            "num_traders": self.num_traders,
            "raw_category": self.raw_category,
            "source_priority": self.source_priority,
            "link_key": self.link_key,
            "matched_terms": list(self.matched_terms),
            "metadata": dict(self.metadata),
            "link_score": self.link_score,
            "link_type": self.link_type,
            "event_family_id": self.event_family_id,
            "governance_source": self.governance_source,
            "discovered": self.discovered,
            "notes": self.notes,
            "theme_bucket_selected": self.theme_bucket_selected,
            "theme_bucket_drop_reason": self.theme_bucket_drop_reason,
            "calibration_applied": self.calibration_applied,
            "theme_cap_applied": self.theme_cap_applied,
            "theme_cap_scale": self.theme_cap_scale,
        }
        if include_aliases:
            payload.update(
                {
                    "market_id": self.native_id,
                    "title": self.question_text,
                    "current_probability": self.probability_raw,
                    "open_time": _format_date(self.created_at),
                    "close_time": _format_date(self.resolves_at),
                    "resolution_time": _format_date(self.resolves_at),
                    "outcome_type": self.outcome_type,
                    "selected_probability_raw": self.probability_raw,
                    "selected_probability_governed": self.probability_calibrated,
                }
            )
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SignalContract":
        source = coerce_source(payload.get("source") or "")
        native_id = str(payload.get("native_id") or payload.get("market_id") or "")
        return cls(
            contract_id=str(payload.get("contract_id") or f"{source.value}::{native_id}"),
            source=source,
            provenance_tier=str(payload.get("provenance_tier") or ("archive_recovered" if source is Source.MANIFOLD else "live_ingested")),
            question_text=str(payload.get("question_text") or payload.get("title") or ""),
            structural_theme=str(payload.get("structural_theme") or ""),
            proxy_family_id=payload.get("proxy_family_id"),
            aggregation_policy=str(payload.get("aggregation_policy") or theme_default_aggregation_policy(str(payload.get("structural_theme") or ""))),
            probability_raw=payload.get("probability_raw", payload.get("current_probability")),
            probability_calibrated=payload.get("probability_calibrated", payload.get("selected_probability_governed", payload.get("probability_raw", payload.get("current_probability")))),
            efficiency_gap_applied=float(payload.get("efficiency_gap_applied") or 0.0),
            created_at=payload.get("created_at", payload.get("open_time")),
            resolves_at=payload.get("resolves_at", payload.get("resolution_time", payload.get("close_time"))),
            resolved_outcome=payload.get("resolved_outcome"),
            volume_usd=float(payload.get("volume_usd") or 0.0),
            quality_score=float(payload.get("quality_score") or 0.0),
            is_binary=bool(payload.get("is_binary", str(payload.get("outcome_type") or "BINARY").upper() == "BINARY")),
            is_macro_relevant=bool(payload.get("is_macro_relevant", False)),
            last_updated=payload.get("last_updated") or payload.get("snapshot_timestamp") or _utc_now_iso(),
            snapshot_timestamp=payload.get("snapshot_timestamp") or payload.get("last_updated") or _utc_now_iso(),
            category=str(payload.get("category") or ""),
            native_id=native_id,
            url=str(payload.get("url") or ""),
            status=str(payload.get("status") or ""),
            liquidity_usd=payload.get("liquidity_usd"),
            num_traders=payload.get("num_traders"),
            raw_category=str(payload.get("raw_category") or ""),
            source_priority=int(payload.get("source_priority") or 999),
            link_key=str(payload.get("link_key") or ""),
            matched_terms=list(payload.get("matched_terms") or []),
            metadata=dict(payload.get("metadata") or {}),
            link_score=float(payload.get("link_score") or 0.0),
            link_type=str(payload.get("link_type") or ""),
            event_family_id=str(payload.get("event_family_id") or ""),
            governance_source=str(payload.get("governance_source") or ""),
            discovered=bool(payload.get("discovered", False)),
            notes=str(payload.get("notes") or ""),
            theme_bucket_selected=bool(payload.get("theme_bucket_selected", True)),
            theme_bucket_drop_reason=str(payload.get("theme_bucket_drop_reason") or ""),
            calibration_applied=str(payload.get("calibration_applied") or "none"),
            theme_cap_applied=bool(payload.get("theme_cap_applied", False)),
            theme_cap_scale=float(payload.get("theme_cap_scale") or 1.0),
        )


def ensure_signal_contract(value: SignalContract | dict[str, Any]) -> SignalContract:
    if isinstance(value, SignalContract):
        return value
    return SignalContract.from_dict(dict(value))


class ContractNormaliser(ABC):
    @abstractmethod
    def normalise(self, market: SourceMarket | dict[str, Any], registry: dict | None = None) -> SignalContract:
        raise NotImplementedError


class DefaultContractNormaliser(ContractNormaliser):
    def normalise(self, market: SourceMarket | dict[str, Any], registry: dict | None = None) -> SignalContract:
        market_obj = SourceMarket(**market) if isinstance(market, dict) else market
        policy = theme_policy(registry or {}, market_obj.structural_theme) if registry else {}
        aggregation_policy = str(policy.get("aggregation_policy") or theme_default_aggregation_policy(market_obj.structural_theme))
        probability_raw = market_obj.current_probability
        probability_calibrated = probability_raw
        snapshot_timestamp = _utc_now_iso()
        return SignalContract(
            contract_id=f"{market_obj.source}::{market_obj.market_id}",
            source=coerce_source(market_obj.source),
            provenance_tier="archive_recovered" if market_obj.source == "manifold" else "live_ingested",
            question_text=market_obj.title,
            structural_theme=market_obj.structural_theme,
            proxy_family_id=None,
            aggregation_policy=aggregation_policy,
            probability_raw=probability_raw,
            probability_calibrated=probability_calibrated,
            efficiency_gap_applied=0.0,
            created_at=market_obj.open_time,
            resolves_at=market_obj.resolution_time or market_obj.close_time,
            resolved_outcome=None,
            volume_usd=float(market_obj.volume_usd or 0.0),
            quality_score=float(market_obj.quality_score or 0.0),
            is_binary=str(market_obj.outcome_type).upper() == "BINARY",
            is_macro_relevant=_macro_relevance_score(market_obj.title, market_obj.structural_theme) >= 0.55,
            last_updated=snapshot_timestamp,
            snapshot_timestamp=snapshot_timestamp,
            category=market_obj.category,
            native_id=market_obj.market_id,
            url=market_obj.url,
            status=market_obj.status,
            liquidity_usd=market_obj.liquidity_usd,
            num_traders=market_obj.num_traders,
            raw_category=market_obj.raw_category,
            source_priority=market_obj.source_priority,
            link_key=market_obj.link_key,
            matched_terms=list(market_obj.matched_terms),
            metadata=dict(market_obj.metadata),
        )
