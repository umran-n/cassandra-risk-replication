from __future__ import annotations

from dataclasses import dataclass, field


def _as_float(value, default=0.0) -> float:
    if value in (None, ""):
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value, default=0) -> int:
    if value in (None, ""):
        return int(default)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _as_list(value) -> list:
    return list(value) if isinstance(value, list) else []


@dataclass
class RSIResponse:
    value: float
    timestamp: str
    regime_label: str
    hazard_mass: float
    position_pct: float

    @classmethod
    def from_dict(cls, d: dict) -> "RSIResponse":
        value = _as_float(d.get("value", d.get("rsi")))
        timestamp = str(d.get("timestamp") or d.get("asof") or d.get("date") or "")
        regime_label = str(d.get("regime_label") or d.get("dominant_theme") or "")
        hazard_mass = _as_float(d.get("hazard_mass", d.get("total_hazard")))
        position_pct = _as_float(d.get("position_pct"), default=value * 100.0)
        return cls(
            value=value,
            timestamp=timestamp,
            regime_label=regime_label,
            hazard_mass=hazard_mass,
            position_pct=position_pct,
        )

    @property
    def regime(self) -> str:
        if self.value >= 0.8:
            return "STABLE"
        elif self.value >= 0.5:
            return "CAUTIOUS"
        elif self.value >= 0.3:
            return "FRAGILE"
        else:
            return "CRITICAL"


@dataclass
class SignalContract:
    contract_id: str
    source: str
    question_text: str
    structural_theme: str
    proxy_family_id: str
    probability_calibrated: float
    weight: float
    hazard_contribution: float
    resolves_at: str
    provenance_tier: str

    @classmethod
    def from_dict(cls, d: dict) -> "SignalContract":
        contract_id = str(d.get("contract_id") or d.get("event_family_id") or "")
        source = str(d.get("source") or d.get("selected_source") or "")
        if not source:
            source_options = _as_list(d.get("source_options"))
            source = str(source_options[0]) if source_options else ""
        question_text = str(d.get("question_text") or d.get("title") or d.get("dominant_event_question") or "")
        structural_theme = str(d.get("structural_theme") or d.get("theme") or "")
        proxy_family_id = str(d.get("proxy_family_id") or contract_id)
        probability_calibrated = _as_float(d.get("probability_calibrated", d.get("selected_probability_governed")))
        weight = _as_float(d.get("weight", d.get("quality_score", d.get("selected_quality_score"))))
        hazard_contribution = _as_float(d.get("hazard_contribution", d.get("total_hazard")))
        resolves_at = str(d.get("resolves_at") or d.get("resolution_date") or d.get("asof") or d.get("date") or "")
        provenance_tier = str(
            d.get("provenance_tier")
            or d.get("governance_source")
            or d.get("approval_status")
            or ("governed" if contract_id else "")
        )
        return cls(
            contract_id=contract_id,
            source=source,
            question_text=question_text,
            structural_theme=structural_theme,
            proxy_family_id=proxy_family_id,
            probability_calibrated=probability_calibrated,
            weight=weight,
            hazard_contribution=hazard_contribution,
            resolves_at=resolves_at,
            provenance_tier=provenance_tier,
        )


@dataclass
class ThemeSignal:
    theme: str
    weight: float
    probability: float
    hazard_contribution: float
    contract_count: int
    timestamp: str

    @classmethod
    def from_dict(cls, d: dict) -> "ThemeSignal":
        families = _as_list(d.get("families"))
        probabilities = [
            _as_float(family.get("selected_probability_governed"))
            for family in families
            if family.get("selected_probability_governed") not in (None, "")
        ]
        probability = _as_float(d.get("probability"))
        if not probability and probabilities:
            probability = sum(probabilities) / len(probabilities)
        return cls(
            theme=str(d.get("theme") or ""),
            weight=_as_float(d.get("weight", d.get("theme_hazard_share"))),
            probability=probability,
            hazard_contribution=_as_float(d.get("hazard_contribution", d.get("total_hazard"))),
            contract_count=_as_int(d.get("contract_count", d.get("event_count", len(families)))),
            timestamp=str(d.get("timestamp") or d.get("asof") or d.get("date") or ""),
        )


@dataclass
class FamilySignal:
    family_id: str
    contracts: list[SignalContract] = field(default_factory=list)
    aggregate_probability: float = 0.0
    aggregation_policy: str = ""
    timestamp: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "FamilySignal":
        raw_contracts = _as_list(d.get("contracts"))
        contracts = [SignalContract.from_dict(item) for item in raw_contracts]
        if not contracts and any(
            key in d for key in ("selected_source", "selected_probability_governed", "title", "selected_market_id")
        ):
            contracts = [SignalContract.from_dict(d)]
        aggregate_probability = _as_float(d.get("aggregate_probability", d.get("selected_probability_governed")))
        if not aggregate_probability and contracts:
            aggregate_probability = sum(contract.probability_calibrated for contract in contracts) / len(contracts)
        return cls(
            family_id=str(d.get("family_id") or d.get("event_family_id") or ""),
            contracts=contracts,
            aggregate_probability=aggregate_probability,
            aggregation_policy=str(d.get("aggregation_policy") or "max"),
            timestamp=str(d.get("timestamp") or d.get("asof") or d.get("date") or ""),
        )


@dataclass
class RegistryEntry:
    contract_id: str
    source: str
    question_text: str
    structural_theme: str
    proxy_family_id: str
    quality_score: float
    gates_passed: list[str] = field(default_factory=list)
    provenance_tier: str = ""
    decided_at: str = ""
    decision_reason: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "RegistryEntry":
        source_candidates = _as_list(d.get("source_candidates"))
        first_candidate = source_candidates[0] if source_candidates else {}
        gates_passed = d.get("gates_passed")
        if not isinstance(gates_passed, list):
            gates_passed = [str(gates_passed)] if gates_passed not in (None, "") else []
        return cls(
            contract_id=str(d.get("contract_id") or d.get("event_family_id") or ""),
            source=str(d.get("source") or first_candidate.get("source") or ""),
            question_text=str(d.get("question_text") or d.get("title") or first_candidate.get("title") or ""),
            structural_theme=str(d.get("structural_theme") or d.get("theme") or ""),
            proxy_family_id=str(d.get("proxy_family_id") or d.get("event_family_id") or ""),
            quality_score=_as_float(d.get("quality_score", first_candidate.get("quality_score"))),
            gates_passed=gates_passed,
            provenance_tier=str(d.get("provenance_tier") or d.get("governance_source") or d.get("approval_status") or ""),
            decided_at=str(d.get("decided_at") or ""),
            decision_reason=str(d.get("decision_reason") or d.get("approval_reason") or d.get("notes") or ""),
        )


@dataclass
class HealthResponse:
    status: str
    version: str
    timestamp: str

    @classmethod
    def from_dict(cls, d: dict) -> "HealthResponse":
        return cls(
            status=str(d.get("status") or ""),
            version=str(d.get("version") or ""),
            timestamp=str(d.get("timestamp") or ""),
        )


@dataclass
class SourceStatus:
    source: str
    status: str
    last_sync: str
    contract_count: int

    @classmethod
    def from_dict(cls, d: dict) -> "SourceStatus":
        reachable = d.get("reachable")
        status = d.get("status")
        if not status:
            status = "reachable" if reachable else "unreachable"
        return cls(
            source=str(d.get("source") or ""),
            status=str(status),
            last_sync=str(d.get("last_sync") or d.get("fetched_at") or ""),
            contract_count=_as_int(d.get("contract_count", d.get("market_count"))),
        )
