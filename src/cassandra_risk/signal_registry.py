from __future__ import annotations

from collections import defaultdict

from .signal_contract import SignalContract, ensure_signal_contract


class SignalRegistry:
    def __init__(self) -> None:
        self._families: dict[str, list[SignalContract]] = defaultdict(list)

    def add(self, contract: SignalContract | dict) -> None:
        typed = ensure_signal_contract(contract)
        family_id = typed.proxy_family_id or typed.event_family_id or typed.contract_id
        self._families[family_id].append(typed)

    def get_families(self) -> list[dict]:
        families: list[dict] = []
        for family_id, contracts in sorted(self._families.items()):
            families.append(
                {
                    "proxy_family_id": family_id,
                    "contracts": [contract.to_dict(include_aliases=True) for contract in contracts],
                    "sources": sorted({contract.source.value for contract in contracts}),
                }
            )
        return families
