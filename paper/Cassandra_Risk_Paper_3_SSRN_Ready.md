# Cassandra-Risk Paper 3: From Forecast Overlay to Governed Signal Infrastructure

## SSRN Preprint Draft

**Author:** Umran Nayani  
**Citation:** Nayani, U. (2026c). *Cassandra-Risk Paper 3: From Forecast Overlay to Governed Signal Infrastructure.* Working paper. GitHub preprint draft.  
**Codebase milestone:** `v0.6.4-market-ready` (`407f472`)  
**License:** Manuscript draft pending publication venue

## Abstract

Paper 1 established that a sparse, governed public reconstruction of Cassandra-Risk could generate directionally compelling risk-adjusted results from prediction-market event probabilities. Paper 2 expanded that event universe, documented the resulting degradation, and recovered a coherent three-layer architecture consisting of monetary calibration, targeted hazard pruning, and structural concentration caps. Paper 3 asks the next necessary question: when does a promising risk framework become a governed signal service rather than a backtest artifact?

This paper documents the Phase 6 build-out of Cassandra-Risk into a multi-source, promotion-gated, API-deliverable signal system. The core contribution is architectural rather than parametric. A canonical `SignalContract` schema is introduced as the single unit of signal across Polymarket, Kalshi, Metaculus, and Manifold adapters. Around that schema, the system adds a governed signal registry, a promotion workflow with full audit trail, a boundary-tested contract normalization layer, deterministic family selection keyed on explicit `aggregation_policy`, and a market-ready API surface that separates public signal consumption from operator-only governance actions.

The central empirical result of Paper 3 is not a new backtest. It is the elimination of hidden implementation discretion. During the `SignalContract` migration, a previously implicit family tie-break dependency was surfaced: a geopolitical family representative was changing as a function of dict ordering rather than an explicit aggregation rule. Formalizing family representation as an `aggregation_policy`-aware selector, and backfilling policy fields across 54 governed registry rows, made the live RSI path deterministic and auditable. As of March 26, 2026, the live governed service emits three active signals, a current RSI of 0.1007, and a full source-of-truth registry exposed through a hardened Tier 1 API.

The contribution of Paper 3 is therefore to move Cassandra-Risk from empirical strategy research toward infrastructure-grade signal governance. The system now has typed signal boundaries, explicit operator controls, public/operator route separation, rate-limited API delivery, and a manuscript-level architecture record that explains exactly which components are production-ready and which remain future work. Paper 4 will address ensemble weighting and cross-platform overlap resolution. Paper 3 establishes the governed data plane required for that step.

**Keywords:** prediction markets, signal infrastructure, API governance, event-driven risk management, calibration, market microstructure, software architecture

**Suggested JEL Codes:** G11, G17, C53, D84, C88

## 1. Introduction

The first two Cassandra-Risk papers asked whether event-implied fragility could be transformed into a usable risk overlay. Paper 3 asks whether that overlay can be operationalized as a governed signal service without losing the epistemic discipline that made the research credible in the first place. This is a different class of problem. A backtest can tolerate manual curation, implicit data conventions, and operator intuition. A signal API cannot. The moment Cassandra is exposed as a service, every hidden assumption becomes part of the product. Every undocumented fallback becomes a governance risk.

That shift in emphasis is what makes this paper necessary. The question is no longer only whether prediction-market probabilities contain actionable macro-risk information. The question is whether those probabilities can be ingested, normalized, governed, and delivered in a way that is deterministic, auditable, and product-safe. In practical terms, Paper 3 is about contract identity, source boundaries, operator controls, auditability, and live route hardening. It is about whether Cassandra can stop being only a research result and start becoming a dependable interface.

The answer reported here is positive but deliberately bounded. Cassandra-Risk is now capable of governed live signal delivery. It is not yet a full multi-source ensemble engine. The system can ingest live markets, preserve discovered candidates outside the governed RSI, promote contracts into the live book with a recorded decision trail, and publish a market-ready public API with access controls. What remains unfinished is the overlap-aware ensemble layer and full production Kalshi and Metaculus integration. Paper 3 therefore documents a transition point: Cassandra has become a governed signal platform, but not yet the final autonomous multi-source oracle envisioned in the Phase 6 specification.

## 2. Starting Point from Paper 2

Paper 2 concluded with three relevant outputs.

1. A three-layer public best stack: monetary Becker calibration, top-5 monetary hazard removal, and a 30 percent monetary bucket cap.
2. A governed geopolitical extension that improved the stack when left uncalibrated but degraded under both flat and sub-bucket geopolitical calibration.
3. A live systems insight: the next bottleneck was not another parameter sweep, but a unified signal architecture capable of ingesting, linking, governing, and publishing current event contracts.

The Paper 2 endpoint therefore left Cassandra in an analytically strong but operationally incomplete state. The research logic was clear, yet the live layer still depended on multiple file shapes, platform-specific assumptions, and manually curated transitions between discovery and governance. Paper 3 begins from that endpoint.

## 3. Research Questions

Paper 3 addresses five questions.

1. What canonical signal object is required so that multiple prediction-market sources can coexist without leaking platform-native logic into the RSI engine?
2. Can live discovery, governed admission, and signal publication be separated into distinct layers with explicit operator control?
3. What hidden implementation dependencies appear when the live pipeline is forced through a typed schema?
4. Can those dependencies be resolved in a way that is deterministic, auditable, and bounded by tests rather than operator convention?
5. Is the resulting service sufficiently hardened to package as a Tier 1 public API product?

## 4. System Design

### 4.1 The architectural problem

Phase 5 worked with Polymarket alone because one source can hide a great deal of inconsistency. Phase 6 could not. Polymarket, Kalshi, Metaculus, and Manifold differ in authentication, market metadata, resolution semantics, and signal quality. Without a canonical schema, every new source would force another branch into the live pipeline. That would make the service brittle by design.

The central architectural decision of Paper 3 is therefore simple: the RSI engine must consume only one canonical signal object. Everything upstream of that object is adapter logic. Everything downstream is governed aggregation and delivery. Platform identity must not leak into the RSI calculation itself.

### 4.2 The `SignalContract` schema

Paper 3 formalizes this boundary through the `SignalContract` dataclass in `src/cassandra_risk/signal_contract.py`. The schema includes:

- identity: `contract_id`, `source`, `provenance_tier`
- question and governance metadata: `question_text`, `structural_theme`, `proxy_family_id`, `aggregation_policy`
- probabilities: `probability_raw`, `probability_calibrated`, `efficiency_gap_applied`
- temporal fields: `created_at`, `resolves_at`, `resolved_outcome`
- quality fields: `volume_usd`, `quality_score`, `is_binary`, `is_macro_relevant`
- operational metadata: `last_updated`, `snapshot_timestamp`

The significance of this object is not just typing. It is containment. Before migration, live discovery and governance paths were still vulnerable to dict-shaped payload drift. After migration, contract identity, probabilities, temporal fields, and themes all live in one place. This allows the promotion layer, registry layer, and API layer to pass around a single canonical object rather than loosely coupled field maps.

### 4.3 Promotion workflow as governance boundary

The live system is intentionally not fully automatic. Discovered contracts do not silently enter the live RSI. They pass through a promotion workflow, implemented in `src/cassandra_risk/promotion_workflow.py`, that wraps a `SignalContract` inside a `PromotionCandidate` and adds only promotion-specific state:

- gate results
- quality score
- auto-recommendation
- human decision metadata

This is the correct relationship. `PromotionCandidate` contains a `SignalContract`; it does not duplicate it. That design closes the drift seam between discovery and governance. Approval is therefore just promotion of `candidate.contract` into the governed registry, not translation into a second contract representation.

### 4.4 Governed registry and audit trail

Approved contracts are written to a single machine-readable governed source of truth in `data/governed/signal_registry.json`, with decisions recorded in `data/governed/promotion_audit.json` and `data/governed/promotion_audit.csv`. This registry replaces the old split between manually curated shortlist JSONs and ad hoc override files.

The governed registry now performs two roles:

- source of truth for live signal families
- governance ledger for what has been admitted into the live service

That matters because a product API cannot rely on implicit curation state scattered across the repo. The signal registry creates one canonical checkpoint between human review and live RSI publication.

### 4.5 Public versus operator surfaces

By the end of this paper's build arc, Cassandra exposes two distinct service layers from the same server in `api/app.py`.

**Public Tier 1 routes**

- `GET /v1/meta`
- `GET /v1/registry/governed`
- `GET /v1/rsi/latest`
- `GET /v1/signals/latest`
- `GET /v1/signals/latest/{event_family_id}`
- `GET /v1/sources/status`

**Operator-only routes**

- `GET /v1/meta/registry`
- `GET /v1/sources/markets`
- `GET /v1/events/families`
- `GET /v1/candidates/discovered`
- `GET /v1/graph/link-audit`
- `GET /v1/admin/promotion/queue`
- `GET /v1/admin/promotion/audit`
- `POST /v1/admin/promotion/decide`
- `POST /v1/admin/promotion/decide/batch`
- `POST /v1/admin/refresh`

That split is part of the research contribution. The product surface is intentionally narrower than the research surface.

## 5. Implementation Chronology

Table 1 summarizes the Phase 6 implementation arc.

| Milestone | Commit / Tag | Main contribution |
| --- | --- | --- |
| `v0.6.0-unified-signal-api` | `d613de5` | Source registry, event graph, signal engine foundation, local API shell |
| `v0.6.1-live-query-api` | `4cb7f16` | Expanded live query surface, temporal guard against stale family linking |
| `v0.6.2-promotion-workflow` | `8b7331a` | Review queue, decision audit, governed signal registry |
| `v0.6.3-signal-contract-schema` | `bf6325a` | Canonical `SignalContract`, boundary tests, explicit family selection governance |
| `v0.6.4-market-ready` | `407f472` | Public/operator route split, API-key auth, rate limiting, Tier 1 surface |

This progression matters because Paper 3 is not a theoretical architecture note written after the fact. It is the documented history of how Cassandra acquired typed boundaries and service governance in stages.

## 6. Boundary Testing as Method

The core methodological contribution of Paper 3 is not just the schema itself, but the enforcement structure around it. A boundary test pyramid was added to ensure the architecture remained coherent as the API became public-facing.

### 6.1 Schema gate

The schema gate in `tests/test_signal_contract.py` verifies:

- contract ID format
- probability bounds
- provenance tier validity
- theme validity
- aggregation policy validity
- temporal consistency
- quality-score bounds

### 6.2 Architectural boundary gate

The architectural gate in `tests/test_architectural_boundaries.py` verifies:

- adapters emit `SignalContract`, not dicts
- no raw dict reaches the RSI engine
- the RSI engine has no source conditionals
- platform-native fields are stripped during normalization
- Manifold remains archive-only
- registry family deduplication works
- Becker calibration only modifies the calibrated field

### 6.3 API contract gate

The API contract suite in `tests/test_api_contract.py` verifies:

- public metadata routes require an API key
- operator routes reject public-only credentials
- public rate limiting returns `429`
- approved promotions reach the governed registry
- promotion changes the published RSI from unity in isolated test environments

By `v0.6.4`, the full suite reached 102 passing tests.

## 7. Results

### 7.1 Live signal service state

As of March 26, 2026, the live governed service state is:

- governed families in registry: `54`
- active governed signals: `3`
- current RSI: `0.1006928493`
- total hazard: `8.9311918086`
- dominant theme: `geopolitical`

Active governed signals at that snapshot:

| Event family | Source | Probability | Calibration |
| --- | --- | ---: | --- |
| `geopolitical_another_israeli_military_action_against_iran_in_2024_2025` | Polymarket `1551490` | `0.86` | none |
| `geopolitical_russia_x_ukraine_ceasefire_in_2024_2025` | Polymarket `561829` | `0.005` | none |
| `monetary_policy_fed_emergency_rate_cut_in_2024_2025` | Polymarket `616903` | `0.26` | Becker |

This is not a backtest artifact. It is live service output from the governed book written under `outputs/signals/`.

### 7.2 Honest emptiness as a governance result

One of the most important early Paper 3 results is that the live RSI initially returned exactly `1.0000` when no promoted governed signals were active. This was not treated as a failure. It was treated as evidence that the governance barrier was functioning correctly: discovery existed, but nothing crossed into the live signal without admission.

That is a subtle but important systems result. A signal service that emits nothing until governed inputs exist is more trustworthy than one that silently promotes discovered candidates just to keep the dashboard non-empty.

### 7.3 The hidden family-selection dependency

The most technically important result of Paper 3 appeared during the `SignalContract` migration. A regression check showed that the live RSI moved sharply when the migration was first applied. The cause was not numerical drift. The cause was that family representative selection had been depending on implicit dict ordering. Once contracts became typed objects, the same family began selecting a different representative.

The key family was a geopolitical Iran/Israel escalation cluster. Pre-migration, it selected a low-probability cold contract. Post-migration, it selected a high-probability hot contract. The migration therefore surfaced a hidden governance decision that had never been formalized: what does it mean for one contract to represent a family?

This was resolved in `v0.6.3` by:

- backfilling `aggregation_policy` across all 54 governed rows
- defining an explicit `select_family_representative(...)` function in `src/cassandra_risk/signal_engine.py`
- enforcing a mixed-policy guard
- selecting family representatives according to policy rather than insertion order

For `weighted_average` families, representative selection now anchors on highest volume. For `max` families, it anchors on highest calibrated probability. The result is not that the live RSI stayed numerically identical. The result is that it became deliberate, deterministic, and auditable.

### 7.4 Backfill result

The registry backfill result is itself noteworthy:

- governed registry rows: `54`
- rows requiring `aggregation_policy` backfill: `54`
- backfill audit marker: `_policy_backfilled = true`

This is not embarrassing. It is the expected outcome of migrating a research-stage governed universe into a typed service-stage registry. Paper 3 treats it as a governance improvement rather than a bug fix.

### 7.5 Market-ready hardening

The `v0.6.4-market-ready` hardening pass added:

- public API-key auth for Tier 1 routes
- operator-key protection for governance routes
- in-memory rate limits for public endpoints
- a public `/v1/meta` route exposing version and signal counts
- a public `/v1/registry/governed` route exposing the governed family registry

That is enough for a first commercial tier. It is intentionally not a billing stack, not a multi-tenant entitlement system, and not yet an enterprise deployment story. But it is a real service boundary that can be listed and sold in a controlled developer-marketplace setting.

## 8. Interpretation

Paper 3's main contribution is not "the API works." It is that Cassandra now has explicit boundaries where it previously had conventions.

There are three ways to understand the progression from Paper 2 to Paper 3:

1. **Research continuity.** The API service does not replace the research stack. It inherits the same governed event logic, calibration rules, and theme caps.
2. **Governance improvement.** The migration surfaced a hidden implementation dependency and replaced it with a tested, documented selector.
3. **Commercial readiness.** The service is now sufficiently explicit to support a paid entry tier without pretending to be fully autonomous institutional infrastructure.

This is why Paper 3 matters. In financial signal products, the absence of explicit boundaries is often a larger source of risk than the model itself. Cassandra's Phase 6 work narrowed that risk materially.

## 9. Limitations

Paper 3 still leaves three major limitations unresolved.

### 9.1 No ensemble layer yet

The live system still does not perform overlap-aware source ensembling. A Polymarket and Kalshi contract pricing the same FOMC event do not yet collapse into a weighted ensemble signal. The API is therefore multi-source capable but not yet multi-source optimal.

### 9.2 Kalshi and Metaculus are architecture-ready, not fully production-complete

The schema and adapter structure are in place, but the full cross-platform ingest story remains incomplete until:

- Kalshi RSA-PSS market and history retrieval is production-complete
- Metaculus authenticated forecast ingest is fully wired into the live service

Paper 3 therefore documents an architecture ready for those sources, but not the final overlap result expected in Paper 4.

### 9.3 Hardening is marketplace-grade, not enterprise-grade

The current service has:

- route gating
- keys
- rate limits
- audit trails

It does not yet have:

- billing and usage metering
- key rotation flows
- persistent distributed rate limiting
- high-availability deployment
- operational alerting

This is sufficient for a Tier 1 developer product, not yet for institutional SLA claims.

## 10. Conclusion

Paper 1 showed that Cassandra-Risk could survive public reconstruction. Paper 2 showed that it could survive expansion, diagnosis, and controlled remediation. Paper 3 shows that it can survive operationalization.

The key result is not another headline Sortino number. It is that the system now has a governed data plane. `SignalContract` gives Cassandra a canonical unit of signal. The promotion workflow gives it a disciplined admission boundary. The governed registry gives it a single source of live truth. The family selector gives it deterministic representation. And the hardened API gives it a sellable surface without collapsing operator control into public access.

This is the correct endpoint for the current phase. Cassandra is no longer only a research architecture with good papers behind it. It is now a governed signal service whose live outputs, decision boundaries, and implementation seams are all explicit enough to audit. That is what earns the right to sell the signal.

Paper 4 will address the next unresolved step: overlap-aware source ensembling across regulated and unregulated venues, with explicit source weighting and cross-platform validation. Paper 3 establishes the infrastructure base required for that work to be meaningful.

## Appendix A. Public Tier 1 API Surface at `v0.6.4`

Public endpoints:

- `GET /health`
- `GET /v1/meta`
- `GET /v1/registry/governed`
- `GET /v1/rsi/latest`
- `GET /v1/signals/latest`
- `GET /v1/signals/latest/{event_family_id}`
- `GET /v1/sources/status`

Operator endpoints:

- `GET /v1/meta/registry`
- `GET /v1/sources/markets`
- `GET /v1/events/families`
- `GET /v1/candidates/discovered`
- `GET /v1/graph/link-audit`
- `GET /v1/admin/promotion/queue`
- `GET /v1/admin/promotion/audit`
- `POST /v1/admin/promotion/decide`
- `POST /v1/admin/promotion/decide/batch`
- `POST /v1/admin/refresh`

## Appendix B. Repo Artifacts Relevant to Paper 3

- `src/cassandra_risk/signal_contract.py`
- `src/cassandra_risk/signal_engine.py`
- `src/cassandra_risk/promotion_workflow.py`
- `src/cassandra_risk/promotion_store.py`
- `api/app.py`
- `data/governed/signal_registry.json`
- `data/governed/promotion_audit.json`
- `outputs/signals/rsi_snapshot.json`
- `outputs/signals/signal_snapshots.json`
- `tests/test_signal_contract.py`
- `tests/test_architectural_boundaries.py`
- `tests/test_api_contract.py`
