from __future__ import annotations

from pathlib import Path

from .source_registry import load_source_registry
from .signal_contract import SignalContract, ensure_signal_contract
from .sources import (
    fetch_kalshi_catalog,
    fetch_manifold_catalog,
    fetch_metaculus_catalog,
    fetch_polymarket_catalog,
)
from .utils import ensure_dir, write_json


ADAPTERS = {
    "metaculus": fetch_metaculus_catalog,
    "kalshi": fetch_kalshi_catalog,
    "polymarket": fetch_polymarket_catalog,
    "manifold": fetch_manifold_catalog,
}


def collect_source_catalogs(root: Path, refresh: bool = False) -> tuple[dict, list[SignalContract], list[dict]]:
    registry = load_source_registry(root)
    raw_dir = ensure_dir(root / "data" / "raw")

    source_status_rows: list[dict] = []
    source_markets: list[SignalContract] = []
    for source_name in registry.get("selection_policy", {}).get("source_priority", []):
        settings = dict(registry.get("sources", {}).get(source_name, {}))
        if not settings.get("enabled", True):
            continue
        adapter = ADAPTERS[source_name]
        markets, status = adapter(settings, raw_dir, refresh=refresh)
        source_status_rows.append(status)
        source_markets.extend(ensure_signal_contract(market) for market in markets)

    source_markets.sort(
        key=lambda contract: (
            contract.structural_theme,
            contract.source.value,
            -float(contract.quality_score or 0.0),
            contract.native_id,
        )
    )
    source_status_rows.sort(key=lambda row: row["source"])
    return registry, source_markets, source_status_rows


def write_source_outputs(root: Path, source_markets: list[SignalContract | dict], source_status_rows: list[dict]) -> None:
    output_dir = ensure_dir(root / "outputs" / "signals")
    serializable = []
    for contract in source_markets:
        typed = ensure_signal_contract(contract)
        serializable.append(typed.to_dict(include_aliases=True))
    write_json(output_dir / "source_markets.json", serializable)
    write_json(output_dir / "source_status.json", source_status_rows)
