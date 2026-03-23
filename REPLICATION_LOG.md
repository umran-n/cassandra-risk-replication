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

## V3 Manifold Extension

V3 pivoted fully to Manifold after Metaculus historical export access was unavailable on the tested account.

What changed in V3:

- Search all nine kill-list events through Manifold `/v0/search-markets`
- Recover full bet histories using paginated `fetch_manifold_bets()`
- Replace manual reconstructions only where a defensible pre-event Manifold market existed
- Keep post-event or weak/off-target matches manual to avoid look-ahead bias

Manual events upgraded in V3:

- `oct_selloff_2023` -> `EHCpVy2PXpeA0LdG0jEx`
- `china_taiwan_2024` -> `UjzOb7pBZuVnZvuKzR8n`

Manual events searched but still kept manual:

- `covid_crash_2020`
- `rate_hike_shock_2022`
- `svb_contagion_2023`
- `aug_volatility_2024`
- `eu_banking_contagion_2024`

Headline V3 results:

| Strategy | CAGR | Daily MDD | Monthly MDD | Sortino | Avg Position |
| --- | ---: | ---: | ---: | ---: | ---: |
| Buy & Hold | 13.99% | -33.72% | -23.93% | 0.733 | 100.00% |
| Vol Target | 11.46% | -15.14% | -14.78% | 0.836 | 77.29% |
| Cassandra | 17.84% | -20.27% | -19.67% | 1.296 | 84.09% |

Most important V2 -> V3 shifts:

- Cassandra CAGR fell from `18.84%` to `17.84%`
- Cassandra Sortino fell from `1.366` to `1.296`
- Cassandra average position fell from `87.54%` to `84.09%`
- Drawdown changed little, which suggests the added Manifold replacements mainly reduced over-optimism rather than improving crash capture

Remaining V3 gaps:

- Only two additional manual events were upgraded, so the panel is still materially sparser than the paper's production Dredger universe
- The best SVB-related Manifold candidate was created on `2023-03-11`, after the `2023-03-10` event window, so it was rejected
- Some searches returned weak or off-target results rather than event-aligned markets, especially for `covid_crash_2020` and `eu_banking_contagion_2024`
- Cassandra remains materially above the paper on CAGR and average exposure, which still points to missing false positives and incomplete public event coverage
