# Replication Log

## V1 Baseline

Initial closest-public replication using:

- `SPY` adjusted-close data from Yahoo Finance
- Hybrid event panel built from public Manifold recoveries plus paper-based manual reconstructions
- Uniform category lambdas of `0.10`
- Sortino computed against a `0%` risk-free rate
- Drawdown computed from the daily equity curve only

Headline V1 results:

| Strategy | CAGR | Max Drawdown | Sortino | Avg Position |
| --- | ---: | ---: | ---: | ---: |
| Buy & Hold | 13.99% | -33.72% | 1.019 | 100.00% |
| Vol Target | 11.46% | -15.14% | 1.335 | 77.29% |
| Cassandra | 18.75% | -20.19% | 1.789 | 87.41% |

Key V1 finding:

- The replication was directionally useful, but it materially diverged from the paper, especially on Cassandra CAGR, cash usage, and drawdown behavior.

## V2 Fixes

V2 applied three paper-aligned changes:

1. Sortino risk-free rate:
   - Use annualized 3-month T-bill rates when available.
   - In this environment, the live FRED `TB3MS` fetch failed, so the configured fallback of flat `4.31%` annualized was used.
2. Lambda correction in `config/backtest_config.json`:
   - `Kinetic=0.10`
   - `Sovereign=0.15`
   - `Trade=0.12`
   - `Monetary=0.12`
   - `Technology=0.10`
3. Dual MDD reporting:
   - Daily-equity MDD
   - Monthly-resampled MDD

Headline V2 results:

| Strategy | CAGR | Daily MDD | Monthly MDD | Sortino | Avg Position |
| --- | ---: | ---: | ---: | ---: | ---: |
| Buy & Hold | 13.99% | -33.72% | -23.93% | 0.733 | 100.00% |
| Vol Target | 11.46% | -15.14% | -14.78% | 0.836 | 77.29% |
| Cassandra | 18.71% | -20.27% | -19.67% | 1.355 | 87.49% |

Most important V1 -> V2 shifts:

- Sortino fell materially across all strategies once the non-zero risk-free rate was introduced.
- Buy & Hold monthly MDD (`-23.93%`) moved substantially closer to the paper's reported `-25.4%`, supporting the hypothesis that the paper's headline MDD is likely based on monthly resampling rather than daily equity paths.
- Lambda corrections changed Cassandra only modestly in this sparse hybrid event panel, suggesting the remaining divergence is dominated by event-history coverage rather than by these specific decay settings.

## Remaining Gaps After V2

- Buy & Hold still does not match the paper exactly, which suggests differences in baseline construction, sample handling, or aggregation convention.
- Cassandra still runs too much average exposure relative to the paper (`87.49%` here vs `73.00%` in the paper).
- Cassandra CAGR remains far above the paper, implying the public reconstruction still understates false positives and/or overstates the effectiveness of protective events.

## V3 Planned Metaculus Pass

Planned V3 objective:

- Replace as much of the manual reconstructed panel as possible with real Metaculus historical question metadata and probability histories.

Priority data needed from Metaculus:

- Historical question metadata
- Open / close / resolve timestamps
- Resolved outcomes
- Historical probability paths or forecast snapshots over time
- Question identifiers matching the paper's `2020-2025` event set

Expected V3 improvements:

- Lower reliance on manual interpolation
- Better false-positive accounting
- Better Brier-score validation
- More realistic Cassandra exposure path
- Cleaner reconciliation of paper vs replication results

Operational note:

- If direct API access does not expose the full historical paths, a manual export plus API access is still sufficient for a materially stronger V3 pass.
