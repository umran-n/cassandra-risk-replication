# Cassandra-Risk Paper 2: Expansion, Calibration, and the Boundary Conditions of Forecast-Based Risk Overlays

## SSRN Preprint Draft

## Abstract

When does a promising risk framework earn the right to become infrastructure? The answer is not when it produces a strong backtest result. It is when the framework survives deliberate stress, generates informative failure modes, and yields boundary conditions that are theoretically principled rather than empirically tuned. This paper reports that second stage for Cassandra-Risk.

Paper 1 ended at a governed nine-event public baseline with a Sortino ratio of 1.159, CAGR of 15.99%, and daily maximum drawdown of -20.27% for SPY over 2020-01-01 through 2025-01-10. Paper 2 expands the event universe to 38 approved contracts, introduces a Polymarket historical ingestion pipeline, diagnoses the resulting degradation, and tests a sequence of remediation layers: monetary-theme ablation, targeted top-5 hazard removal, bucket capping, Becker-style efficiency-gap calibration, geopolitical expansion, and Monte Carlo robustness analysis.

The central finding is that the naive expansion degrades materially and coherently. Sortino falls from 1.159 to 0.231 when the public universe expands from 9 to 38 events, but the degradation is not random. It is concentrated in the monetary-policy bucket, where 20 of 38 admitted events keep RSI chronically depressed through the 2023-2024 recovery. Removing the monetary-policy theme raises Sortino to 0.341. A governed three-layer remediation stack consisting of monetary Becker correction (0.0017), top-5 monetary removal, and a 30% monetary hazard cap recovers the strategy to a Sortino of 0.323. Adding a governed geopolitical extension further improves Sortino to 0.330 and CAGR to 7.24%, with daily maximum drawdown unchanged at -33.72%.

The main contribution of Paper 2 is therefore not a claim of final optimization. It is a set of empirical boundary conditions. Calibration helps when the event family is structurally homogeneous and the correction constant is empirically anchored, as in monetary-policy contracts. Calibration hurts when the family is heterogeneous and the constants are only theory-driven, as in the current geopolitical bucket. Block-bootstrap Monte Carlo analysis further shows that the current best stack is directionally credible but not statistically settled: observed Sortino sits near the middle of the bootstrap distribution rather than in its tail. Taken together, these results advance Cassandra-Risk from a promising backtest toward a governed research architecture with explicit limits, reproducible decision nodes, and a clear path for Paper 3.

**Keywords:** prediction markets, risk management, regime fragility, drawdown control, calibration, monetary policy, geopolitical risk

**Suggested JEL Codes:** G11, G17, C53, D84

## 1. Introduction

Risk overlays usually fail for one of two reasons. They are either too backward-looking to notice fragility before price damage is visible, or too discretionary to survive contact with implementation. Cassandra-Risk was proposed to address the first problem by transforming event-space probabilities into a continuous Regime Stress Index (RSI). Paper 1 showed that the idea remained directionally compelling in a sparse but governed public reconstruction. Paper 2 asks the harder question: what happens when that governed universe is expanded, stressed, calibrated, and forced to reveal where it breaks?

This paper starts from the final Paper 1 public anchor: a 9-event governed baseline, a structural-theme taxonomy, a curated public discovery pipeline, hazard attribution, proxy-governance rules, and a formal multi-proxy aggregation policy. The phase documented here begins with a Polymarket historical ingest, then moves through curation, expansion, diagnosis, remediation, and robustness testing. The point is not to hide the failure modes. The point is to learn from them.

The guiding claim is precise. If prediction-market probabilities carry genuine macro-risk information, then expanding the event universe should not fail randomly. It should fail in structured ways that reveal how the signal interacts with event composition, concentration, and calibration. That is exactly what happens. Expansion to a 38-event universe damages performance sharply, but in a causally locatable way. The response is not arbitrary tuning. It is a governed architecture built from explicit empirical tests.

## 2. Starting Point from Paper 1

Paper 1 concluded with the `v0.4.0-ablation` milestone. The public baseline at that point had the following properties:

- Universe: 9 governed event families
- Asset: SPY
- Sample: 2020-01-01 to 2025-01-10
- Position rule: `position_t = RSI_t`
- Current best public baseline at that stage: Sortino `1.159`, CAGR `15.99%`, daily MDD `-20.27%`

The main conclusion from Paper 1 was modest but important: Cassandra-Risk remained directionally compelling under degraded public-data conditions, and the ablation harness showed that the result was not reducible to a single flagship event. Paper 2 begins from that anchor and asks whether the framework survives scale.

## 3. Research Questions

Paper 2 addresses five questions.

1. What happens when the public event universe expands from 9 curated events to a 38-event governed universe?
2. If the strategy degrades, is the degradation broad-based or attributable to a specific structural theme?
3. Can targeted calibration and concentration controls recover the lost performance without improving drawdown only by hiding risk elsewhere?
4. Does the same calibration logic generalize from homogeneous monetary-policy contracts to heterogeneous geopolitical contracts?
5. How statistically stable is the best post-remediation strategy under block-bootstrap resampling?

## 4. Data, Universe Construction, and Governance

### 4.1 Phase 5a: Polymarket historical ingestion

The first step beyond Paper 1 was a Polymarket historical ingestion pass. A dedicated dredger pulled resolved markets over the public sample window and applied a three-gate eligibility filter:

- informative probability history
- days-to-resolution no greater than 180
- non-noise category assignment

This produced 139 eligible candidates from 23,811 scanned markets and 10,186 scanned resolved Polymarket events. Candidate metadata included phase-3 governance fields such as `proxy_family_id`, `proxy_relation`, `aggregation_policy`, `event_window_start`, `event_window_end`, `quality_score`, and `structural_theme`.

### 4.2 Phase 5b-5c: curation into a governed 38-event universe

The candidate set was converted into a curator worksheet and then a final approved universe. The resulting governed universe had 38 events:

- 32 Polymarket events with usable histories
- 6 manually inserted Metaculus anchors

An Israel-arc cap retained only five specified geopolitical Israel-path events while dropping temporal near-duplicates. A final manual addition kept systemic-credit coverage from collapsing entirely.

The thematic mix was intentionally broader than Paper 1, but it also introduced the central challenge of this paper: a monetary-policy bucket with 20 events, many of them clustered around the 2022-2024 rate cycle.

### 4.3 Structural themes

Paper 2 uses the `structural_theme` taxonomy introduced at the end of Paper 1:

- `geopolitical`
- `monetary_policy`
- `fiscal_debt`
- `electoral`
- `systemic_credit`
- `trade_technology`

This taxonomy is analytically important because raw hazard categories were too coarse for expansion diagnostics. In particular, the old `Sovereign` bucket mixed debt and credit stress in ways that made ablations uninterpretable.

## 5. Empirical Program

The Paper 2 program unfolded in six steps:

1. Expand the universe and rerun the backtest.
2. Diagnose the degradation with theme-removal tests and hazard concentration analysis.
3. Stress-test the monetary-policy bucket with targeted sub-ablations.
4. Add Becker-style calibration as a low-cost theoretical correction layer.
5. Extend the best monetary stack with governed geopolitical contracts, with and without geopolitical calibration.
6. Run a block-bootstrap Monte Carlo test on the best resulting strategy.

Every step was committed, tagged where appropriate, and preserved in the repo artifact set.

## 6. Results

### 6.1 The expansion shock

The first result is the key diagnostic event of Paper 2.

| Version | Events | Sortino | CAGR | Daily MDD | Avg Position |
| --- | ---: | ---: | ---: | ---: | ---: |
| V4 baseline | 9 | 1.159 | 15.99% | -20.27% | 78.72% |
| V5 approved universe | 38 | 0.231 | 5.75% | -33.72% | 67.26% |

The degradation is severe. But it should not be interpreted as random model fragility. If prediction-market probabilities were noise, expansion would have had no systematic directional effect. Instead, the expanded universe failed coherently: exposure stayed too low for too long during the 2023-2024 equity recovery.

### 6.2 Expansion failure as evidence of informational sensitivity

The expansion collapse is evidence for the core thesis as much as it is a problem to fix. The failure was asymmetric in timing, concentrated in specific quarters, and traceable to a concrete structural bucket. This is what a real signal looks like when it is overloaded with poorly governed inputs. The RSI was not inert. It was informationally sensitive to what entered the event universe.

The strongest missed-recovery quarters were:

| Quarter | Avg RSI | Avg Position | SPY Return | Cassandra Return | Gap vs SPY |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023Q2 | 0.132 | 13.21% | 8.68% | 0.07% | 8.61% |
| 2023Q4 | 0.231 | 23.14% | 11.64% | 1.72% | 9.92% |
| 2024Q1 | 0.111 | 11.14% | 10.39% | 1.18% | 9.21% |
| 2024Q2 | 0.138 | 13.76% | 4.38% | -0.26% | 4.63% |
| 2024Q3 | 0.133 | 13.26% | 5.75% | -0.02% | 5.77% |
| 2024Q4 | 0.141 | 14.15% | 2.49% | -1.31% | 3.80% |

That pattern is too coherent to dismiss as random drift.

### 6.3 Theme-level diagnosis

Theme-removal tests isolated the source of the damage.

| Theme Removed | Active Events | Sortino | CAGR | Daily MDD | Avg Position |
| --- | ---: | ---: | ---: | ---: | ---: |
| `monetary_policy` | 12 | 0.341 | 7.42% | -33.72% | 77.86% |
| `geopolitical` | 26 | 0.257 | 6.14% | -33.72% | 71.13% |
| `electoral` | 28 | 0.276 | 6.42% | -33.72% | 69.03% |

Removing `monetary_policy` produces by far the strongest recovery. The immediate implication is that the V5 failure is not broad event-universe contamination. It is a concentration problem in one structurally interpretable bucket.

### 6.4 Monetary concentration

The monetary bucket is not dominated by a single bad contract. It is overloaded by a stack of related FOMC and rate-cut/rate-hike markets.

Top cumulative monetary hazard contributors:

| Rank | Event | Theme Hazard Share | Total Hazard Share |
| ---: | --- | ---: | ---: |
| 1 | Fed +25 bps after March 2023 meeting | 11.57% | 5.12% |
| 2 | Fed 0 bps after September 2023 meeting | 9.92% | 4.40% |
| 3 | Fed +50 bps after February 2023 meeting | 9.50% | 4.21% |
| 4 | Fed 0 bps after December 2023 meeting | 8.66% | 3.84% |
| 5 | Fed rate cut by May 1 2024 | 8.06% | 3.57% |

The top five monetary contracts jointly account for approximately 47.7% of theme hazard. That is distributed enough to rule out a single rogue contract, but concentrated enough to justify a targeted pruning rule.

### 6.5 Monetary-policy sub-ablation

Three monetary fixes were tested.

| Test | Monetary Events | Sortino | CAGR | Daily MDD | Avg Position |
| --- | ---: | ---: | ---: | ---: | ---: |
| Family compression | 3 | 0.211 | 5.42% | -33.72% | 75.30% |
| Top-5 removal | 15 | 0.294 | 6.69% | -33.72% | 72.22% |
| 30% bucket cap | 20 | 0.268 | 6.30% | -33.72% | 70.83% |

The result is decisive:

- crude family compression makes the strategy worse
- top-5 removal is the strongest single structural fix
- bucket capping also helps, but overlaps with top-5 removal

This is already an important methodological finding. The right remedy is not to collapse all FOMC events into a tiny family set. It is to remove the worst offenders and constrain residual concentration.

### 6.6 Becker calibration

A Becker-style efficiency-gap correction was then applied as a separate calibration layer.

| Version | Sortino | CAGR | Daily MDD | Avg Position |
| --- | ---: | ---: | ---: | ---: |
| V5 | 0.231 | 5.75% | -33.72% | 67.26% |
| V5_Becker | 0.241 | 5.89% | -33.72% | 66.92% |

The lift is small but important: a +0.010 Sortino improvement from a 0.0017 monetary efficiency gap, with structure unchanged and drawdown unchanged. This is exactly the scale expected from a low-amplitude, theory-driven calibration term applied to a structurally homogeneous event family.

### 6.7 The three-layer monetary stack

Paper 2 then stacked three interventions:

- Becker monetary calibration
- top-5 monetary removal
- 30% monetary bucket cap

The result is:

| Version | Sortino | CAGR | Daily MDD | Avg Position |
| --- | ---: | ---: | ---: | ---: |
| V5 | 0.231 | 5.75% | -33.72% | 67.26% |
| V5_Becker | 0.241 | 5.89% | -33.72% | 66.92% |
| V5_Becker_top5 | 0.305 | 6.86% | -33.72% | 71.44% |
| V5_Becker_cap30 | 0.279 | 6.46% | -33.72% | 70.01% |
| V5_Becker_top5_cap | 0.323 | 7.13% | -33.72% | 73.05% |

This is a key Paper 2 result. The best monetary stack improves Sortino by 39.8% relative to the naive V5 expansion baseline and raises CAGR by 1.38 percentage points, while daily maximum drawdown remains unchanged across all five configurations.

### 6.8 Risk decomposition of the monetary stack

To make that claim reviewer-safe, additional downside metrics were measured across the five stack rows.

| Version | Sortino | Downside Deviation | CVaR 95 | Monthly MDD Mean | Monthly MDD Worst |
| --- | ---: | ---: | ---: | ---: | ---: |
| V5 | 0.231 | 0.1417 | -0.0312 | -0.0373 | -0.2832 |
| V5_Becker | 0.241 | 0.1416 | -0.0312 | -0.0372 | -0.2832 |
| V5_Becker_top5 | 0.305 | 0.1428 | -0.0313 | -0.0386 | -0.2832 |
| V5_Becker_cap30 | 0.279 | 0.1422 | -0.0312 | -0.0381 | -0.2832 |
| V5_Becker_top5_cap | 0.323 | 0.1431 | -0.0313 | -0.0391 | -0.2832 |

This matters for interpretation. The Sortino lift does not come from compressing downside deviation. Downside deviation drifts slightly upward, while CVaR 95 and worst monthly drawdown remain effectively unchanged. The strongest safe claim is therefore:

the three-layer stack materially improves downside-adjusted performance and CAGR while leaving CVaR and worst monthly drawdown essentially flat.

### 6.9 Governed geopolitical expansion

After the monetary stack was stabilized, Paper 2 added a governed geopolitical extension.

| Version | Events | Sortino | CAGR | Daily MDD | Avg Position |
| --- | ---: | ---: | ---: | ---: | ---: |
| V5_Becker_top5_cap | 27 | 0.323 | 7.13% | -33.72% | 73.05% |
| V5_geo_only | 39 | 0.236 | 5.82% | -33.72% | 66.80% |
| V5_Becker_top5_cap_geo | 34 | 0.330 | 7.24% | -33.72% | 72.54% |
| V5_Becker_top5_cap_geo_calibrated | 34 | 0.318 | 7.05% | -33.72% | 74.66% |

Two results are important.

1. Raw governed geopolitical admission adds real signal. Sortino rises from 0.323 to 0.330.
2. Flat geopolitical Becker correction overcorrects and gives the gain back.

This means the geo contracts themselves are informative, but the current calibration granularity is wrong.

### 6.10 Geopolitical sub-bucket calibration

Paper 2 then tested whether finer geopolitical splitting would rescue calibration.

| Version | Sortino | CAGR | Daily MDD | Avg Position |
| --- | ---: | ---: | ---: | ---: |
| V5_Becker_top5_cap_geo | 0.330 | 7.24% | -33.72% | 72.54% |
| V5_Becker_top5_cap_geo_flat | 0.318 | 7.05% | -33.72% | 74.66% |
| V5_Becker_top5_cap_geo_subbucket | 0.316 | 7.03% | -33.72% | 74.61% |

Sub-bucket calibration performs slightly worse than flat bucket calibration. That is the cleanest calibration boundary condition in the entire project. Theme splitting alone does not rescue geopolitical calibration. The residual problem is almost certainly horizon interaction and the lack of empirically estimated geopolitical family constants.

### 6.11 Monte Carlo robustness

The current best strategy, `V5_Becker_top5_cap_geo`, was then subjected to block-bootstrap Monte Carlo testing:

- block length: 20 trading days
- samples: 500
- metrics: Sortino, CAGR, MDD, downside deviation

Result summary:

| Metric | Observed | Bootstrap Mean | 95% CI |
| --- | ---: | ---: | ---: |
| Sortino | 0.330 | 0.454 | [-0.651, 1.806] |
| CAGR | 7.24% | 8.37% | [-8.99%, 25.36%] |
| MDD | -33.72% | -31.93% | [-58.55%, -14.05%] |
| Downside Deviation | 0.1431 | 0.1400 | [0.0979, 0.1940] |

The one-sided empirical p-value for Sortino, defined as the fraction of bootstrap samples with Sortino greater than the observed 0.330, is 0.542.

The implication is clear: the current best strategy is directionally credible, but not statistically settled. The observed Sortino is not an outlier relative to the bootstrap distribution. It sits near the middle of a wide path-dependent range.

## 7. Decision Nodes and Architecture Freeze

The evidence accumulated in Paper 2 supports a current best architecture:

- `monetary_policy`: Becker 0.0017 + top-5 removal + 30% cap
- `geopolitical`: governed admission, uncalibrated
- combined best row: `V5_Becker_top5_cap_geo`

This architecture is not the product of a single tuning pass. It is the product of explicit decision nodes:

1. Expansion failure was diagnosed as monetary over-warning rather than broad event-universe collapse.
2. Monetary remediation favored targeted removal and capping over crude family compression.
3. Becker calibration was kept permanently for monetary policy because it helped at low amplitude with empirical grounding.
4. Geopolitical contracts were kept because raw admission added signal.
5. Geopolitical calibration was intentionally deferred because both flat and sub-bucket variants degraded performance.

The resulting policy is an architecture, not a patchwork:

- calibrate where event families are homogeneous and constants are empirical
- cap where concentration is the real risk
- defer calibration where structure is heterogeneous and the dominant error source is still unresolved

## 8. Interpretation

The most important conceptual finding of Paper 2 is that negative results were informative in the right direction.

The V5 degradation did not invalidate Cassandra-Risk. It revealed that the framework is highly sensitive to event composition, especially inside structurally concentrated buckets. The monetary-policy failure mode behaved like a real signal reacting to real informational content, not like arbitrary noise.

The geopolitical calibration failures are equally informative. They show that calibration benefit depends on two conditions:

1. empirical gap estimation from a structurally homogeneous event family
2. alignment between the calibration dimension and the dominant source of miscalibration

Monetary policy satisfied both conditions. Geopolitics satisfied neither. That is why calibration helped in one bucket and harmed in the other.

## 9. Limitations

### 9.1 Path dependence is not the same as regime-class generalization

The Monte Carlo exercise addresses path dependence within already observed regime classes. It does not answer whether Cassandra generalizes to a regime class it has never seen. That is the deeper unsettled question.

The public sample includes COVID crash, the rate-hike cycle, SVB contagion, and carry-trade unwind. These are structurally distinct episodes, but they are still the regimes the architecture has already learned from. A genuinely new fragility pattern that does not map cleanly onto the existing taxonomy could still produce systematic error that block bootstrap cannot detect.

### 9.2 Current public data remains imperfect

Paper 2 improves the event universe materially, but it still relies on a mixed public architecture:

- 32 active Polymarket histories
- 6 manually inserted Metaculus anchors without live historical paths in the current workspace

This is a better expansion environment than Paper 1, but it is not yet a full multi-source empirical calibration lab.

### 9.3 Geopolitical calibration remains unresolved

Paper 2 rules out two coarse approaches:

- flat geopolitical Becker correction
- sub-bucket geopolitical Becker correction

It does not yet estimate empirical family-by-horizon constants from realized geopolitical contract histories. That remains a Paper 3 task.

## 10. Conclusion

Paper 2 moves Cassandra-Risk forward in a way that is more valuable than another isolated backtest win. It shows how the framework behaves under stress, how it fails, how those failures can be localized, and which remediation layers are legitimate rather than cosmetic.

The strongest current empirical result is not the original 9-event baseline. It is the governed expanded architecture:

- expansion to 38 events reveals a coherent monetary over-warning failure mode
- a three-layer monetary stack recovers most of that damage
- a governed geopolitical extension adds further signal
- geopolitical calibration does not help yet and is therefore explicitly deferred
- Monte Carlo testing shows the result is promising but not statistically settled

That is enough for a serious Paper 2 claim. Cassandra-Risk has moved beyond a promising backtest and into a governed research architecture with explicit boundary conditions. It has not yet earned the label of deployable infrastructure. But it is now close enough that the remaining gaps are precise rather than vague.

## Code and Data Availability

All milestones described in this paper are preserved in the public repository:

- repository: [https://github.com/umran-n/cassandra-risk-replication](https://github.com/umran-n/cassandra-risk-replication)
- current best-stack Monte Carlo tag: `v0.5.8-monte-carlo`
- calibration-boundary tag: `v0.5.7-geo-subbucket-calibration`
- geopolitical-expansion tag: `v0.5.6-geopolitical-expansion`
- risk-decomposition tag: `v0.5.5-risk-decomposition`
- Becker-stack tag: `v0.5.4-becker-stack`
- monetary-subablation tag: `v0.5.2-monetary-subablation`
- diagnostic tag: `v0.5.1-diagnostic`
- expansion-results tag: `v0.5.0-expansion-results`

Key artifact files include:

- `outputs/expansion/expansion_summary.csv`
- `outputs/expansion/theme_ablation.csv`
- `outputs/expansion/monetary_subablation.csv`
- `outputs/becker/becker_stack_summary.csv`
- `outputs/becker/risk_decomposition.csv`
- `outputs/expansion/geopolitical_expansion_summary.csv`
- `outputs/expansion/geopolitical_subbucket_summary.csv`
- `outputs/monte_carlo/mc_summary.csv`

## References

- Becker microstructure and efficiency-gap calibration paper used for the monetary-policy correction layer.
- Prediction-market calibration decomposition paper documenting the importance of domain-by-horizon interaction.
- Paper 1 public preprint draft and associated replication artifacts.

## Appendix A: Development Ledger Since Paper 1 Freeze

| Commit | Tag | Decision Node | Result |
| --- | --- | --- | --- |
| `6601e36` | `v0.4.0-ablation` | Freeze Paper 1 public ablation baseline | 9-event governed baseline established |
| `af1fbfb` | n/a | Phase 5a Polymarket historical ingestion | 139 eligible candidates recovered |
| `a63f303` | `v0.5.1-curator-worksheet` | Build curator worksheet for review | Review package created for final universe selection |
| `c3bf193` | `v0.5.0-curation-final` | Finalize 38-event approved universe | 32 Polymarket + 6 Metaculus anchors approved |
| `ae77429` | `v0.5.0-expansion-results` | Rerun backtest on expanded universe | Sortino collapses to 0.231 |
| `6eccf59` | `v0.5.1-diagnostic` | Diagnose expansion degradation | Monetary over-warning isolated |
| `0bc2320` | `v0.5.2-monetary-subablation` | Test structural monetary fixes | Top-5 removal and bucket cap validated |
| `fb84548` | `v0.5.3-becker` | Add Becker monetary calibration layer | Sortino lifts from 0.231 to 0.241 |
| `a031735` | `v0.5.4-becker-stack` | Stack Becker + top-5 + cap | Sortino rises to 0.323 |
| `2a8400f` | `v0.5.5-risk-decomposition` | Test whether stack improvement merely hides risk | CVaR and worst monthly MDD remain flat |
| `d74cf85` | `v0.5.6-geopolitical-expansion` | Add governed geopolitical extension | Sortino improves to 0.330 uncalibrated |
| `8ec3f50` | `v0.5.7-geo-subbucket-calibration` | Test flat vs sub-bucket geo calibration | Both calibrated variants underperform raw geo |
| `824da3d` | n/a | Freeze calibration architecture in ADR-005 | Monetary-only calibration policy formalized |
| `993bf11` | `v0.5.8-monte-carlo` | Run block-bootstrap robustness test on best stack | Directionally credible, not statistically settled |
| `1981ef6` | n/a | Freeze Paper 2 framing | Infrastructure, expansion-signal, and regime-limit framing added |

## Appendix B: Current Architecture Recommendation

The current architecture implied by Paper 2 is:

```text
Monetary policy:
  - Apply Becker calibration (gap = 0.0017)
  - Remove top 5 cumulative-hazard contracts
  - Cap monetary hazard share at 30%

Geopolitical:
  - Use governed admission only
  - Keep bucket uncalibrated
  - Revisit only after empirical family-by-horizon constants exist

Combined best stack:
  - V5_Becker_top5_cap_geo
  - Sortino 0.330
  - CAGR 7.24%
  - Daily MDD -33.72%
```

## Appendix C: Reviewer-Safe Claims

The strongest claims Paper 2 can make without overreach are:

1. Expansion from 9 to 38 events degrades performance in a coherent, diagnosable way rather than a random one.
2. Monetary-policy concentration is the dominant source of degradation in the expanded public universe.
3. A governed three-layer monetary stack recovers most of the lost downside-adjusted performance.
4. Governed geopolitical admission adds signal, but geopolitical calibration does not yet help.
5. The current best stack is empirically promising but not statistically settled under block-bootstrap Monte Carlo.
