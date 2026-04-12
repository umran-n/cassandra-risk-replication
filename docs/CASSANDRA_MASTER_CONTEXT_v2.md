# CASSANDRA RISK — MASTER CONTEXT DOCUMENT v2.0
**Thread Date:** 2026-04-02 | Mumbai IST  
**Status:** Living document — update after every major session  
**Repo:** github.com/umran-n/cassandra-risk-replication  
**Version:** v2.0 (supersedes CASSANDRA RISK — FULL SESSION CONTEXT v0.5.8)

---

## 0. SESSION OPERATING RULES

### Git Workflow Rule

All standard git backup actions are user-executed in PowerShell. Codex should provide the exact commands to run, but should not default to GitHub MCP for normal commit or push flows unless the user explicitly asks for a fallback.

### Branch Safety Rule

Do not push active research work to `main`. `main` is Railway-stable and deploy-sensitive. Active research, enterprise-tier work, and experimental findings should be committed and pushed through PowerShell to `dev` or the relevant feature branch first.

### Default PowerShell Git Commands

```powershell
git status
git add .
git commit -m "YOUR_COMMIT_MESSAGE"
git push origin feature/enterprise-tier-v1
```

### Tag Push Command

```powershell
git push origin research/paper2-findings-snapshot-v0.5.9
```

### Fallback Rule

Use GitHub MCP only if PowerShell git fails and the user explicitly wants a non-shell backup path.

---

## 1. PROJECT IDENTITY

**Project Name:** Cassandra Risk  
**Tagline:** Bloomberg tells you what happened. Cassandra tells you what's coming.  
**Core Hypothesis:** Prediction market event probabilities contain forward-looking regime fragility signals that can govern portfolio exposure more efficiently than backward-looking risk controls (VaR, realised volatility).  
**Framework:** Regime Stability Index (RSI) computed from weighted, horizon-decayed event probabilities across hazard categories. Portfolio position = RSI. When aggregate event hazard rises, exposure falls.  
**Epistemological Arbitrage:** At the intersection of prediction markets (The Gambler), forecasters (The Philosopher), institutional quants (The Bureaucrat), and academics (The Validator) — none of whom talk to each other.

---

## 2. PUBLISHED RESEARCH (DOI-STAMPED)

| Paper | Title | DOI | Status |
|-------|-------|-----|--------|
| Paper 1 | Beyond Value-at-Risk: Cassandra-Risk via Prediction Markets | 10.13140/RG.2.2.21272.05124 | ✅ Live |
| Paper 2 | Governance & Calibration Architecture (Becker Stack) | 10.13140/RG.2.2.17209.12644 | ✅ Live |
| Paper 3 | Ensemble Signal: Polymarket + Kalshi Cross-Platform Validation | TBD | 🔨 In progress |
| Paper 4 | Fragility Alpha: RSI vs VaR Delta (Bigdata.com cross-validation) | TBD | 📋 Planned |
| Paper 5 | Kelly-Optimal Position Sizing from Governed RSI | TBD | 📋 Planned |
| Paper 6 | Asset Class RSI Vector & Event-Driven Rotation | TBD | 📋 Planned |
| Paper 7 | On-Chain Funds Movement as Cross-Signal Alpha | TBD | 📋 Planned |
| Paper 8 | SIR Contagion Model with Prediction Market Transmission Coefficient | TBD | 📋 Planned |

**Rule:** Every API tier has a corresponding paper. Every paper funds the next API tier.

---

## 3. HEADLINE PERFORMANCE (Paper 1 Baseline — V4)

| Metric | Buy & Hold | Vol Targeting | Cassandra V4 |
|--------|-----------|---------------|--------------|
| CAGR | 13.99% | 11.46% | **15.99%** |
| Sortino | 0.733 | 0.836 | **1.159** |
| Daily MDD | -33.72% | -15.14% | -20.27% |
| Avg Position | 100% | 77.3% | 78.7% |
| Total Return (5yr) | 92.73% | 72.22% | **110.31%** |

**Backtest period:** 2020-01-01 to 2025-01-10, SPY daily, 3 independent replication passes.  
**Key result:** Higher return AND lower drawdown simultaneously — not a conventional risk/return tradeoff. A new information dimension.

---

## 4. CURRENT BEST ARCHITECTURE (Frozen at v0.5.7)

```
Strategy:    V5-Becker-top5cap-geo
Tag:         v0.5.7-geo-subbucket-calibration
Commit:      8ec3f50
Performance: Sortino 0.330 | CAGR 7.24% | MDD -33.72%

Architecture layers:
  Monetary:     Becker 0.0017 + top-5 removal + 30% cap
  Geopolitical: Governed admission (500K floor, binary, macro-relevant, 25% cap), UNCALIBRATED
  All other:    Standard admission, no calibration correction yet
```

### Becker Efficiency Gap Constants

| Category | Gap | Source |
|----------|-----|--------|
| monetary_policy | 0.0017 | Kalshi, 72.1M trades, $18.26B volume |
| geopolitical | 0.0732 | Widest — heterogeneous event types |
| electoral | 0.0102 | — |
| trade_technology | 0.0269 | — |
| fiscal_debt | 0.0102 | — |
| systemic_credit | 0.0102 | — |

---

## 4A. ENTERPRISE TIER 1 SHIPPING BOX (Locked 2026-04-05)

**Enterprise Tier 1 is not Becker alone.** It is the full stacked V5 production signal:

```text
Base V5 universe         38 events, governed admission
+ Top-5 removal          ADR-003
+ 30% bucket cap        ADR-003
+ Becker calibration    theme-specific epsilon layer
+ Geo adjustment        ADR-005
+ Asymmetric Kelly      internal numerator weighting only
                         (not exposed as a client parameter)
= Enterprise Tier 1
```

**Current Enterprise Tier 1 result:** Sortino `0.361`

**Interpretation:**
- Paper 1 / V4 remains the public proof-of-concept signal
- Enterprise Tier 1 is the private production signal on the governed V5 universe
- Asymmetric Kelly belongs inside the production stack as an internal weighting layer, not as a marketplace knob

**Release tag sequence when shipping Tier 1:**

```powershell
git tag v1.0.0-enterprise-tier1
git push origin v1.0.0-enterprise-tier1
```

---

## 5. BUILD VERSION HISTORY (Key Milestones)

| Version | Description | Sortino | CAGR |
|---------|-------------|---------|------|
| v0.5.0 | V5 Expansion — 38-event Polymarket universe | 0.231 | 5.75% |
| v0.5.3 | Becker calibration layer added | 0.241 | 5.89% |
| v0.5.4 | Becker + top-5 + cap30 stack | 0.323 | 7.13% |
| v0.5.6 | Geopolitical expansion (uncalibrated) | 0.330 | ~7.2% |
| v0.5.7 | Sub-bucket geo calibration (frozen best) | **0.330** | **7.24%** |
| v0.5.8 | Monte Carlo bootstrap CI (in progress at session end) | — | — |
| v0.6.x | Kalshi dredger + governed promotion workflow | ✅ Built | — |
| v1.0.0 | Live RSI API — deployed to Railway | ✅ LIVE | — |

---

## 6. LIVE API STATUS

| Marketplace | Status | Popularity | Uptime | Price |
|-------------|--------|-----------|--------|-------|
| RapidAPI | ✅ Live | 8.7 | 100% | $49/mo PRO |
| Zyla Labs | ✅ Live | 100% SLA | 190ms | Active |
| Postman | ⏸ Deferred | Platform friction | — | — |
| AWS Marketplace | 📋 Planned | — | — | Month 2 |
| Azure Marketplace | 📋 Planned | — | — | Month 2 |

**Subscribers:** 1 (RapidAPI)  
**MCP Access:** Zyla auto-exposes MCP endpoint — usable with Claude Desktop, Cursor, Windsurf, Cline today.  
```
mcp.zylalabs.com/mcp?apikey=YOUR_ZYLA_API_KEY
```

### Product Positioning Split

```text
Free / public tier:
  V4 signal (Paper 1 proof of concept)
  Open source, public framing

Enterprise Tier 1:
  Full stacked V5 production signal
  Becker + geo + asymmetric Kelly internals
  Private endpoint, API key gated
  Sortino 0.361 on governed V5 universe
```

---

## 7. FULL API ROADMAP — THE CASSANDRA INSTITUTIONAL STACK

```
LAYER 1 — Signal Foundation
  Cassandra-Core API             ✅ LIVE
  └─ Live RSI, governed registry, Becker-calibrated
  └─ 54 event families, 3 DOI papers
  └─ $49/mo | RapidAPI + Zyla

LAYER 2 — Intelligence
  Cassandra-Pro API              🔨 NEXT BUILD (v0.7.0)
  └─ RSI history (2020–2026)
  └─ Ensemble monetary (Polymarket + Kalshi)
  └─ Theme-level signal decomposition
  └─ Family-level breakdown (all 54 families)
  └─ $149/mo

LAYER 3 — Fragility Alpha          ← NEW (Bigdata.com)
  Cassandra-Alpha API            📋 Paper 4
  └─ Fragility Alpha = RSI - VaR delta
  └─ Bigdata.com cross-validation (news sentiment vs RSI)
  └─ "When Cassandra sees danger VaR doesn't"
  └─ $299/mo

LAYER 4 — Position Sizing
  Cassandra-Kelly API            📋 Paper 5
  └─ Kelly-optimal position sizing from governed RSI
  └─ Direct portfolio overlay output
  └─ Downside deviation compression target
  └─ $299/mo

LAYER 5 — Regime Intelligence
  Cassandra-Regime API           📋 Paper 6
  └─ Asset Class RSI Vector (per-asset hazard sensitivity)
  └─ Event-driven rotation: SPY / TLT / GLD / BTC / Cash
  └─ Hazard sensitivity matrix α(a,k)
  └─ $499/mo

LAYER 6 — On-Chain Cross-Signal
  Cassandra-Chain API            📋 Paper 7
  └─ On-chain funds movement as leading risk signal
  └─ Stablecoin inflows to exchanges = risk-off indicator
  └─ Whale wallet movements cross-validated with RSI
  └─ Delta = on-chain alpha layer
  └─ $499/mo

LAYER 7 — Bio-Signal (Contagion Model)
  Cassandra-Bio API              📋 Paper 8
  └─ SIR epidemiological model applied to market contagion
  └─ Susceptible = exposed asset classes
  └─ Infected = RSI-degraded assets
  └─ Recovered = RSI normalising post-event
  └─ Transmission coefficient β = Cassandra hazard mass Ht
  └─ Recovery rate γ = RSI re-risking speed (~13 days avg)
  └─ R₀ = β/γ = "Contagion Reproduction Number"
  └─ R₀ > 1 → regime stress spreading; R₀ < 1 → contained
  └─ $999/mo

LAYER 8 — Real-Time Streaming
  Cassandra-Stream API           📋 v0.9.0
  └─ WebSocket live RSI feed
  └─ RSI threshold alerts + webhooks
  └─ $499/mo

LAYER 9 — Enterprise Suite
  Cassandra-Enterprise           📋 v5.0
  └─ All APIs bundled
  └─ Dedicated MCP server (pip install cassandra-risk-mcp)
  └─ White-label ready
  └─ Audit trail + SLA
  └─ Bigdata.com Fragility Alpha integrated
  └─ Custom pricing (RBC-tier clients)
```

---

## 8. THE FRAGILITY ALPHA THESIS (NEW — Added 2026-04-02)

**Core Insight:** VaR is backward-looking by construction. Cassandra RSI is forward-looking. The gap between them is the alpha.

```
Fragility Alpha = RSI_signal - VaR_signal

When Cassandra sees danger VaR doesn't → Advance warning premium
When VaR sees danger Cassandra doesn't → Noise filter / false alarm catch
```

**Paper 4 Hypotheses:**
- H1: RSI leads VaR spikes by 3–7 trading days on geopolitical events
- H2: RSI-VaR delta predicts abnormal returns better than either signal alone
- H3: Fragility Alpha is largest during low-volatility, high-event-hazard regimes (exactly when VaR is most blind)

**Data requirement:** Bigdata.com API access (trial requested 2026-04-01, confirmation received).

**Case examples:**
- Ukraine Feb 2022: VaR = normal (12% vol). RSI = 0.14 (P_invasion = 68%). Delta = advance warning.
- SVB Mar 2023: VaR = calm. RSI elevated (P_major bank failure = 42%). Delta = early signal.

---

## 9. ASSET CLASS RSI VECTOR (Layer 5 Detail)

From Paper 1 Section 13 — multi-asset hazard sensitivity matrix α(a,k):

| Asset | Kinetic | Sovereign | Trade | Monetary | Technology |
|-------|---------|-----------|-------|----------|-----------|
| SPY (Equities) | -0.85 | -0.70 | -0.60 | -0.55 | -0.40 |
| TLT (Long Bonds) | +0.60 | -0.30 | +0.20 | -0.80 | +0.10 |
| GLD (Gold) | +0.75 | +0.50 | +0.30 | +0.20 | +0.15 |
| BTC (Crypto) | -0.40 | -0.60 | -0.35 | -0.70 | -0.80 |
| Cash | +0.50 | +0.40 | +0.30 | +0.25 | +0.20 |

**Rotation logic:** Rather than de-risking to cash uniformly, Layer 5 rotates into safe-haven assets capturing the risk premium differential during regime stress. Empirical multi-asset validation reserved for Paper 6.

---

## 10. ON-CHAIN CROSS-SIGNAL THESIS (Layer 6 Detail)

**Signal sources:**
- Stablecoin inflows to exchanges → risk-off capital flight indicator
- Whale wallet movements to CEXs → near-term sell pressure
- BTC/ETH smart money wallet tracking → regime confirmation

**Cross-signal logic:**
```
On-chain flight + High RSI  = CONFIRMED regime stress (highest conviction)
On-chain calm  + High RSI  = Prediction markets LEADING on-chain (early warning)
On-chain stress + Low RSI  = Noise filter — RSI catches false alarm
On-chain calm  + Low RSI  = Risk-on confirmed (full position)
```

**Alpha:** The quadrant delta between on-chain and RSI signals. Paper 7 core result.

---

## 11. SIR CONTAGION MODEL THESIS (Layer 7 Detail)

**Model:** Standard SIR epidemiological framework (Kermack-McKendrick) applied to financial contagion.

```
S (Susceptible)  = Asset classes exposed to active hazard families
I (Infected)     = Assets with RSI below threshold (regime stress spreading)
R (Recovered)    = Assets where RSI is normalising post-event

β (Transmission) = Cassandra hazard mass Ht (from RSI engine)
γ (Recovery)     = RSI re-risking speed (empirical avg: 13 trading days)
R₀ = β/γ        = "Contagion Reproduction Number"
```

**Novel contribution:** No prior framework uses live prediction market probabilities as the transmission coefficient β. Academic precedent exists for SIR models in finance (epidemiological contagion literature, ~1990s onward) but all prior work uses historical price correlations — not forward-looking event hazard — as the transmission mechanism.

**Signals:**
- R₀ > 1 → regime stress reproducing, spreading across asset classes
- R₀ < 1 → contagion contained, recovery underway
- dR₀/dt → rate of contagion acceleration (early warning of regime break)

---

## 12. REVENUE MODEL

| Tier | API | Price | Target Audience |
|------|-----|-------|----------------|
| 1 | Cassandra-Core | $49/mo | Quant developers, researchers |
| 2 | Cassandra-Pro | $149/mo | Portfolio managers, allocators |
| 3 | Cassandra-Alpha | $299/mo | Risk desks, hedge funds |
| 3 | Cassandra-Kelly | $299/mo | Systematic funds |
| 4 | Cassandra-Regime | $499/mo | Multi-asset allocators |
| 4 | Cassandra-Chain | $499/mo | Crypto-native institutions |
| 4 | Cassandra-Stream | $499/mo | Real-time risk systems |
| 5 | Cassandra-Bio | $999/mo | Institutional risk research |
| 6 | Cassandra-Enterprise | Custom | RBC-tier institutions |

**Conservative Month 6 ceiling:** ~$5,600/mo  
**Year 2 ceiling (institutional adoption):** ~$25,000/mo

---

## 13. MCP STRATEGY

**Immediate (free, already live):** Zyla auto-exposes MCP endpoint. Works today with Claude Desktop, Cursor, Windsurf, Cline.

**Near-term build (Tier 2):** Dedicated `cassandra-risk-mcp` Python package on PyPI.
```bash
pip install cassandra-risk-mcp
```

**Claude Desktop config:**
```json
{
  "mcpServers": {
    "cassandra-risk": {
      "command": "uvx",
      "args": ["cassandra-risk-mcp"],
      "env": {"CASSANDRA_API_KEY": "their-key"}
    }
  }
}
```

**Strategic significance:** Institutional AI stacks (RBC Aiden-style) are already running MCP-native architectures. A dedicated Cassandra MCP makes RSI a first-class tool in their AI workflow — callable in natural language, no code required.

---

## 14. BIGDATA.COM INTEGRATION PLAN

**Status:** Trial access requested 2026-04-01. Confirmation email received.

**Integration architecture:**
```
Bigdata.com  →  Unstructured intelligence (news sentiment, 40,000+ sources)
Cassandra    →  Structured prediction market RSI
Together     →  Complete forward-looking risk stack
```

**First experiment on trial access:**
Pull Bigdata.com VaR scores for SPY on the 2020–2026 backtest window. Compute delta against RSI series. Plot lead/lag relationship. This chart is the Tier 3 sales pitch.

**Partnership angle:** Bigdata.com is the unstructured layer. Cassandra is the structured prediction market signal layer. They are complementary, not competitive. RBC/Bigdata.com architecture is the template — Cassandra slots in as the regime fragility input layer their AI research stack is currently missing.

---

## 15. NEXT BUILD PRIORITIES

```
Immediate (this sprint):
  1. Tier 2 endpoints → v0.7.0
     - GET /v1/rsi/history?from=2020-01-01
     - GET /v1/signals/decomposition
     - GET /v1/ensemble/monetary
     - GET /v1/signals/families (all 54)
     - GET /v1/risk/overlay?ticker=SPY
     - GET /v1/meta/calibration
  2. RapidAPI $149/mo PRO plan update
  3. Zyla listing update — add MCP banner to description

Near-term (next 2 sessions):
  4. cassandra-risk-mcp → PyPI
  5. RSI history export from outputs/ backtest series
  6. Paper 3 draft — ensemble monetary result

When Bigdata.com trial lands:
  7. VaR vs RSI delta computation
  8. Lead/lag analysis (H1: RSI leads VaR by 3–7 days)
  9. Paper 4 draft — Fragility Alpha

Deferred (Month 2+):
  10. AWS/Azure Marketplace listing
  11. Cassandra-Kelly (v0.5.9 Kelly weighting)
  12. Landing page — cassandra-risk.com
  13. Show HN launch post
```

---

## 16. MARKETPLACE EXPANSION ROADMAP

```
✅ RapidAPI (live, 8.7 popularity, 1 subscriber)
✅ Zyla Labs (live, 100% SLA, MCP-enabled)
⏳ APILayer (30 min, free listing)
⏳ AWS Marketplace (Tier 2+, Month 2)
⏳ Azure Marketplace (Tier 3+, Month 2)
⏳ Bigdata.com ecosystem (Enterprise, pending partnership)
⏳ PyPI / MCP Registry (all tiers)
⏳ QuantConnect community (algo traders)
⏳ SSRN author page → API link
⏳ Show HN (one launch post = thousands of signups)
```

---

## 17. KEY THEORETICAL PROPERTIES

**RSI Mathematical Properties (proven):**
1. **Boundedness:** RSI ∈ (0, 1] for all Ht ≥ 0
2. **Strict Monotonicity:** ∂RSI/∂Ht < 0 — rising hazard strictly reduces stability
3. **Convex Risk Response:** ∂²RSI/∂Ht² > 0 — multiple simultaneous risks trigger disproportionate de-risking
4. **Interpretability:** Position(t) = RSI(t) × Position_base — direct, unit-free scaling

**Soros Bound (Reflexivity Constraint):**
- Cassandra retains predictive edge below ~15% aggregate institutional adoption
- Above this threshold: Synthetic Jitter and Liquidity-Aware Scaling required

**Human Error Beta:** -0.80% annually — human overrides cost ~80bps/year. Defer to model when P_human - P_market < 0.30.

**Paranoia Tax:** ~1.2% annual drag from false positives. Mathematically justified — exceeded many times over by drawdown avoidance and alpha generation.

---

## 18. REPO STRUCTURE (Key Files)

```
src/cassandra_risk/
  becker_calibration.py         Efficiency gap constants + longshot compression
  monetary_subablation.py       Monetary bucket structural fixes
  geopolitical_subbucket.py     Sub-bucket geo calibration
  promotion_workflow.py         Governed promotion workflow (v0.6.2)
  signal_contract.py            Canonical SignalContract schema (Phase 6)

data/governed/
  signal_registry.json          Promoted contracts (source of truth)
  promotion_audit.csv           Full decision audit trail

outputs/
  becker_stack_summary.csv      All 5 stack rows (v0.5.4)
  risk_decomposition.csv        Downside dev, CVaR, monthly MDD (v0.5.5)
  monte_carlo/                  Bootstrap CI results (v0.5.8)

config/
  geopolitical_admission_policy.json

docs/adr/
  ADR-005-calibration-architecture.md   Frozen calibration decisions

paper/
  CassandraRiskV1PreprintDraft.md
```

---

## 19. SESSION STATE (as of 2026-04-02, 00:05 IST)

```
Last clean tag:    v0.5.7-geo-subbucket-calibration (8ec3f50)
Live API version:  v1.0.0 on Railway
Marketplace:       RapidAPI ✅ | Zyla ✅
Subscribers:       1 (RapidAPI Basic)
Bigdata.com:       Trial requested, confirmation received
MCP:               Zyla auto-MCP live | Dedicated MCP = next build after Tier 2

Active papers:
  Paper 1 ✅ DOI live
  Paper 2 ✅ DOI live
  Paper 3 🔨 In progress (ensemble monetary result)
  Paper 4 📋 Pending Bigdata.com trial access

Next tag:          v0.7.0-tier2-endpoints
Next session goal: Tier 2 API build (history + ensemble + decomposition)
```

### Enterprise Tier 1 Note

- Shipping box is the full stacked V5 signal, not Becker-only
- Client message: **Paper 1 is the proof of concept. Enterprise Tier 1 is the production signal.**
- Enterprise release tag to use when promoted: `v1.0.0-enterprise-tier1`
- Azure Marketplace posture: use a near-zero Azure architecture for Enterprise
  Tier 1, separate from the Railway consumer surface
- Near-zero Azure default:
  - Static Web Apps for landing page
  - Azure Functions Consumption for webhook and fulfillment
  - Azure Container Apps Consumption for enterprise API
  - minimal storage + Key Vault for subscription state and secrets
- Goal: keep enterprise listing purchasable off the shelf with minimal idle
  spend until real buyers arrive

---

*This document supersedes CASSANDRA RISK — FULL SESSION CONTEXT v0.5.8.*  
*Maintained by Umran Nayani. Commit to repo at: `docs/CASSANDRA_MASTER_CONTEXT_v2.md`*
