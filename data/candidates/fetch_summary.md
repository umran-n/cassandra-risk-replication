# Phase 5a Polymarket Historical Ingestion

- Sample window: `2020-01-01` to `2025-01-10`
- Events scanned: `10186`
- Markets scanned: `23811`
- Category gate pass (`category != noise`): `1492`
- Horizon gate pass (`days_to_resolution <= 180`): `23098`
- Probability gate pass: `139`
- Eligible candidates written: `139`
- Fetch errors logged: `0`

## Gate Assumption

- Probability gate interpreted as: `interpreted as 0.15 <= P <= 0.85 for at least one history point`

## Structural Theme Counts

- `monetary_policy`: `53`
- `geopolitical`: `43`
- `electoral`: `41`
- `fiscal_debt`: `1`
- `trade_technology`: `1`

## Top 10 Candidates by Quality Score

| Rank | market_id | structural_theme | category | quality_score | question |
| --- | --- | --- | --- | ---: | --- |
| 1 | `501872` | `geopolitical` | `Kinetic` | 0.807841 | Israel military action against Iran by end of 2024? |
| 2 | `507792` | `geopolitical` | `Kinetic` | 0.766695 | Israel x Hezbollah Ceasefire in 2024? |
| 3 | `252598` | `geopolitical` | `Kinetic` | 0.766029 |  Israel and Hamas ceasefire in 2023? |
| 4 | `253299` | `monetary_policy` | `Monetary` | 0.763851 | Fed rate cut by May 1? |
| 5 | `504492` | `monetary_policy` | `Monetary` | 0.761810 | Fed decreases interest rates by 25 bps after November 2024 meeting? |
| 6 | `504642` | `geopolitical` | `Kinetic` | 0.761660 | Israel x Hamas ceasefire in 2024? |
| 7 | `254174` | `geopolitical` | `Kinetic` | 0.750759 | Israel x Hamas ceasefire before March? |
| 8 | `253462` | `electoral` | `Sovereign` | 0.748848 | Will U.S. Supreme Court vote to reinstate Trump on Colorado's 2024 ballot? |
| 9 | `248209` | `monetary_policy` | `Monetary` | 0.748687 | Will the Fed increase interest rates by 75 bps after its February meeting? |
| 10 | `504070` | `monetary_policy` | `Monetary` | 0.742338 | Fed decreases interest rates by 25 bps after September 2024 meeting? |
