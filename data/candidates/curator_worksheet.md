# Curator Worksheet Summary

- Source: `data/candidates/polymarket_candidates.json`
- Sorted by theme, then `total_volume_usd` descending
- `suggested_action` defaults to `REVIEW`, uses `REVIEW_CAP` for electoral rows, and appends `LOW_LIQUIDITY` when `total_volume_usd < 10000`.
- `num_traders` is left blank when unavailable in the source candidate payload.

## electoral

| Rank | title | resolution_date | peak_probability | probability_range | total_volume_usd | num_history_points | suggested_action |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | Will Republicans have between 220 and 224 seats in House after election? | 2024-12-04 | 0.982500 | 0.922500 | 347290.68 | 111 | REVIEW_CAP |
| 2 | Will Republicans have between 215 and 219 seats in House after election? | 2024-12-04 | 0.375000 | 0.369000 | 344808.70 | 111 | REVIEW_CAP |
| 3 | Will Nigel Farage win election to UK parliament? | 2024-07-05 | 0.972500 | 0.282500 | 326337.44 | 32 | REVIEW_CAP |
| 4 | Will Republicans have 230 or more seats in House after election? | 2024-12-04 | 0.300000 | 0.299500 | 247672.60 | 111 | REVIEW_CAP |
| 5 | Will U.S. Supreme Court vote to reinstate Trump on Colorado's 2024 ballot? | 2024-03-04 | 0.920000 | 0.685000 | 244342.63 | 75 | REVIEW_CAP |
| 6 | Will Republicans have between 225 and 229 seats in House after election? | 2024-12-04 | 0.335000 | 0.334500 | 185403.96 | 111 | REVIEW_CAP |
| 7 | Will Fischer win Nebraska senate election by 7+ points? | 2024-12-02 | 0.950000 | 0.934500 | 172535.87 | 33 | REVIEW_CAP |
| 8 | Will Republicans have fewer than 200 seats in House after election? | 2024-12-04 | 0.210000 | 0.209500 | 125095.79 | 111 | REVIEW_CAP |
| 9 | Will Republicans have between 210 and 214 seats in House after election? | 2024-12-04 | 0.500000 | 0.499500 | 117571.68 | 111 | REVIEW_CAP |
| 10 | Will Republicans have between 205 and 209 seats in House after election? | 2024-12-04 | 0.560000 | 0.559500 | 112828.85 | 111 | REVIEW_CAP |
| 11 | Will Donald Trump be President of the USA on November 30, 2023? | 2023-12-01 | 0.500000 | 0.499500 | 110640.79 | 127 | REVIEW_CAP |
| 12 | Will Cyril Ramaphosa be the next President of South Africa? | 2024-06-15 | 0.999500 | 0.724500 | 97507.33 | 64 | REVIEW_CAP |
| 13 | Will Republicans have between 200 and 204 seats in House after election? | 2024-12-04 | 0.515000 | 0.514500 | 89222.38 | 111 | REVIEW_CAP |
| 14 | Will VB win the most seats in the Belgian federal elections? | 2024-06-11 | 0.965000 | 0.964500 | 70561.55 | 35 | REVIEW_CAP |
| 15 | Will the N-VA win the most seats in the Belgian federal elections? | 2024-06-11 | 0.995000 | 0.973500 | 38209.94 | 35 | REVIEW_CAP |
| 16 | Jeremy Corbyn elected to parliament in UK election? | 2024-07-05 | 0.830000 | 0.505000 | 37952.52 | 42 | REVIEW_CAP |
| 17 | Will Garvey win the California Senate Primary by between 0-2% of the vote? | 2024-04-13 | 0.720000 | 0.714000 | 37592.34 | 37 | REVIEW_CAP |
| 18 | Trump sentenced to house arrest? | 2024-11-05 | 0.435000 | 0.432500 | 36124.71 | 158 | REVIEW_CAP |
| 19 | Will another non-ANC candidate be the next President of South Africa? | 2024-06-15 | 0.499000 | 0.498500 | 32786.53 | 64 | REVIEW_CAP |
| 20 | Labour wins 30-35% of votes? | 2024-07-06 | 0.974000 | 0.939000 | 31262.22 | 44 | REVIEW_CAP |

## fiscal_debt

| Rank | title | resolution_date | peak_probability | probability_range | total_volume_usd | num_history_points | suggested_action |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | US debt ceiling hike by July 1? | 2023-06-03 | 0.995000 | 0.815000 | 108835.70 | 37 | REVIEW |

## geopolitical

| Rank | title | resolution_date | peak_probability | probability_range | total_volume_usd | num_history_points | suggested_action |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | Israel x Hezbollah Ceasefire in 2024? | 2024-12-05 | 0.999500 | 0.749500 | 40061277.63 | 72 | REVIEW |
| 2 | Will Israel invade Syria in 2024? | 2024-12-21 | 0.999500 | 0.982500 | 16819559.74 | 99 | REVIEW |
| 3 | Will Israel invade Lebanon before November? | 2024-10-06 | 0.999500 | 0.909500 | 5313533.73 | 60 | REVIEW |
| 4 | Israel x Hamas ceasefire in 2024? | 2025-01-01 | 0.670000 | 0.667000 | 3950958.94 | 147 | REVIEW |
| 5 | Russia x Ukraine Ceasefire in 2024? | 2025-01-01 | 0.215000 | 0.214000 | 3514408.22 | 107 | REVIEW |
| 6 | Another Iran strike on Israel in 2024? | 2025-01-01 | 0.670000 | 0.669500 | 3168665.69 | 67 | REVIEW |
| 7 | Another Iran strike on Israel in October? | 2024-11-01 | 0.585000 | 0.579500 | 1770275.94 | 30 | REVIEW |
| 8 | Another Israeli military action against Iran in 2024? | 2025-01-01 | 0.695000 | 0.692000 | 1660869.00 | 65 | REVIEW |
| 9 | Will Israel invade Lebanon before September? | 2024-09-01 | 0.645000 | 0.644500 | 1345780.16 | 95 | REVIEW |
| 10 | Iran strike on Israel before December? | 2024-12-01 | 0.530000 | 0.527500 | 1317271.58 | 31 | REVIEW |
| 11 | U.S. military action against Iran before November? | 2024-11-01 | 0.155500 | 0.151000 | 1070645.35 | 39 | REVIEW |
| 12 | Israel x Hamas ceasefire before September? | 2024-09-01 | 0.715000 | 0.713000 | 972382.17 | 95 | REVIEW |
| 13 | Israel military action against Iran by end of 2024? | 2024-10-26 | 0.988500 | 0.773500 | 934236.52 | 150 | REVIEW |
| 14 | Israel withdraws from Gaza in 2024? | 2025-01-01 | 0.300000 | 0.298500 | 501887.10 | 75 | REVIEW |
| 15 | U.S. military action against Iran in 2024? | 2025-01-01 | 0.195000 | 0.191500 | 495157.12 | 71 | REVIEW |
| 16 | Iran military response before October? | 2024-10-01 | 0.520000 | 0.513000 | 467982.23 | 42 | REVIEW |
| 17 | Will Israel invade Lebanon before March? | 2024-03-01 | 0.220000 | 0.217000 | 408699.99 | 42 | REVIEW |
| 18 | Ceasefire between Russia and Ukraine before October? | 2024-10-01 | 0.195000 | 0.193500 | 315612.94 | 130 | REVIEW |
| 19 | Israel declares war on Iran in October? | 2024-11-01 | 0.150000 | 0.148000 | 269771.90 | 31 | REVIEW |
| 20 | Will Ukraine sever the land bridge between Crimea and Russia before Nov 1? | 2023-11-01 | 0.360000 | 0.357500 | 249080.32 | 147 | REVIEW |

## monetary_policy

| Rank | title | resolution_date | peak_probability | probability_range | total_volume_usd | num_history_points | suggested_action |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | No change in Fed interest rates after 2024 September meeting? | 2024-09-18 | 0.155000 | 0.142000 | 23499210.73 | 55 | REVIEW |
| 2 | Fed decreases interest rates by 50+ bps after September 2024 meeting? | 2024-09-18 | 0.590000 | 0.525000 | 10906333.42 | 55 | REVIEW |
| 3 | Fed decreases interest rates by 50 bps after December 2024 meeting? | 2024-12-18 | 0.410000 | 0.407500 | 9192309.53 | 134 | REVIEW |
| 4 | Fed decreases interest rates by 50 bps after November 2024 meeting? | 2024-11-07 | 0.515000 | 0.494000 | 8393267.79 | 97 | REVIEW |
| 5 | No change in Fed interest rates after 2024 November meeting? | 2024-11-07 | 0.225000 | 0.202000 | 7995206.76 | 97 | REVIEW |
| 6 | Fed decreases interest rates by 25 bps after December 2024 meeting? | 2024-12-18 | 0.971500 | 0.556500 | 7490697.07 | 134 | REVIEW |
| 7 | No change in Fed interest rates after December 2024 meeting? | 2024-12-18 | 0.405000 | 0.378500 | 7400313.75 | 134 | REVIEW |
| 8 | Fed decreases interest rates by 25 bps after September 2024 meeting? | 2024-09-18 | 0.905000 | 0.530000 | 6660914.25 | 55 | REVIEW |
| 9 | Fed decreases interest rates by 25 bps after November 2024 meeting? | 2024-11-07 | 0.953500 | 0.638500 | 5010507.07 | 97 | REVIEW |
| 10 | Fed rate cut by March 20? | 2024-03-21 | 0.630000 | 0.626500 | 1907759.26 | 94 | REVIEW |
| 11 | Fed rate cut by July 31? | 2024-08-01 | 0.910500 | 0.909500 | 1727507.99 | 170 | REVIEW |
| 12 | Fed rate cut by May 1? | 2024-05-02 | 0.885000 | 0.884500 | 1608415.70 | 148 | REVIEW |
| 13 | Fed rate cut by June 12? | 2024-06-13 | 0.969500 | 0.969000 | 1253483.92 | 134 | REVIEW |
| 14 | Fed emergency rate cut in 2024? | 2025-01-01 | 0.270000 | 0.269500 | 835804.64 | 152 | REVIEW |
| 15 | Increase in ECB interest rates after 2024 December meeting? | 2024-12-12 | 0.165000 | 0.163500 | 399674.02 | 43 | REVIEW |
| 16 | Will Jerome Powell say "inflation" 50 or more times during December FOMC Press Conference? | 2024-12-18 | 0.620000 | 0.295000 | 387258.68 | 33 | REVIEW |
| 17 | Will the Fed increase interest rates by 0 bps after its June meeting? | 2023-06-14 | 0.940000 | 0.610000 | 243878.27 | 41 | REVIEW |
| 18 | >50 bps decrease in ECB interest rates after 2024 December meeting? | 2024-12-12 | 0.250000 | 0.247500 | 237073.15 | 43 | REVIEW |
| 19 | No change in ECB interest rates after 2024 December meeting? | 2024-12-12 | 0.500000 | 0.494000 | 203799.68 | 43 | REVIEW |
| 20 | Will the Fed raise interest rates by 25+ bps after its 2024 March meeting? | 2024-03-20 | 0.300000 | 0.298500 | 197105.48 | 49 | REVIEW |

## trade_technology

| Rank | title | resolution_date | peak_probability | probability_range | total_volume_usd | num_history_points | suggested_action |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | Will the Ethereum Merge (EIP-3675) occur by October 1, 2022? | 2022-09-15 | 0.500000 | 0.000000 | 622044.37 | 78 | REVIEW |
