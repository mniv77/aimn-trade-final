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
