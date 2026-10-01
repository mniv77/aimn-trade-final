# AATA / AiMn Trading Project — HANDOFF REPORT
## 2026-09-01

This document is a handoff for a new ChatGPT conversation. Read this first, then inspect the latest dated strategy documents and code in this folder/repository. Do not make the user repeat the project history.

## 1. Project

Repository: `mniv77/aimn-trade-final`

The project is the AiMn automated trading system / AATA (AI Autonomous Trading Academy). The current strategic focus is a deliberately simple KISS strategy rather than a large collection of traditional indicators.

Core philosophy: **KISS — Keep It Simple.**

The strategy is based primarily on market direction and transitions:
- LONG = rising trend
- SHORT = falling trend
- FLAT = sideways

The important event is the **transition**, not the visual shape itself.

Ideal visual examples:
- **V-Long** = falling → rising; the bottom is the ideal transition area.
- **V-Short** = rising → falling; the top is the ideal transition area.
- Other shapes can be M, W, U, inverted U, mountain-like, irregular, etc. Shape is descriptive only; transition is the strategy.

## 2. Entry Rules

Entries are made on:
- SHORT → LONG
- LONG → SHORT
- FLAT → LONG
- FLAT → SHORT

LONG → FLAT and SHORT → FLAT are not entry signals; they are treated as waiting/sideways situations.

The goal is to enter as close as reasonably possible to the real trend transition. Entering too late can mean most of the profitable move has already happened and the trade may only cover commission or become a loser.

## 3. Exit Rules

The desired exit is another meaningful trend transition.

Trailing take-profit / retracement is useful because it can identify a possible reversal, but **one small reversal is not automatically a real global trend change**. Minor local reversals are noise and may be ridden out.

A meaningful reversal should survive a small confirmation/safety zone (the working idea has been roughly 2–4 candles) before a normal trailing exit is accepted.

However, an unusually violent move against the trade can require immediate protection.

## 4. Emergency Protection

RSI is NOT the strategy.

It is an emergency circuit breaker for extraordinary moves where waiting to establish a normal trend transition is too slow.

Examples discussed:
- LONG position + catastrophic negative news → price can fall extremely quickly; RSI should help force an emergency exit.
- SHORT position + extraordinary positive news → price can jump violently; RSI should help force an emergency exit.

Stop-loss remains another final safety mechanism.

## 5. Key Architectural Idea — WHAT vs WHEN

A major insight reached during testing:

**30-minute candles may be used to decide WHAT the major/global trend is.**

**5-minute candles may be used to decide WHEN to execute.**

Reason:
- 30m gives a stable major-trend view and reduces local noise.
- 5m gives 6× more timing resolution than 30m.
- Fast V transitions and price jumps can occur largely inside one 30m candle.
- Waiting for the 30m candle/confirmation can therefore produce entries that are visibly too late and exits that are visibly too late.

This is an experiment, NOT an assumption that 5m is better. The only valid answer comes from the backtest comparison.

The next clean comparison is:
**old/current KISS: 30m decision + 30m execution**
versus
**experiment: 30m decision + 5m execution**

Keep everything else the same.

## 6. Why NVDA Is the Laboratory

NVDA was deliberately chosen because its chart contains many fast V-shaped transitions and sudden jumps. It is therefore a good stress test for execution timing.

Observed problem in the initial KISS NVDA tests:
- direction could be broadly correct;
- entry could occur far too late;
- exit could occur far too late;
- the trade could therefore enter near the end of the move and leave after much of the move had reversed.

The user emphasized that losing trades are the important feedback. Winners do not need to dominate the review; the goal is to understand and reduce loser trades.

## 7. Existing KISS Backtest UI

The project now has an independent KISS backtest page with:
- Broker
- Symbol
- Direction
- Candle/timeframe
- total trades
- total P&L
- win rate
- loser count
- loser-only list
- individual Trade IDs
- chart with entry/exit markers
- entry/exit prices and times
- transition and exit reason
- max favorable/adverse excursion
- RSI at entry/exit

This was specifically built so the user can inspect losers and later provide feedback for AI training.

Example Trade IDs seen in testing: `KISS-0002`, `KISS-0003`, etc.

## 8. Current Independent Files

Important files added/modified for the clean KISS experiment:

- `engine/kiss_backtest.py` — initial independent KISS backtest engine.
- `kiss_backtest_routes.py` — independent routes and KISS button integration.
- `templates/kiss_backtest.html` — loser-focused report/chart.
- `engine/kiss_execution_5m.py` — 30m trend / 5m execution experiment.

The existing broker/symbol/direction selection machinery is considered working and should be treated as **do not touch unless proven broken**.

The existing Auto Tuner should not be rewritten merely to implement the KISS experiment. The KISS experiment is intentionally separate.

## 9. Important Existing Strategy Document

The repository contains the more complete KISS strategy document:

`doc/strategy/AiMn-KISS-Strategy-V3-full.md`

Its core architecture states:
- one strategy / one engine;
- different memories/notebooks for live, backtest, and tuner;
- trend transition rather than indicator soup;
- start from the newest candle and work backward to find the latest transition where possible;
- remember the previous trend/time so each subsequent scan only needs to inspect new candles rather than repeatedly traversing the whole history;
- RSI emergency only;
- trailing protection;
- separate memory for each application.

## 10. Database Concept

The user supplied these relevant MySQL tables:

- `active_trades`
- `ai_feedback`
- `ai_vision_log`
- `asset_states`
- `backtest_orders`
- `bot_active_state`
- `bot_indicators`
- `broker_products`
- `brokers`
- `candles`
- `global_symbols`
- `market_sessions`
- `ml_dataset`
- `note_categories`
- `orders`
- `strategy_params`
- `symbol_locks`
- `system_alerts`
- `system_logs`
- `system_notes`
- `tuning_history`
- `tuning_runs`

Important structures supplied by the user:

`asset_states`: symbol primary key, `last_state`, `last_checked_at`, `updated_at`.

`candles`: id, symbol, timeframe, timestamp, open, high, low, close, volume.

`active_trades`: includes direction, entry/exit information, peak profit, RSI/MACD fields, trailing fields, stop loss, exit reason, etc.

`orders`: includes strategy_id, symbol, broker, side, candle_time, entry/exit prices, status, P&L, RSI at entry, cooldown, test flag, scanner source, exit time.

`backtest_orders`: includes run_id, symbol, exchange, side, entry/exit prices/times, RSI values, exit reason, P&L, max favorable excursion and duration.

The design goal is for live trading, backtesting, and tuning to share the **same strategy logic/functions** while maintaining separate state/memory appropriate to each application. Do not duplicate the strategy into three subtly different implementations.

## 11. Earlier Engineering Lesson

A previous PythonAnywhere failure came from:
`ImportError: cannot import name 'run_analysis' from engine.tuning.auto_tuner`

The immediate fix was to comment out the top-level `run_analysis` import in `app.py`, verify with:
`python -m py_compile app.py`
and:
`python -c "import app; print('APP IMPORT OK')"`

It then imported successfully.

Do not reintroduce that broken dependency casually.

## 12. Current Git State / Latest Known Milestone

The user successfully pulled the latest experiment into PythonAnywhere and ran compilation successfully.

Latest known pull at the end of the previous conversation:
`6b8955f..c14b81c`

Latest commit at that point:
`c14b81c` — **Expose 30m and 5m experiment timing in KISS report**.

The commit updates the KISS route so that a `30m` request explicitly reports:
`30m trend → 5m execution`
and exposes the 5m candle count / experiment label.

The user ran:

```bash
cd ~/aimn-trade-final
git pull origin main
python -m py_compile engine/kiss_execution_5m.py kiss_backtest_routes.py
touch /var/www/meirniv_pythonanywhere_com_wsgi.py
```

and the commands completed without a reported error.

## 13. What Has NOT Been Proven Yet

The 30m → 5m experiment has NOT yet been validated by a fresh NVDA comparison.

Do not claim that 5m execution improves profitability until the user runs it and the results are compared.

The next goal is empirical:

**Run NVDA SHORT again using 30m trend decision + 5m execution and compare the losers against the previous NVDA SHORT run.**

Primary questions:
1. Is entry earlier?
2. Is exit earlier?
3. Are obvious late-entry losers reduced/eliminated?
4. Does total P&L improve?
5. Does loser count improve?
6. Does the change accidentally create too many noise trades?

## 14. Do Not Overcomplicate the Next Step

The user proposed another potentially more complicated idea: find the peak of the transition and execute after a percentage retracement/offset from that point. This is a possible later experiment, but **not now**.

For now, change only execution resolution to 5m.

Do not add MACD, volume grids, RSI entry filters, or a collection of traditional indicators simply because they are available.

## 15. Working Style With User

The user prefers:
- simple explanations;
- paste-ready Bash commands when needed;
- as few patches as possible;
- full/simple code rather than fragmented edits when practical;
- one controlled change at a time;
- clear progress reports when requested;
- not having to repeat the project history;
- preserving working components.

The user often says `Continue` to authorize the next implementation step.

## 16. Immediate Next Action

When continuing:

1. Inspect the current `engine/kiss_execution_5m.py` and `kiss_backtest_routes.py` on GitHub.
2. Verify that the 30m→5m path is logically using 30m for trend and 5m for execution and that timestamps are aligned without look-ahead leakage.
3. If code changes are needed, keep them isolated to the KISS experiment.
4. Ask the user to pull/reload only after the implementation is verified.
5. Have the user run NVDA SHORT with the same selection used for the old test.
6. Compare loser trades first.

**Golden rule:** We are testing the strategy, not trying to make a pretty backtest. The losing trades are the laboratory.


---

## 17. V13.17 / KISS Transition Research Archive — Experiments #1–#18
### Research milestone: 2026-09-29

RESEARCH ONLY — NO ORDERS — NO PRODUCTION ENGINE CHANGES — NO AI TRAINING — NO THRESHOLD PROMOTION

This section preserves the major trajectory research performed after the original handoff. Read it before beginning a new transition/trajectory experiment.

### 17.1 Research foundation

The V13.17 case-aware research uses completed candles only, causal timing, no hindsight/future leakage, and 28 unique trajectory cases keyed by symbol, direction, and opposite_time. States are PERSISTENT_FAILURE, DETERIORATING, NEUTRAL, and RECOVERING.

Core principle: a transition is a trajectory, not a single candle, state, RSI value, or return reversal. A warning is not automatically an exit. Thesis failure is not automatically a reversal. Recovery is not defined by one positive return change.

### 17.2 Established 28-case outcome groups

Current post-first-deterioration persistence audit:
- LATER_PF_BY_60: 11
- NO_PF_BY_60: 17

Descriptive persistence differences:
- Negative persistence >=2: PF 11/11 vs NO_PF 4/17
- Negative persistence >=3: PF 8/11 vs NO_PF 2/17
- Positive persistence >=2: PF 2/11 vs NO_PF 9/17
- Positive persistence >=3: PF 0/11 vs NO_PF 3/17

Persistent direction of return change is more informative than a single improvement/worsening observation, but it is not sufficient as an operational rule.

### 17.3 Experiments #1–#5 — persistence, geometry and failed recovery

Early experiments established that mixed post-D return geometry was not itself a reliable separator; persistent negative return-change runs were concentrated in PF cases; first positive reversal was not enough to establish recovery; severity measures overlapped too much to justify a threshold; and third consecutive negative movement was highly concentrated in PF but had a NO_PF counterexample (NVDA #06).

Important counterexample: NVDA #06 reached three consecutive negative return changes but ultimately remained NO_PF.

Conclusion: more deterioration is informative, but even persistent deterioration is not automatically final failure.

### 17.4 Experiments #6–#8 — recovery and resilience

A positive reversal is an event, not a recovery.

Important examples:
- TSLA #19: D D D D D R R — sustained recovery, NO_PF.
- TSLA #18: D D PF PF D PF PF — apparent positive reversal followed by renewed deterioration, PF.
- TSLA #20: D R D PF PF PF PF — even a RECOVERING state can be temporary.
- NVDA #07: D D D D R R D — recovery can suffer a negative challenge and still finish NO_PF.
- AMZN #16: D D D R D D D — recovery can be challenged and later improve again while remaining NO_PF.

The useful sequence became:
FIRST POSITIVE REVERSAL → APPARENT RECOVERY → FIRST NEGATIVE CHALLENGE → STATE RESPONSE → SUBSEQUENT TRAJECTORY.

Recovery is a trajectory property, not a single event.

### 17.5 Experiment #9 — State / Return Divergence

State and return are two partially independent trajectory dimensions. State can improve while return worsens; return can improve while state remains unchanged or worsens; or both can agree.

Examples:
- QQQ #23: state remains DETERIORATING while return improves strongly; final NO_PF.
- NVDA #07: return improves while state remains D, later state becomes R, then suffers a challenge; final NO_PF.
- AAPL #08: return improves after a temporary PF state, but state remains D; canonical corrected outcome is NO_PF.
- GOOGL #27: state and return agree on deterioration; final PF.
- GOOGL #28: eventual state/return convergence toward deterioration; final PF.

Conclusion: neither state nor return is the answer; disagreement and later resolution are more informative.

### 17.6 Experiment #10 — Convergence / Resolution

Divergence was defined as return changing while state remains unchanged. Convergence was the first later state change in the same direction as the return change.

15 cases qualified using the first such event per case:
- Recovery convergence: #06, #07, #16, #19, #22.
- Deterioration convergence: #04, #08, #10, #11, #15, #18, #24, #25, #27, #28.

Recovery convergence: 5/5 ended NO_PF.
Deterioration convergence: 9/10 ended PF; AAPL #08 was the exception.

Conclusion: convergence establishes a direction; it does not prove the final outcome.

### 17.7 Experiment #11 — Post-Resolution Challenge

The next checkpoint after convergence was treated as the first challenge.

Recovery convergence: all 5 observed cases ended NO_PF. Most first challenges continued recovery, but AMZN #16 had a negative challenge and still ended NO_PF.

Deterioration convergence: 9/10 ended PF. Positive challenges after deterioration did not necessarily rescue the trajectory, notably TSLA #18 and GOOGL #25. AAPL #08 again showed that deterioration convergence can later unwind.

Conclusion: the challenge after convergence is more informative than convergence alone, but a single challenge is not decisive.

### 17.8 Experiment #12 — Multi-Challenge Resilience

Two successive challenges were examined where available.

Recovery cases #06, #07, #16, #19, and #22 all ended NO_PF despite different aligned/counter challenge sequences.

Deterioration cases showed both outcomes: most ended PF, but AAPL #08 survived despite counter-direction challenges. Positive challenges did not reliably rescue TSLA #18 or GOOGL #25.

Conclusion: two challenges provide context, but simple aligned/counter sequences still do not classify outcomes universally.

### 17.9 Experiment #13 — Direction Re-Establishment

After a counter-direction challenge, the next return change in the original direction was called direction re-establishment.

Examples:
- recovery re-established: AMZN #16 → NO_PF;
- recovery did not re-establish within observable horizon: NVDA #06 → NO_PF;
- deterioration re-established: MSFT #10, TSLA #18, GOOGL #25 → PF;
- deterioration did not re-establish: AAPL #08 → NO_PF.

Conclusion: re-establishment is more informative than a single challenge, but re-establishment alone is not a final classifier.

### 17.10 Experiment #14 — Re-Establishment Strength & Persistence

The question became whether re-established direction persists for 1, 2, or 3 later checkpoints.

AMZN #16 recovery re-established and persisted for two positive intervals → NO_PF.
Deterioration re-establishment in #10, #18, #24 and #25 was followed by continued deterioration → PF.
AAPL #08 did not re-establish deterioration after its positive challenge → NO_PF.

Conclusion: persistence after re-establishment is more interesting than re-establishment itself, but the sample remained too small for a rule.

### 17.11 Experiment #15 — Second-Challenge Survival

Observable cases were limited:
- NVDA #07: recovery → second negative challenge → NO_PF.
- QQQ #22: recovery → second negative challenge → NO_PF.
- TSLA #18: deterioration re-established → positive second challenge while state remained PF → PF.

Conclusion: a second challenge does not automatically determine the outcome.

### 17.12 Experiment #16 — Second-Challenge Resolution

Only #07, #22, and #18 had observable second challenges, and in each case the challenge occurred at the final +60 checkpoint. Therefore immediate response could be observed, but true post-challenge resolution could not.

### 17.13 Experiment #17 — Resolution Persistence

Strict definition:
Re-establishment → persistence → Challenge #2 → immediate response → NEXT checkpoint → persistence of response.

Result: 0 qualifying cases. The relevant second challenges occurred at +60, which was the end of the available horizon. No information after +60 was inferred.

This is a valid data limitation, not a failed experiment.

### 17.14 Experiment #18 — Extended-Horizon Resolution Test

Question: after directional re-establishment, can we observe at least two later checkpoints to determine whether that direction persists?

Three PF cases qualified under the strict extended-horizon definition:
- #04 NVDA LONG
- #25 GOOGL LONG
- #28 GOOGL LONG

All three showed continued deterioration across the remaining checkpoints and ended PF.

The critical counterexample test then asked:
Can a NO_PF case also show a re-established direction that persists for 2+ later checkpoints?

YES.

Clear NO_PF counterexamples:

#16 AMZN SHORT
D D D R D D D
After the negative challenge, positive return direction re-established at +45 (+0.006752) and +60 (+0.115634). Two consecutive positive return changes. Outcome: NO_PF.

#23 QQQ SHORT
R R D D D D D
After the negative sequence, positive return direction re-established at +45 (+0.174558) and +60 (+0.366719). Two consecutive positive return changes. Outcome: NO_PF.

#26 GOOGL LONG
D D D D D D D
Positive return direction re-established at +45 (+0.221208) and +60 (+0.129960). Two consecutive positive return changes. Outcome: NO_PF.

#13 AMZN SHORT
D R N N N D D
After deterioration returned, positive return direction appeared at +45 (+0.027548) and +60 (+0.114128). Two consecutive positive return changes. Outcome: NO_PF.

### 17.15 Critical #18 conclusion

Extended directional persistence by itself does NOT separate PF from NO_PF.

Do NOT promote any of the following to a production rule:
- 2 positive intervals = recovery;
- 2 negative intervals = failure;
- re-established direction + persistence = exit;
- any fixed return-change threshold;
- any single state transition as a production rule.

The more promising question is now:
After re-establishment and persistence, do STATE and RETURN subsequently converge toward the same trajectory outcome?

### 17.16 Current research hierarchy

TRANSITION RECOGNITION
→ TRAJECTORY STATE
→ RETURN DIRECTION
→ CONVERGENCE
→ CHALLENGE
→ DIRECTIONAL RESPONSE
→ RE-ESTABLISHMENT
→ PERSISTENCE
→ STATE / RETURN CONVERGENCE
→ EVENTUAL TRAJECTORY

This hierarchy is descriptive research, not a production trading rule.

### 17.17 Next experiment — #19

#19 — Re-Establishment + State/Return Convergence Test

Question:
After direction re-establishes and persists, does state eventually move into agreement with the return direction, and does that agreement persist?

Priority counterexamples:
- #16 AMZN — return improves while state remains D → NO_PF.
- #23 QQQ — return improves while state remains D → NO_PF.
- #26 GOOGL — return improves while state remains D → NO_PF.
- #13 AMZN — return improves while state remains D → NO_PF.

Compare these with PF cases where negative return persistence is accompanied by progression toward PERSISTENT_FAILURE.

Do not convert #19 into an operational rule unless the pattern survives direction-controlled, symbol-controlled, and larger-sample validation.

### 17.18 Important canonical correction

A historical persistence audit temporarily classified AAPL #08 as LATER_PF_BY_60 because an older outcome function treated the presence of any intermediate PERSISTENT_FAILURE state as a PF outcome.

The corrected canonical interpretation uses the final +60 state:
D D D D PF D D
Therefore AAPL #08 is a critical NO_PF counterexample and must not contaminate later experiments with the old PF label.

### 17.19 Research philosophy — preserve the counterexamples

The most important lesson from this research is not a new indicator or threshold. It is the discipline of keeping the counterexamples.

A pattern that looks strong on PF cases must immediately be tested against NO_PF cases with the same trajectory structure.

The objective is not to make the backtest look better. The objective is to understand why losers become losers, why apparent failures sometimes recover, why apparent recoveries sometimes fail, when state and return disagree, how that disagreement resolves, and which trajectory information is actually available at the time a decision would have been made.

This research archive is part of the strategic memory of AIMn/AATA and should be read before starting a new transition/trajectory experiment.
