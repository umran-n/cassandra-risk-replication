# Beyond Value-at-Risk: Cassandra-Risk as a Forward-Looking Regime Fragility Overlay

## Preprint Draft

Author metadata, affiliation, and contact details to be added before submission.

Draft date: 2026-03-25

Code and public replication package: [https://github.com/umran-n/cassandra-risk-replication](https://github.com/umran-n/cassandra-risk-replication)
Referenced public replication tag: `v0.4.0-ablation`

## Abstract

Classical market risk controls such as realized volatility targeting and Value-at-Risk are inherently backward-looking. They respond to price movement that has already occurred, and they are therefore slow precisely when regime breaks matter most. This paper proposes Cassandra-Risk, a forward-looking risk overlay that converts forecasted event probabilities into a continuous Regime Stress Index (RSI) and uses that signal to modulate equity exposure. The framework is designed as insurance rather than as a claim of unconditional alpha: it seeks to reduce exposure when event-driven fragility rises, while explicitly accounting for the false-positive cost of precaution through a measurable Paranoia Tax.

This preprint presents both the framework and a closest-public replication package built from daily SPY data, public Manifold market histories, and documented manual reconstructions where the original production event histories are unavailable. The replication now includes: a Manifold discovery and curation pipeline, event-level shortlist governance, paper-aligned risk-free and lambda fixes, daily and monthly max-drawdown reporting, a formal aggregation policy for multi-proxy events, and a theme-aware ablation harness. Under the current public configuration, Cassandra-Risk over 2020-01-01 through 2025-01-10 delivers a CAGR of 15.99%, daily max drawdown of -20.27%, monthly max drawdown of -19.67%, and Sortino ratio of 1.159, versus 13.99%, -33.72%, -23.93%, and 0.733 for buy-and-hold, and 11.46%, -15.14%, -14.78%, and 0.836 for volatility targeting.

The central result is not that the public reconstruction exactly reproduces the production paper. It does not. The central result is that a forward-looking event overlay remains directionally compelling under degraded public-data conditions, while the public replication makes the remaining gaps explicit. The Phase 4 ablations sharpen this claim: removing all manual events drops Sortino to 0.521, but removing either `ukraine_invasion_2022` or `us_debt_ceiling_2023` does not collapse the strategy, and the strongest isolated theme, `systemic_credit`, retains a Sortino of 1.150 on its own. Taken together, these results support Cassandra-Risk as a credible working-paper contribution while leaving open the stronger questions of structural alpha and exact production replication.

**Keywords:** risk management, regime shifts, prediction markets, drawdown control, volatility targeting, event-driven investing

**JEL Classification (suggested):** G11, G17, C53

## 1. Introduction

Risk management tends to fail in the same way alpha models fail: by being too attached to the last regime. Measures derived from recent returns are valuable for sizing and for portfolio hygiene, but they are reactive by construction. In tranquil periods they can understate latent fragility; in crisis periods they can de-risk only after damage is already visible in price space. Cassandra-Risk is motivated by the proposition that some classes of fragility are forecastable in event space before they are fully visible in realized volatility.

The key idea is simple. Instead of asking only how much the market has moved, we also ask what classes of destabilizing events the forecasting ecosystem currently considers plausible. Forecast probabilities for war escalation, sovereign stress, trade shocks, monetary tightening, and technology-linked fragility are mapped into a common hazard language. That hazard is transformed into an RSI, and the portfolio's position is set equal to the RSI. When event-space fragility rises, exposure falls.

This paper makes three contributions.

1. It presents Cassandra-Risk as a conceptually coherent forward-looking risk overlay rather than a collection of ad hoc crisis flags.
2. It provides a public replication package that documents exactly what can and cannot be reconstructed from public data.
3. It introduces operational governance refinements that emerged from the replication process itself: an ex ante Paranoia Tax budget, live forecast-quality monitoring, a formal rule for aggregating multiple approved proxies for the same event, and a structural-theme ablation harness that makes robustness claims auditable.

The V1 claim is intentionally modest. The evidence here supports the view that Cassandra-Risk is a serious and testable research framework. It does not yet support claims of exact replication, proven structural alpha, or complete production readiness.

## 2. Conceptual Frame

### 2.1 From realized risk to forecasted fragility

The framework begins from a practical observation: many of the events that damage portfolios are preceded by publicly visible argument, disagreement, and probabilistic repricing. Market volatility notices the aftermath. Forecasting markets, crowd probabilities, and event narratives often notice the buildup earlier. Cassandra-Risk attempts to convert that buildup into a disciplined portfolio governor.

### 2.2 Insurance rather than prediction

The correct framing is insurance. Cassandra-Risk is not presented as a machine that forecasts the future perfectly. It is a framework that spends exposure to buy protection against regime fragility. The relevant trade-off is therefore not only return, but return conditional on downside risk and false-positive drag. This is why the Paranoia Tax matters. A risk overlay that never reduces exposure is useless, but one that de-risks constantly becomes a tax on compounding. The right question is whether the insurance spend is bounded, governed, and worth paying.

### 2.3 Reflexivity and bounded adoption

Any successful risk overlay invites reflexivity. If too many allocators act on the same de-risking protocol, the protocol can become part of the instability it aims to manage. The original Cassandra paper framed this as a Soros Bound, with viable aggregate adoption constrained to `A_viable <= 0.15`. This V1 draft keeps that reflexivity concern explicit and adds a second layer of operational self-throttling based on forecast quality and insurance-budget exhaustion.

## 3. Framework

### 3.1 Event taxonomy

The public Cassandra implementation uses five hazard classes plus a null bucket:

- `Kinetic`
- `Sovereign`
- `Trade`
- `Monetary`
- `Technology`
- `None`

The current public reconstruction uses the following category weights:

| Category | Weight |
| --- | ---: |
| Kinetic | 10.0 |
| Sovereign | 8.0 |
| Trade | 6.0 |
| Monetary | 5.0 |
| Technology | 3.0 |
| None | 0.0 |

The current public reconstruction uses the following decay parameters:

| Category | Lambda |
| --- | ---: |
| Kinetic | 0.10 |
| Sovereign | 0.15 |
| Trade | 0.12 |
| Monetary | 0.12 |
| Technology | 0.10 |
| None | 0.00 |

For empirical analysis, however, these raw hazard categories are not sufficient on their own. In particular, the public `Sovereign` bucket mixes fiscal/debt events with systemic-credit events, which makes direct category ablations analytically ambiguous. The public package therefore introduces a second taxonomy layer, `structural_theme`, used for robustness analysis and governance reporting.

| Structural Theme | Typical Events |
| --- | --- |
| `geopolitical` | Ukraine invasion, China-Taiwan escalation, Middle East proxies |
| `monetary_policy` | Fed tightening, higher-for-longer scares, FOMC shock proxies |
| `fiscal_debt` | Debt ceiling, sovereign default, rating-event proxies |
| `electoral` | US and major international election shocks |
| `systemic_credit` | COVID panic as credit/liquidity stress, SVB, Credit Suisse, banking contagion |
| `trade_technology` | Trade wars, sanctions, export controls, tech-regulation shocks |

In the current public event universe, `Sovereign` events are split between `fiscal_debt` and `systemic_credit` at the event-definition layer. This refinement is important because the ablation results reported below would otherwise be testing the wrong boundaries.

### 3.2 Hazard and RSI

For each event `e` active on date `t`, Cassandra computes:

`H_e,t = omega_e * d_e,t * P_e,t`

where:

- `omega_e` is the category weight
- `d_e,t = exp(-lambda_e * tau_e,t / 30)` is the horizon-scaled decay term
- `tau_e,t` is days to resolution, bounded below by 1
- `P_e,t` is the event probability on day `t`

Aggregate hazard is:

`H_t = sum_e H_e,t`

The Regime Stress Index is then:

`RSI_t = 1 / (1 + H_t)`

The public backtest sets the portfolio position equal to `RSI_t`, with no leverage and a 5 bps trading-cost penalty on position changes.

### 3.3 Multi-proxy aggregation policy

One of the most important findings of the public replication concerns how to combine multiple approved proxies for the same event. The initial public implementation used an inverse-Brier weighted average:

`P_e,t = sum_j w_j p_j,t / sum_j w_j`, with `w_j = 1 / Brier_j`

That rule is reasonable only when the proxies are effectively nested or highly correlated measurements of the same underlying proposition. It is not the right rule when the proxies are temporally misaligned or dimensionally orthogonal.

The public replication surfaced exactly this problem in three events:

- `us_debt_ceiling_2023`
- `oct_selloff_2023`
- `china_taiwan_2024`

For debt-ceiling and October 2023 stress, averaging materially diluted a strong live warning from one proxy with a weak or differently structured reading from another. The adopted V1 policy is therefore:

- Use `max` aggregation for temporally misaligned or orthogonally dimensioned proxies:
  `P_e,t = max_j(p_j,t)`
- Reserve inverse-Brier weighted averaging for genuinely nested or correlated proxies.

This policy is now implemented in the public codebase via `cassandra.multi_proxy_aggregation`, with `max` set as the active configuration.

## 4. Public Replication Architecture

### 4.1 Scope

The public replication targets the paper's main SPY backtest over `2020-01-01` through `2025-01-10`. The portfolio rules are:

- Universe: `SPY`
- Frequency: daily
- Execution: end-of-day close
- Return series: adjusted close, dividends reinvested
- Leverage: none
- Cash return: 0% in V1 baseline; excess-return metrics in later passes use 3-month T-bill convention
- Trading cost: 5 bps per position change

Benchmarks:

- Buy & Hold: fully invested at all times
- Volatility Targeting: `position_t = min(1, 0.12 / rolling_21d_vol_t)`
- Cassandra-Risk: `position_t = RSI_t`

### 4.2 Data sources

The public package uses:

- Yahoo Finance SPY daily data
- Manifold public API for market discovery and bet-history recovery
- FRED `TB3MS` for the 3-month T-bill series when available, with a fallback flat annualized rate of 4.31%
- Manual reconstructions where public historical event paths could not be recovered

An authenticated Metaculus API was tested during the replication process, but the available access tier did not expose the historical data needed for this project. The public package therefore pivoted fully to Manifold for the V3 and V4 passes.

### 4.3 Curated Manifold dredger

The current public pipeline is no longer just a seed file. It contains a semi-automated discovery and curation workflow:

- deterministic query expansion by hazard class and known event aliases
- Manifold `/v0/search-markets` discovery
- bet-history recovery for candidate markets
- candidate normalization and scoring
- deterministic override rules
- a checked-in shortlist of approved markets

The current catalog results are:

| Item | Count |
| --- | ---: |
| Search queries | 34 |
| Total in-window candidates | 48 |
| Approved | 7 |
| Pending | 2 |
| Rejected | 39 |

### 4.4 Current event-universe coverage

The current public event-universe status is:

| Event | Status | Public State |
| --- | --- | --- |
| `covid_crash_2020` | manual retained | no approved public candidate |
| `ukraine_invasion_2022` | approved | 1 Manifold proxy |
| `rate_hike_shock_2022` | manual retained | no approved public candidate |
| `svb_contagion_2023` | pending | 2 candidate proxies held for created-date verification |
| `us_debt_ceiling_2023` | approved | 2 Manifold proxies |
| `oct_selloff_2023` | approved | 2 Manifold proxies |
| `china_taiwan_2024` | approved | 2 Manifold proxies |
| `aug_volatility_2024` | manual retained | no approved public candidate |
| `eu_banking_contagion_2024` | manual retained | current top candidate rejected as off-target |

Thus, five event definitions still rely directly on paper/manual seeds, while four event families have approved Manifold coverage.

## 5. Experimental Design

### 5.1 Anti-overfitting structure

The public work preserves the paper's basic temporal discipline:

- `2020-2022`: calibration and event-panel formation
- `2023`: threshold and decay sanity checks
- `2024-2025`: out-of-sample evaluation

This does not eliminate all model risk, but it does explicitly reject crisis cherry-picking and forward leakage.

### 5.2 Replication chronology

The public package evolved through a series of explicit replication passes.

| Pass | Main Change | Cassandra CAGR | Cassandra Sortino | Avg Position |
| --- | --- | ---: | ---: | ---: |
| V1 baseline | 0% risk-free, uniform lambdas, sparse hybrid panel | 16.01% | 1.601 | 78.59% |
| V2 fixes | T-bill Sortino convention, paper lambdas, monthly MDD | 15.99% | 1.159 | 78.72% |
| V3 Manifold pivot | Manifold-first public recovery | 15.99% | 1.159 | 78.72% |
| V4 shortlist dredger | 48-candidate catalog with explicit approvals/rejections | 15.99% | 1.159 | 78.72% |
| Final V1 policy | `max` multi-proxy aggregation for orthogonal/misaligned proxies | 15.99% | 1.159 | 78.72% |

The most important point is not the label sequence. It is that the framework remained directionally stable while the public reconstruction became less discretionary and more auditable.

### 5.3 Ablation design

The current public package now includes a dedicated ablation harness designed to answer a narrower question than the headline backtest: is the result coming from a single event, a single aggregation convention, or a broader structure in the event set?

The Phase 4 ablation suite runs five families of checks:

1. `no_manual_events`: remove all manual/paper reconstructions and retain only approved public proxies.
2. Top-event removal: rerun after removing `ukraine_invasion_2022`, then rerun after removing `us_debt_ceiling_2023`.
3. Aggregation-policy head-to-head: force global `max`, force global `weighted_average`, and compare both with the current per-family governance policy.
4. Structural-theme isolation: run the backtest with only one `structural_theme` active at a time.
5. Single-proxy versus combined-proxy runs for events with multiple approved public proxies.

For the last class of runs, the dominant proxy is defined deterministically as the proxy with the highest cumulative hazard contribution in the Phase 3 hazard-attribution output.

## 6. Results

### 6.1 Headline results

Under the current public V1 configuration, the main backtest produces:

| Metric | Buy & Hold | Vol Target | Cassandra |
| --- | ---: | ---: | ---: |
| CAGR | 13.99% | 11.46% | 15.99% |
| Total Return | 92.73% | 72.22% | 110.31% |
| Volatility | 20.97% | 12.09% | 14.43% |
| Daily Max Drawdown | -33.72% | -15.14% | -20.27% |
| Monthly Max Drawdown | -23.93% | -14.78% | -19.67% |
| Downside Deviation | 15.13% | 8.80% | 10.06% |
| CVaR 95% | -3.18% | -1.81% | -2.12% |
| Sharpe | 0.730 | 0.958 | 1.101 |
| Sortino | 0.733 | 0.836 | 1.159 |
| Calmar | 0.415 | 0.757 | 0.789 |
| Average Position | 100.00% | 77.29% | 78.72% |
| Days in 90% Cash | 0 | 0 | 5 |
| Max Consecutive Cash Days | 0 | 0 | 4 |

The most robust public observation is that Cassandra exhibits the highest realized Sortino ratio among the three strategies. In practical terms, it delivered the strongest return per unit of downside risk in this sample.

### 6.2 Comparison with paper targets

The public replication does not exactly match the original paper's headline figures. The current comparison is:

| Metric | Paper Buy & Hold | Public Buy & Hold | Paper Cassandra | Public Cassandra |
| --- | ---: | ---: | ---: | ---: |
| CAGR | 12.30% | 13.99% | 10.90% | 15.99% |
| Monthly MDD | -25.40% | -23.93% | -14.10% | -19.67% |
| Sortino | 0.61 | 0.733 | 0.92 | 1.159 |
| Average Position | 100.00% | 100.00% | 73.00% | 78.72% |
| Paranoia Tax | n/a | n/a | -1.20% | +2.00% |

Two conclusions follow.

1. The public replication is directionally supportive of the framework.
2. It still overstates public Cassandra performance relative to the paper, especially on CAGR and cash usage.

The most plausible explanation is incomplete public event coverage rather than arithmetic error. This interpretation is strengthened by the fact that even the buy-and-hold baseline differs from the paper, while Cassandra remains systematically too invested.

### 6.3 Drawdowns and the monthly MDD issue

One of the useful discoveries of the replication process was methodological rather than strategic. The buy-and-hold daily max drawdown is `-33.72%`, but the monthly-resampled max drawdown is `-23.93%`, much closer to the paper's `-25.4%`. This strongly suggests that the paper's headline MDD likely corresponds to a monthly rather than a daily drawdown convention.

The public package now reports both.

### 6.4 Event examples

The current event-level analysis shows the framework behaving most plausibly in the following episodes:

- `ukraine_invasion_2022`: high hazard, deep de-risking, meaningful avoidance of subsequent market damage
- `oct_selloff_2023`: sharp hazard escalation around a higher-for-longer scare, followed by a large exposure cut
- `us_debt_ceiling_2023`: a large false positive that de-risked heavily without a true crash, illustrating the insurance-cost problem directly

This combination of correct warnings and costly false positives is exactly why governance matters.

### 6.5 Bootstrap uncertainty

The current block-bootstrap results remain wide, which is appropriate for a short regime-rich sample. For Cassandra, the current 95% intervals are:

- CAGR: `4.37%` to `30.19%`
- Max drawdown: `-29.3%` to `-9.9%`
- Sharpe: `0.362` to `1.932`
- Sortino: `0.108` to `2.460`

These intervals do not invalidate the framework, but they do reinforce that this is still a working paper, not a final proof.

### 6.6 Ablation evidence and robustness checks

The ablation harness materially improves what can be claimed from the public package. It shows both where the current signal is robust and where it still depends on incomplete public coverage. The manuscript table below reports the highest-signal subset of runs, while the full ablation matrix is preserved in the public artifact set.

Selected ablation results are:

| Run | CAGR | Sortino | Daily MDD | Interpretation |
| --- | ---: | ---: | ---: | --- |
| `aggregation_per_family` | 15.99% | 1.159 | -20.27% | current public baseline |
| `no_manual_events` | 10.30% | 0.521 | -33.72% | public-only panel is currently too sparse |
| `top_event_removal_ukraine` | 16.53% | 1.203 | -18.39% | result does not collapse when Ukraine is removed |
| `top_event_removal_debt_ceiling` | 16.28% | 1.180 | -20.27% | result does not collapse when debt ceiling is removed |
| `aggregation_max` | 15.99% | 1.159 | -20.27% | forced global `max` |
| `aggregation_weighted_average` | 15.95% | 1.155 | -20.27% | forced global weighted average |
| `theme_systemic_credit_only` | 17.69% | 1.150 | -24.50% | strongest isolated structural theme |
| `theme_geopolitical_only` | 11.35% | 0.584 | -33.72% | isolated geopolitical theme is insufficient on its own |

Three conclusions are important.

1. The current public result is not reducible to a single flagship event. Removing either `ukraine_invasion_2022` or `us_debt_ceiling_2023` does not collapse downside-adjusted performance.
2. The current public result is still materially dependent on hybrid coverage. When all manual events are removed, performance degrades sharply, which quantifies the present cost of incomplete public archives. Relative to the current per-family baseline, the `no_manual_events` run loses 0.638 Sortino points; this is a useful first public estimate of how much the present hybrid panel still depends on human/manual reconstruction.
3. Aggregation policy matters less at the whole-portfolio level than it did at the individual-event level. Forced `max` and forced `weighted_average` differ by only 0.004 Sortino points in the current sample, suggesting that the governance value of the policy is interpretability and correctness at the event level rather than headline-metric rescue.

The structural-theme runs are also informative. `systemic_credit` is the strongest isolated theme in the current public universe, retaining a Sortino of 1.150 on its own. By contrast, the public `electoral` bucket is currently empty and therefore reproduces a near buy-and-hold path; this should be interpreted as a coverage gap rather than as evidence that electoral risk is irrelevant.

The single-proxy runs add a final nuance. Keeping only the dominant `china_taiwan_2024` proxy modestly improves Sortino to 1.175, while keeping only the dominant `oct_selloff_2023` proxy reduces Sortino to 1.143. This is exactly the kind of asymmetry the governance layer is meant to expose: some event families benefit from proxy plurality, while others are cleaner when a single dominant market carries the signal.

## 7. Interpretation of the Public Evidence

### 7.1 What it shows

- A forward-looking event overlay can generate meaningfully different exposure paths from both buy-and-hold and volatility targeting.
- The framework remains attractive on downside-adjusted metrics even under degraded public-data conditions.
- The signal survives multiple implementation refinements rather than collapsing once arithmetic and convention choices are corrected.
- The current public signal is not reducible to a single event, since top-event removals do not collapse performance in the ablation harness.

### 7.2 What it does not show

- It does not prove structural alpha.
- It does not prove exact replication of the original production Cassandra system.
- It does not justify production autonomy without governance.
- It does not show that the current public-only event panel is sufficient; the `no_manual_events` ablation demonstrates that it is not.

The strongest defensible statement is therefore:

Even under degraded public-data conditions, Cassandra-Risk maintained a higher realized Sortino ratio than both buy-and-hold and volatility targeting across successive public replication passes, suggesting that its downside-management effect is directionally robust. That is not the same thing as proving structural alpha.

## 8. Governance and Deployment

### 8.1 The Paranoia Tax as an ex ante budget

The Paranoia Tax should not remain a purely ex post descriptive statistic. It should be formalized as a deployment budget.

Define trailing 12-month insurance drag as:

`Pi_t^12m = R_base,t^12m - R_RSI,t^12m`

where `R_base,t^12m` is the trailing return of the unmodified base strategy and `R_RSI,t^12m` is the trailing return of the RSI-governed strategy.

The deployment rule is:

`Pi_t^12m <= Pi*`

where `Pi*` is the maximum tolerable insurance spend approved in advance. If this threshold is breached, the framework must narrow the approved event universe, raise trigger thresholds, or shift from automatic execution to human approval.

### 8.2 Live forecast-quality monitoring

Historical validation is necessary but not sufficient. In production, Cassandra should monitor rolling:

- Brier score
- calibration error
- resolved-question coverage

If forecast quality drifts outside predefined bounds, automatic de-risking authority should be suspended and the system should revert to advisory status pending review.

This matters because a model can have acceptable portfolio PnL for the wrong reasons. The risk framework must therefore be governed by signal quality, not by outcome luck alone.

### 8.3 Operational self-throttling

Reflexivity constraints and forecast-quality constraints should both limit deployment. In practice, the effective operational adoption rate should be bounded by the minimum of:

- reflexivity viability
- forecast-quality viability
- remaining Paranoia Tax budget

This creates a useful symmetry: Cassandra is meant to detect fragility in the market, but it must also detect fragility in its own epistemic process.

## 9. Limitations

The public replication has real limitations, and they matter.

1. The production Cassandra system is broader than the public replication. The live Dredger is intended to ingest a much larger, continuously refreshed event universe than the current public shortlist.
2. Metaculus historical access was not available in a usable public form during this replication cycle, which forced a Manifold-only pivot for recoverable forecast histories.
3. Five of nine event definitions still depend on paper/manual reconstruction rather than approved public market histories.
4. The public Brier diagnostics are weak. In the current mixed public panel, the aggregated public forecast Brier score is worse than a naive 50/50 baseline, and the manual reconstructions are materially worse than the Manifold subset. This should not be hidden. It is a direct signal that the current public panel remains an imperfect proxy for the intended production forecasting universe.
5. The public implementation still runs too much exposure relative to the paper and therefore likely understates false-positive drag.
6. The structural-theme analysis is only as good as current event coverage. In particular, the public `electoral` theme is presently unpopulated and should be interpreted as a missing-data bucket rather than as a validated null result.

These limitations are serious, but they do not reduce the work to noise. They define the next research agenda.

## 10. Next Research Steps

The most important next steps are:

1. Acquire richer historical forecast histories, especially from Metaculus or comparable archival sources.
2. Expand the shortlist-driven Dredger beyond the current 9-event public panel.
3. Improve event de-duplication and classification so proxy approval becomes less artisanal over time.
4. Extend the new ablation harness across a larger event universe, especially once electoral and systemic-credit coverage are less sparse.
5. Operate the framework in paper-trading or shadow mode with live forecast-quality monitoring.

In other words, the framework has moved beyond initial plausibility testing and into the more demanding phase of industrialization, governance, and forward validation.

## 11. Conclusion

Cassandra-Risk starts from a premise that remains compelling after public replication: regime fragility often becomes visible in event space before it is fully visible in realized volatility. A risk overlay that listens to that event space can plausibly reduce downside pain more efficiently than backward-looking controls alone.

The public evidence here is encouraging but incomplete. Cassandra-Risk, as currently reconstructed, beats buy-and-hold and volatility targeting on realized Sortino over the sample, while operating at materially lower average exposure than buy-and-hold. At the same time, the public reconstruction still overstates performance relative to the original paper and remains constrained by sparse public event coverage.

That is exactly why this is an appropriate preprint rather than a final canonical version. The framework is coherent, the package is reproducible, the limitations are explicit, and the next research steps are clear. That is sufficient for a serious public release.

## Code and Data Availability

The public replication package, scripts, configuration files, selection audits, and generated artifacts are available at:

[https://github.com/umran-n/cassandra-risk-replication](https://github.com/umran-n/cassandra-risk-replication)

The repository tag referenced in this draft is `v0.4.0-ablation`, which captures the Phase 4 structural-theme and ablation-harness milestone.

Key public artifacts currently included in the repository:

- `outputs/latest/report.md`
- `outputs/latest/selection_audit.csv`
- `outputs/latest/catalog_summary.json`
- `outputs/latest/v1_v2_v3_paper_comparison.csv`
- `outputs/latest/multi_proxy_aggregation_comparison.csv`
- `outputs/latest/multi_proxy_aggregation_summary.json`
- `outputs/ablation/ablation_summary.csv`
- `outputs/ablation/ablation_report.md`
- `outputs/ablation/fig1_sortino_comparison.png`
- `outputs/ablation/fig2_theme_isolation.png`
- `outputs/ablation/fig3_proxy_delta.png`
- `REPLICATION_LOG.md`

## References

- Federal Reserve Bank of St. Louis, FRED. 3-Month Treasury Bill: Secondary Market Rate (`TB3MS`).
- Manifold Markets API documentation and public market histories.
- Yahoo Finance historical SPY adjusted-close data.
- Public replication repository for this paper: [https://github.com/umran-n/cassandra-risk-replication](https://github.com/umran-n/cassandra-risk-replication)
- Metaculus API documentation reviewed during replication, though historical archive access was not available for this pass.

## Appendix A: Public Aggregation Diagnostics

The final aggregation policy was motivated by concrete empirical cases.

For `us_debt_ceiling_2023`, the difference between weighted-average and max aggregation reached `0.489047` on `2023-06-01`.

For `oct_selloff_2023`, the difference reached `0.447739` on `2023-10-21`.

For `china_taiwan_2024`, the difference was much smaller, with a maximum of `0.023891` on `2024-01-02`.

This asymmetry is exactly why averaging should be treated as conditional rather than automatic.

## Appendix B: Current Public Forecast-Quality Snapshot

The current public Brier summary is:

| Source | Mean Brier | N |
| --- | ---: | ---: |
| Naive 50/50 | 0.250 | 9 |
| Cassandra aggregated | 0.642 | 9 |
| Manifold subset | 0.498 | 4 |
| Manual subset | 0.757 | 5 |

These figures should be interpreted as diagnostics on a constrained public panel, not as the final word on a richer production forecasting stack. They nonetheless justify the inclusion of live forecast-quality monitoring as a first-class governance requirement.
