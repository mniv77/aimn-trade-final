# AIMn / KISS — EXP40 research milestone and forward-validation handoff
**Date:** 2026-11-27 | **Checkpoint:** Step 276 | **Scope:** NVDA SHORT, 5-minute bars; research only.

## Executive summary
AM3 combines completed 30-minute SHORT SuperTrend context, local LONG AE3 warning, AJ1 next-candle lower-high/lower-close confirmation, and W12 relative retracement >= 0.60. Historical sequential replay yielded 17 trades, 11 winners, 6 losers, +0.946169% sum of net trade returns after 0.20% round-trip commission. This is not a portfolio return or independently validated profitability. AP reproduced exact historical trade, candidate and gate records across all three periods. No forward data has been scored. No production changes or orders authorized.

## Research evolution
| Experiment | Finding |
|---|---|
| EXP40 / B2 | Original V17: 124 trades, 29 wins, 95 losses, -38.355387%. Causal correction B2: 122 trades, 41 wins, 81 losses, -30.391587%. Avoid entry-bar lookahead and ambiguous intrabar trail updates; next-open execution and prior completed bar stop levels. |
| C–H | Directional efficiency, session history and opening context filters; H4 session protections reduced discovery net loss to -0.672133%. |
| I–K | Profit-preservation variants; K3 structural bullish upper-close exit, discovery -0.199296%. |
| L | Nov 16–25 holdout failed H4/K3 (-1.673977%); period subsequently became discovery. |
| M–T | SuperTrend for major context rather than timely entry trigger; TWO_STEP warning, Q4 directional efficiency, opening-history handling. |
| U–AA | Causal warning replay, first held candle invalidation, supplemental higher-high exit. AA1 and AA4 frozen. |
| AB–AD | Sep–Oct robustness failed; structural position and sequential trajectory measurements did not provide reliable discrimination. |
| AE–AH | AE3 peak warning improves timing in retrospectively matched cases; RSI/ST/low-break warning filters fail to generalize. |
| AI | Immediate AE3: 118 trades, 53 wins, 65 losses, -16.998179%. Retain AE3 as warning, not direct entry. |
| AJ | One-candle monitoring AJ1: 58 trades, 25 wins, 33 losses, -7.178589%. AJ2 -7.544668%; AJ3 -7.295186%; two-candle AJ4 -9.955271%. |
| AK | W6/W12 relative V-leg retracement medians higher for winners than no-fee-close losers in all three periods; W24 inconsistent. |
| AL | W12 >= .60 historical subset: 16 trades, 11 wins, +1.452008%; not sequential replay. Combined W12 AUC .634199; Nov .500, small sample. |
| AM | AM3 causal replay: 17 trades, 11 wins, 6 losses, +0.946169%. Freeze .60. |
| AN | Acceleration rejection hypothesis unsupported; winners had greater median acceleration in selected AM3 sample. |
| AO | SHORT-LONG-SHORT sequence more selective in AJ1 but AM3 subset net -0.443425%; no additional sequence filter. |
| AP | Exact AM3 historical parity passed, forward evaluation pending. |

## Frozen AM3 implementation
Reuse existing functions: m.snapshots, m.aggregate, ai.focus, aj.monitor(...,'AJ1'), am.features, aa.replay, ai.check, ab.metrics. AE3 requires local 5m LONG and completed 30m SHORT at warning. AJ1 confirms on next completed candle with lower high and lower close; original peak invalidation, major context loss, cutoff and session restrictions remain. Authorization can occur after local ST flips SHORT. W12 uses lowest low in fixed 12-bar preceding-peak lookback and reversal through authorization close; missing history blocks. Entry at next open; no new signals >=15:30; same-day flatten at 15:55 open; frozen AA exits including fixed/trailing protection, V_PROFIT, structural bullish upper close, RSI emergency and supplemental higher high. No W1/W3 invalidation. Preserve exact implementation rather than reimplementing from prose.

## Historical results
| Period | Trades | Wins | Losses | Net sum % |
|---|---:|---:|---:|---:|
| Jun–Aug | 11 | 6 | 5 | 0.181220 |
| Sep–Oct | 5 | 4 | 1 | 0.322873 |
| Nov 16–25 | 1 | 1 | 0 | 0.442076 |
| Combined | 17 | 11 | 6 | 0.946169 |

AA1 combined 31 trades, -1.305347%; AA4 48 trades, -1.035458%. AM3 additional cost sensitivity: +0.606169% at .02% per trade; +0.096169% at .05%; -0.753831% at .10%. Removing July 24 winner (+1.402595%) leaves -0.456426%. Five of six losers never covered commission at a completed close; one gave back small profit. All historical periods are discovery; threshold selection is in-sample. November contains only one AM3 trade. Discovery feed provenance is unverified and may differ from IEX. No claim of reliable profitability.

## Independent validation protocol (EXP40-AP)
Fixed regular-session cohort: Nov 30; Dec 1–4, 7–11, 14–18, 21–23, 28–29, 2026. 20 sessions, 1560 candles. Exclude shortened Nov 27 and Dec 24 sessions and holidays. Exclusion of shortened sessions from warm-up is a limitation. Collect NVDA 5m Alpaca IEX raw data, manifests and SHA256; no interim scoring or threshold changes. Existing EXP40-L downloader accepts --start and --last but assumes full weekday sessions; collect individual sessions or uninterrupted regular-session ranges. Verify completeness, timestamps and OHLC. Historical warm-up not scored. AP benchmark-only run passed exact parity on all periods; no forward output written. Evaluate fixed cohort after data complete; report results regardless, and assess sample adequacy without selectively stopping on profit. Any further cohort must be separately predefined. Inspect AP CLI before evaluation.

## Recorded SHA256 fingerprints
```
aimn_exp40ai_early_transition_replay.py a2af1e958a26bfd7696216180b4d8c7b4339de7f62126f27ffb6e3d3376aae65
aimn_exp40aj_transition_monitoring_replay.py b6dc48d9f33b59f4f2ea6f388357d1ddb34138ba80dfec3649f5043f74f9a05f
aimn_exp40ak_relative_v_leg_forensics.py 7caf8f2ef059179348754f75c16111429228b7f5c1d0657dc5e45fe0d4ab9e9f
aimn_exp40al_trajectory_discrimination.py b5e7760020314ee1ebdd23d23c99358db97c880b74f4637b48fa5133d7efe5ac
aimn_exp40am_relative_trajectory_replay.py f19067752e1a917da0a277a9bf4e363e57632b9fced7eac8ce4f28a0c382b79f
kiss/results/exp40am_relative_trajectory_replay/summary.json 55a3bf0e544ae668ed4b147e837ec01187dc336cec60e04dcb46dca0119bc547
aimn_exp40ap_forward_validation.py 1384d301e56b7465462d02be4b9ba299189a63a8c6ada200d37d875aeb4fad6a
```

## Next work
1. Save this report under doc/strategy and inspect Git status. Stage only explicitly reviewed research source/report/artifacts; do not use git add --all, reset or clean. Existing unrelated changes must be preserved.
2. Prepare read-only AI Vision Replay research markers for historical AE3 warnings, AJ1 confirmation, W12 value, AM3 gate decisions and executed entries/exits. Keep historical outcome labels separate from causal signals. Do not expose AP interim outcomes.
3. Collect independent data according to frozen cohort; do not optimize AM3 while waiting. Other Alpaca symbols are separate generalization research, Gemini later.

Repository: mniv77/aimn-trade-final; PAW project ~/aimn-trade-final; branch kiss-transition-detector-v5-6-6-final. Current remote synchronization of EXP40 scripts has not been verified. This report is based on conversation execution logs and earlier research summaries, not a fresh repository inspection. Preserve complete source files and existing reports as authoritative records.
