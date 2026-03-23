# Cassandra-Risk Closest-Public Replication

This repository implements a closest-public replication of the backtest described in:

`Beyond Value-at-Risk: Quantifying Regime Fragility via Large Language Model Event Forecasting`

The implementation is explicit about what comes from the paper, what is recovered from public APIs, and what is manually reconstructed because the paper does not publish the full historical event panel.

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
```

Catalog artifacts are written under `data/processed/` and `outputs/latest/`.
Backtest outputs are written under `outputs/latest/`.

Approved Manifold markets live in `data/curated/manifold_shortlist.json`.
Review overrides live in `data/curated/manifold_overrides.json`.
