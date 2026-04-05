# Cassandra-Risk Paper 2 Findings Log

**Status:** Active research log  
**Branch:** `feature/enterprise-tier-v1`  
**Snapshot date:** `2026-04-05`  
**Snapshot tag target:** `research/paper2-findings-snapshot-v0.5.9`

This file records the confirmed findings that now define the Paper 2 evidence set.  
Each finding is anchored to a published paper, frozen tag, or measured experiment commit.

## Paper 1 - Published

Source context: [Cassandra_Risk_V1_Preprint_Draft.md](C:/Users/Admin/.codex/worktrees/f146/New%20project/paper/Cassandra_Risk_V1_Preprint_Draft.md)

### P1-F1 - The Core Thesis
- **Date stamp:** Published prior to current Paper 2 work; referenced in this log on `2026-04-05`
- **Trace:** Paper 1 DOI `10.13140/RG.2.2.21272.05124`
- **Finding:** Prediction market probabilities contain forward-looking regime fragility signal sufficient to generate directionally robust risk-adjusted outperformance over passive benchmarks. Roughly 200bps CAGR alpha over Buy & Hold survives across V1 to V4 with independent data sources.

### P1-F2 - RSI Boundedness (Proposition 1)
- **Date stamp:** Published prior to current Paper 2 work; revalidated architecturally on `2026-04-05`
- **Trace:** Paper 1 DOI `10.13140/RG.2.2.21272.05124`; later enforced in [ADR-007-kelly-weighting-architecture.md](C:/Users/Admin/.codex/worktrees/f146/New%20project/docs/adr/ADR-007-kelly-weighting-architecture.md)
- **Finding:** `RSI_t in (0,1]` for all `H_t >= 0`. The inverse form `1 / (1 + H_t)` prevents negative positions and leverage explosion. Tonight's Kelly experiments proved this is a hard architectural constraint, not just a mathematical nicety.

### P1-F3 - Convex Risk Response (Proposition 3)
- **Date stamp:** Published prior to current Paper 2 work; referenced in this log on `2026-04-05`
- **Trace:** Paper 1 DOI `10.13140/RG.2.2.21272.05124`
- **Finding:** Multiple simultaneous hazards trigger disproportionately aggressive de-risking. The framework is non-linear by design, not by accident.

## Paper 2 - In Progress

Primary draft: [Cassandra_Risk_Paper_2_SSRN_Ready.md](C:/Users/Admin/.codex/worktrees/f146/New%20project/paper/Cassandra_Risk_Paper_2_SSRN_Ready.md)

### P2-F1 - Family Compression Anti-Pattern
- **Date stamp:** `2026-03-26`
- **Trace:** tag `v0.5.2-monetary-subablation` (`0bc2320`)
- **Finding:** Collapsing events into proxies by selecting highest-volume per family concentrates the most biased contracts, making performance worse. Structural compression does not equal risk reduction.

### P2-F2 - Becker Calibration Is Return-Enhancement, Not Risk-Compression
- **Date stamp:** `2026-03-26`
- **Trace:** tag `v0.5.3-becker` (`fb84548`)
- **Finding:** Becker calibration delivers a 4.3% Sortino lift from a 0.17pp efficiency-gap correction. Downside deviation is unchanged or marginally worse. The numerator improves; the denominator does not respond.

### P2-F3 - Stack Interaction Is Sub-Additive
- **Date stamp:** `2026-03-26`
- **Trace:** tag `v0.5.4-becker-stack` (`a031735`)
- **Finding:** Becker plus top-5 is near-additive. The triple stack (Becker + top-5 + cap30) is sub-additive because cap30 and top-5 overlap on the same concentration channel. This is honest and reviewer-defensible.

### P2-F4 - MDD Invariance Across All Probability-Space Interventions
- **Date stamp:** First measured `2026-03-26`; reaffirmed `2026-04-05`
- **Trace:** tag `v0.5.5-risk-decomposition` (`2a8400f`); commits `037b629`, `8b73184`, `9bbdd29`
- **Finding:** MDD stays at `-33.72%` across every configuration tested: all five Becker stack rows, full Kelly, fractional Kelly (k=0.25), and asymmetric Kelly. This invariance is not a coincidence. It behaves like a structural property of the RSI's convex de-risking response to tail events.

### P2-F5 - Calibration Benefit Is Contingent on Structural Homogeneity
- **Date stamp:** `2026-03-26`
- **Trace:** tag `v0.5.7-geo-subbucket-calibration` (`8ec3f50`); architecture frozen in [ADR-005-calibration-architecture.md](C:/Users/Admin/.codex/worktrees/f146/New%20project/docs/adr/ADR-005-calibration-architecture.md)
- **Finding:** Monetary policy events are homogeneous, so empirical gap calibration helps. Geopolitical events are heterogeneous, so flat bucket correction overcorrects. Calibration benefit requires both empirically derived constants and structural homogeneity of the event population.

### P2-F6 - Geopolitical Signal Lives in Contracts, Not Probabilities
- **Date stamp:** `2026-03-26`
- **Trace:** tag `v0.5.6-geopolitical-expansion` (`d74cf85`)
- **Finding:** The uncalibrated geopolitical add-on improves Sortino by `+0.007`. The admission governance (500K floor, binary, macro-relevant) is doing the work, not the probability calibration.

### P2-F7 - Full Kelly Violates RSI Boundedness
- **Date stamp:** `2026-04-05`
- **Trace:** commit `037b629`; [ADR-007-kelly-weighting-architecture.md](C:/Users/Admin/.codex/worktrees/f146/New%20project/docs/adr/ADR-007-kelly-weighting-architecture.md)
- **Finding:** Signed Kelly fractions applied to hazard mass `H_t` can produce negative `H_t`, collapsing Proposition 1. RSI position range reaches `[-12.46, 27.83]` under full Kelly and the higher-fraction experiments later confirm the same failure mode. This is not numerical instability. It is the mathematically correct output of a broken input assumption.

### P2-F8 - Fractional Kelly Is Structurally Incompatible, Not Just Over-Leveraged
- **Date stamp:** `2026-04-05`
- **Trace:** commit `8b73184`; [ADR-007-kelly-weighting-architecture.md](C:/Users/Admin/.codex/worktrees/f146/New%20project/docs/adr/ADR-007-kelly-weighting-architecture.md)
- **Finding:** `k=0.25` still worsens downside deviation (`0.1637` vs `0.1431`). The problem is not magnitude. Signed fractions violate `H_t >= 0` even at small `k`. The failure mode is architectural, not merely over-leverage.

### P2-F9 - Asymmetric Kelly Is a Third Return-Enhancement Layer
- **Date stamp:** `2026-04-05`
- **Trace:** commit `9bbdd29`
- **Finding:** Sortino improves by `+11.8%` (`0.323 -> 0.361`) and CAGR by `+0.64pp` (`7.13% -> 7.77%`). Downside deviation is marginally worse (`0.1489`). RSI range stays clean at `[0.0851, 1.0]`, boundedness is preserved, and MDD remains invariant. This makes asymmetric Kelly a third return-enhancement layer, not a denominator fix.

### P2-F10 - The Denominator Is Resistant to Probability-Space Interventions
- **Date stamp:** `2026-04-05`
- **Trace:** tags `v0.5.3-becker`, `v0.5.4-becker-stack`, `v0.5.5-risk-decomposition`; commits `037b629`, `8b73184`, `9bbdd29`
- **Finding:** Three independent probability-weighting approaches - Becker calibration, the frozen Becker stack, and asymmetric Kelly - all improve Sortino through CAGR numerator. None compress downside deviation. This defines the boundary of the probability-space architecture and points to position-space filtering as the next research dimension.

## Paper 2 Headline Finding

The strongest new Paper 2 conclusion after the Kelly sequence is:

> The denominator is resistant to probability-space interventions.

That statement is now supported by three independent classes of evidence:

- Becker calibration improves Sortino by helping the numerator.
- The frozen Becker stack improves Sortino by helping the numerator.
- Asymmetric Kelly improves Sortino by helping the numerator.

None of them compress downside deviation below the frozen benchmark.  
This is the boundary of the current architecture.

## Snapshot Ledger

| Date | Ref | Evidence |
| --- | --- | --- |
| 2026-03-26 | `v0.5.2-monetary-subablation` / `0bc2320` | Family compression anti-pattern |
| 2026-03-26 | `v0.5.3-becker` / `fb84548` | Becker as numerator enhancer |
| 2026-03-26 | `v0.5.4-becker-stack` / `a031735` | Stack interaction is sub-additive |
| 2026-03-26 | `v0.5.5-risk-decomposition` / `2a8400f` | MDD invariance first formalized |
| 2026-03-26 | `v0.5.6-geopolitical-expansion` / `d74cf85` | Geo signal resides in contracts |
| 2026-03-26 | `v0.5.7-geo-subbucket-calibration` / `8ec3f50` | Calibration requires structural homogeneity |
| 2026-04-05 | `037b629` | Full Kelly violates boundedness |
| 2026-04-05 | `8b73184` | Fractional Kelly structurally incompatible |
| 2026-04-05 | `9bbdd29` | Asymmetric Kelly improves returns, not denominator |

## Governing ADRs

- [ADR-005-calibration-architecture.md](C:/Users/Admin/.codex/worktrees/f146/New%20project/docs/adr/ADR-005-calibration-architecture.md)
- [ADR-006-unified-signal-api.md](C:/Users/Admin/.codex/worktrees/f146/New%20project/docs/adr/ADR-006-unified-signal-api.md)
- [ADR-007-kelly-weighting-architecture.md](C:/Users/Admin/.codex/worktrees/f146/New%20project/docs/adr/ADR-007-kelly-weighting-architecture.md)

## Artifact Pointers

- [becker_stack_summary.csv](C:/Users/Admin/.codex/worktrees/f146/New%20project/outputs/becker/becker_stack_summary.csv)
- [risk_decomposition.csv](C:/Users/Admin/.codex/worktrees/f146/New%20project/outputs/becker/risk_decomposition.csv)
