# cassandra-risk — Python SDK

Python SDK for the Cassandra Risk governed macro-fragility signal API.

## Install

```bash
pip install cassandra-risk
```

## Quickstart

```python
from cassandra_risk import CassandraClient

client = CassandraClient()
rsi = client.rsi_latest()
print("Cassandra Risk — Live RSI")
print(f"RSI: {rsi.value:.4f}")
print(f"Regime: {rsi.regime}")
print(f"Position: {rsi.position_pct:.1f}%")
print(f"Timestamp: {rsi.timestamp}")
```

## Enterprise tier

```python
from cassandra_risk import CassandraClient

client = CassandraClient(enterprise_key="YOUR_ENTERPRISE_KEY")
history = client.rsi_history(days=30)
themes = client.themes_latest()

print(history[-1].regime)
for theme in themes:
    print(theme.theme, theme.hazard_contribution)
```

## Works natively in Databricks notebooks

```python
# Cell 1: Install
# %pip install cassandra-risk

# Cell 2: Free tier — live RSI
from cassandra_risk import CassandraClient
client = CassandraClient()
rsi = client.rsi_latest()
print(f"Live RSI: {rsi.value:.4f} | Regime: {rsi.regime} | Position: {rsi.position_pct:.1f}%")
```

## Available methods

| Method | Tier | Description |
| --- | --- | --- |
| `health()` | Public | Returns service health metadata. |
| `meta()` | Public | Returns API version and headline snapshot metadata. |
| `rsi_latest()` | Public | Returns the latest governed RSI snapshot as a typed model. |
| `signals_latest()` | Public | Returns the current governed signal set. |
| `signal_by_family(family_id)` | Public | Returns one governed signal snapshot by event family. |
| `registry_governed()` | Public | Returns the governed family registry. |
| `sources_status()` | Public | Returns source reachability and sync status. |
| `rsi_history(days=30)` | Enterprise | Returns historical RSI observations. |
| `themes_latest()` | Enterprise | Returns the latest theme-level decomposition. |
| `themes_history(days=30)` | Enterprise | Returns historical theme decomposition rows. |
| `families_latest()` | Enterprise | Returns current family-level breakdown rows. |

## Research backing

- Paper 1: [10.13140/RG.2.2.21272.05124](https://doi.org/10.13140/RG.2.2.21272.05124)
- Paper 2: [10.13140/RG.2.2.17209.12644](https://doi.org/10.13140/RG.2.2.17209.12644)
- Paper 3: [10.13140/RG.2.2.22910.75848](https://doi.org/10.13140/RG.2.2.22910.75848)

MIT License.
