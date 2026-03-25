# Cassandra-Risk Closest-Public Replication

This repository implements a closest-public replication of the backtest described in:

`Beyond Value-at-Risk: Quantifying Regime Fragility via Large Language Model Event Forecasting`

The implementation is explicit about what comes from the paper, what is recovered from public APIs, and what is manually reconstructed because the paper does not publish the full historical event panel.

## Companion Papers

Paper 1 — Nayani (2026a)  
`Beyond Value-at-Risk: Quantifying Regime Fragility via Prediction Market Event Forecasting`  
DOI: `10.13140/RG.2.2.21272.05124`

Paper 2 — Nayani (2026b)  
`Cassandra-Risk Paper 2: Beyond the Backtest — Expansion, Calibration, and the Boundary Conditions of Forecast-Based Risk Overlays`  
DOI: `10.13140/RG.2.2.17209.12644`  
License: `CC BY-NC-ND 4.0`

## What this run does

- Downloads `SPY` daily adjusted-close data from Yahoo Finance.
- Builds a semi-automated Manifold discovery catalog for systemic-risk markets.
- Recovers approved historical prediction-market series from the public Manifold API.
- Reconstructs the missing historical event panel from paper-explicit dates, peak probabilities, and categories.
- Runs three strategies over `2020-01-01` to `2025-01-10`:
  - Buy & Hold
  - Volatility Targeting
  - Cassandra-Risk
- Produces normalized event histories, equity curves, portfolio metrics, bootstrap confidence intervals, Brier scores, event analysis, and a replication-gap report.

## Important caveat

This is not an exact paper replication. The paper references archived 2020-2022 prediction-market histories and a fuller calibrated parameter set that are not fully published in the document. This repo therefore uses a hybrid event panel:

- `archive_recovered`: directly recovered from public Manifold market histories
- `manual_reconstructed`: rebuilt from paper tables and examples

## Run

```powershell
python scripts/build_manifold_catalog.py --refresh
python scripts/run_backtest.py --refresh
python scripts/run_ablation.py
```

Catalog artifacts are written under `data/processed/` and `outputs/latest/`.
Backtest outputs are written under `outputs/latest/`.
Ablation summaries, report artifacts, and figure PNGs are written under `outputs/ablation/`.

Approved Manifold markets live in `data/curated/manifold_shortlist.json`.
Review overrides live in `data/curated/manifold_overrides.json`.

## Unified Signal API

The repo now includes a unified signal foundation that normalizes live source catalogs from:

- Metaculus
- Kalshi
- Polymarket
- Manifold

The live signal layer is governed separately from the historical backtest layer:

- governed families come from the checked-in curated universe and seed files
- live source markets are linked into those families by explicit market IDs or text similarity
- high-quality unlinked markets are preserved as discovered candidates rather than silently entering the governed RSI
- the current live engine applies the validated monetary Becker rule plus the current theme caps
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

Serve it as a local API:

```powershell
python api/app.py --host 127.0.0.1 --port 8765
```

Available endpoints:

- `/health`
- `/v1/meta/registry`
- `/v1/sources/status`
- `/v1/sources/markets`
- `/v1/events/families`
- `/v1/events/families/{event_family_id}`
- `/v1/candidates/discovered`
- `/v1/signals/latest`
- `/v1/signals/latest/{event_family_id}`
- `/v1/rsi/latest`
- `/v1/graph/link-audit`
- `/v1/admin/promotion/queue`
- `/v1/admin/promotion/audit`
- `POST /v1/admin/promotion/decide`
- `POST /v1/admin/promotion/decide/batch`
- `POST /v1/admin/refresh`

Generated outputs are written under `outputs/signals/`.
Governed promotion state is written under `data/governed/`.
