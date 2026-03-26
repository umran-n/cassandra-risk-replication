# Cassandra-Risk Closest-Public Replication

This repository implements a closest-public replication of the Cassandra-Risk research program and its governed live signal service.

The implementation is explicit about what comes from the papers, what is recovered from public APIs, and what is reconstructed because the full historical event panel is not publicly available.

## Companion Papers

Paper 1 - Nayani (2026a)  
`Beyond Value-at-Risk: Quantifying Regime Fragility via Prediction Market Event Forecasting`  
DOI: `10.13140/RG.2.2.21272.05124`

Paper 2 - Nayani (2026b)  
`Cassandra-Risk Paper 2: Beyond the Backtest - Expansion, Calibration, and the Boundary Conditions of Forecast-Based Risk Overlays`  
DOI: `10.13140/RG.2.2.17209.12644`  
License: `CC BY-NC-ND 4.0`

Paper 3 - Nayani (2026c)  
`Cassandra-Risk Paper 3: Cross-Platform Prediction Market Ensembles and Governed Signal Infrastructure`  
DOI: `10.13140/RG.2.2.22910.75848`  
License: `CC BY-NC-ND 4.0`  
Status: `PDF archived in repo`  
Code milestone: `v0.6.4-market-ready`

Published PDFs for Papers 1-3 are stored under `paper/pdfs/`.
The current Paper 3 source manuscript draft is `paper/Cassandra_Risk_Paper_3_SSRN_Ready.md`.

## Historical Replication

This repo reproduces the public backtest stack described in Papers 1 and 2.

It:

- downloads `SPY` daily adjusted-close data from Yahoo Finance
- builds a semi-automated Manifold discovery catalog for systemic-risk markets
- recovers approved historical prediction-market series from public APIs
- reconstructs missing historical event histories from paper-explicit dates, peak probabilities, and categories
- runs the major Cassandra backtest, ablation, expansion, calibration, and robustness pipelines

Key historical commands:

```powershell
python scripts/build_manifold_catalog.py --refresh
python scripts/run_backtest.py --refresh
python scripts/run_ablation.py
```

Major artifact directories:

- `outputs/latest/`
- `outputs/ablation/`
- `outputs/expansion/`
- `outputs/becker/`
- `outputs/monte_carlo/`

## Unified Signal API

The repo also includes the live governed signal layer built in Phase 6.

Live source adapters currently cover:

- Metaculus
- Kalshi
- Polymarket
- Manifold

The live signal layer is governed separately from the historical backtest layer:

- governed families come from curated data and the governed registry
- live source markets are linked into those families by explicit market IDs or text similarity
- high-quality unlinked markets are preserved as discovered candidates rather than silently entering the governed RSI
- reviewed promotions are written into `data/governed/signal_registry.json` with a full decision audit

Build the live signal book:

```powershell
python scripts/sync_sources.py --refresh
python scripts/build_signal_book.py --refresh
```

Review and promote discovered candidates from the CLI:

```powershell
python scripts/review_queue.py --theme monetary_policy
```

Serve the local API:

```powershell
python api/app.py --host 127.0.0.1 --port 8765
```

## Current API Surface

Public Tier 1 routes:

- `/health`
- `/v1/meta`
- `/v1/registry/governed`
- `/v1/rsi/latest`
- `/v1/signals/latest`
- `/v1/signals/latest/{event_family_id}`
- `/v1/sources/status`

Operator routes:

- `/v1/meta/registry`
- `/v1/sources/markets`
- `/v1/events/families`
- `/v1/events/families/{event_family_id}`
- `/v1/candidates/discovered`
- `/v1/graph/link-audit`
- `/v1/admin/promotion/queue`
- `/v1/admin/promotion/audit`
- `POST /v1/admin/promotion/decide`
- `POST /v1/admin/promotion/decide/batch`
- `POST /v1/admin/refresh`

Generated live artifacts are written under `outputs/signals/`.
Governed promotion state is written under `data/governed/`.

## Important Caveat

This is not an exact archival replication of the original private Cassandra environment. The papers reference historical prediction-market data and calibration inputs that are not fully published. The repo is therefore explicit about where it is:

- `archive_recovered`
- `manual_reconstructed`
- `live_ingested`

That separation is intentional and part of the governance design documented in Paper 3.
