# ADR-007: Kelly Weighting Architecture

**Status:** Accepted  
**Date:** 2026-04-05  
**Branch:** feature/enterprise-tier-v1

## Context

Paper 1 proves **Proposition 1: Boundedness** for the Regime Stability Index:

- `RSI_t = 1 / (1 + H_t)`
- `RSI_t ∈ (0, 1]` whenever `H_t ≥ 0`

This boundedness property is not cosmetic. Cassandra uses RSI directly as the portfolio
position surface, so the non-negativity of hazard mass is part of the product contract.

During the `v0.5.9` Kelly weighting experiment, Kelly fractions were applied to the
Becker-corrected event probabilities:

- `p_i^Becker = clip(p_i^raw - ε_i, 0, 1)`
- `f_i* = 2p_i^Becker - 1`
- `H_t = sum_i ω_i * d_{i,t} * p_i^Becker * f_i*`

This makes the hazard contribution signed whenever `p_i^Becker < 0.5`.
As soon as signed Kelly fractions feed directly into the hazard mass, `H_t` can become
negative and the boundedness proof collapses.

The empirical results confirm the architectural break:

| Version | Sortino | CAGR | MDD | Downside Dev |
| --- | ---: | ---: | ---: | ---: |
| V5_Becker_top5_cap | 0.323 | 7.13% | -33.72% | 0.1431 |
| V5+Becker+Kelly25 | 0.696 | 13.74% | -33.72% | 0.1637 |
| V5+Becker+Kelly50 | 4.599 | 52.47% | -44.88% | 0.2680 |
| V5+Becker+Kelly100 | 0.089 | 2.64% | -33.72% | 0.1950 |

Observed RSI / position ranges:

- Kelly25: `[0.30, 8.69]`
- Kelly50: `[-294.48, 23.12]`
- Kelly100: `[-12.46, 27.83]`

These are not numerical glitches. They are mathematically valid outputs produced by
violating the `H_t ≥ 0` assumption underlying Proposition 1.

## Decision

Kelly fractions must **never** be applied as signed multipliers on probabilities feeding
directly into RSI hazard mass.

Accepted architectural constraints:

1. **Preserve non-negativity of hazard**
   - Any Kelly variant must preserve `H_t ≥ 0` at all times.
2. **Preserve boundedness of RSI**
   - Any Kelly variant must preserve `RSI_t ∈ (0, 1]`.
3. **Do not use raw or fractional signed Kelly as hazard input**
   - Full Kelly and fractional Kelly are both architecturally incompatible with
     raw RSI-as-position.
4. **Asymmetric Kelly is the only permitted next iteration**
   - Kelly may only be used to **dampen** exposure.
   - A valid future contract is: multiply exposure when the Kelly signal is below
     baseline, but never amplify exposure beyond the existing RSI baseline.

## Consequences

- Full Kelly is a **documented boundary condition**, not a release candidate.
- Fractional Kelly is also a **documented boundary condition**; reducing the fraction
  does not repair the non-negativity assumption.
- The current frozen best stack remains:
  - `V5_Becker_top5_cap`
- Any future `v0.5.9` success candidate must be an asymmetric, bounded, non-amplifying
  Kelly variant.
- Paper 2 should explicitly record this result as a structural incompatibility rather
  than a failed tuning attempt.

## Current Boundary

This ADR does **not** approve any specific asymmetric Kelly formula yet.

It only freezes the constraint space:

- no signed Kelly hazard
- no exposure amplification beyond baseline RSI
- no future Kelly variant without boundedness preservation
