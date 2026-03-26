from __future__ import annotations

from pathlib import Path

from .signal_contract import SignalContract, ensure_signal_contract


class RSIEngine:
    def compute(
        self,
        contracts: list[SignalContract | dict],
        registry: dict,
        root: Path,
        asof_date: str | None = None,
    ) -> dict:
        from .signal_engine import build_rsi_snapshot

        typed_contracts = [ensure_signal_contract(contract) for contract in contracts]
        return build_rsi_snapshot(typed_contracts, registry, root, asof_date=asof_date)
