# AiMn Trade — Strategy & Project Handoff Report

## Purpose

The most important part of this project is the **trading strategy**. The guiding principle is **KISS — Keep It Simple**.

We want substantially fewer losing trades, especially losses caused by entering too late or exiting too late.

**Do not change the broker / symbol / direction / candle selection unless testing proves it is broken.**

## KISS Strategy

The market has three states:

- LONG = generally moving up

- SHORT = generally moving down

- FLAT = sideways

The strategy is based on **trend transitions**, not a collection of indicators.

### Entries

- SHORT -\> LONG = enter LONG

- LONG -\> SHORT = enter SHORT

- FLAT -\> LONG = enter LONG

- FLAT -\> SHORT = enter SHORT

### Wait

- LONG -\> FLAT = wait

- SHORT -\> FLAT = wait

The chart shape is not the strategy. V, W, M, U and other shapes are only visual descriptions.

- V-Long = falling -\> rising

- V-Short = rising -\> falling

**The transition is what matters.**

## Why the losing-trade charts matter

We deliberately concentrate on losers, not winners.

The charts have shown two major problems:

1. **Entry too late** — the system recognizes the correct direction only after much of the move has already happened.

2. **Exit too late** — the system recognizes the reversal after the price has already moved substantially against the position.

NVDA is an important stress test because its chart can contain rapid V-like reversals and large jumps.

The objective is to get onto the correct side of the transition earlier and get off when the real transition occurs.

## Timeframe Experiment

The current experiment is:

**30m candles = major/global trend decision**

**5m candles = execution timing**

One 30m candle contains six 5m candles. The idea is that the 5m data can locate the actual execution point much closer to the transition instead of waiting for the full 30m candle.

This is an experiment. **Only the real backtest can prove whether it improves the results.**

Do not assume it is better before testing it.

## Noise / Confirmation

Small local reversals can occur while a trade is running.

Example:

LONG -\> brief SHORT -\> LONG

That can be noise.

We therefore do not want to exit because of one noisy candle. A real transition should survive a safety/confirmation zone of roughly **2–4 candles**.

The new implementation uses a 2-of-3 style confirmation for the 5m execution experiment.

A minor reversal that disappears inside the confirmation window should not throw us out. A stronger reversal that survives the safety zone can trigger the exit.

## RSI

RSI is **emergency protection only**.

It is not the normal entry strategy.

Its purpose is to protect against an unexpected violent move, such as bad news while LONG or exceptionally good news while SHORT, where waiting for the normal transition could take too long.

The hierarchy is:

1. Trend transition = normal decision

2. Trailing / meaningful transition = normal exit protection

3. RSI = emergency exit

4. Stop loss = final protection

## Trailing Exit

The KISS design uses approximately a **1.5% trailing distance** from the favorable peak/trough.

For LONG, remember the highest favorable price.

For SHORT, remember the lowest favorable price.

A trailing reversal should not immediately exit on one noisy candle; it should be confirmed.

## Remembering Transitions

An important implementation idea is to start from the newest candle and move backward to find the most recent meaningful transition rather than repeatedly scanning the whole history from the beginning.

The system remembers:

**WHAT = trend/state**

**WHEN = timestamp**

Each application should have its own memory/database area:

- live trading

- backtest

- tuner

They should not overwrite each other's memory.

## Backtest / Loser Inspection

A separate KISS backtest was created so the strategy can be tested without unnecessarily disturbing the existing tuner.

Important files include:

- `engine/kiss\_backtest.py`

- `kiss\_backtest\_routes.py`

- `templates/kiss\_backtest.html`

- `engine/kiss\_execution\_5m.py`

The KISS backtest displays total trades, P&L, win rate, losers, transitions, and detailed losing trades.

Each loser can be selected by **Trade ID** so we can quickly inspect:

- entry time

- entry price

- exit time

- exit price

- transition

- exit reason

- maximum favorable movement

- maximum adverse movement

- RSI at entry/exit

The chart is an investigation tool, not a winner showcase.

## Current 5m Experiment

A new independent file was added:

`engine/kiss\_execution\_5m.py`

It implements:

**30m trend decision + 5m execution**

It intentionally does not create a new indicator-heavy strategy.

It includes:

- 30m market-state detection

- 30m transitions

- 5m execution confirmation

- V-shape description

- trailing protection

- RSI emergency exit

- Trade IDs

- entry/exit data

- favorable/adverse movement measurements

Latest related Git state reported in the previous session:

`c14b81c`

## Testing Plan

Do not change ten things at once.

First compare the existing KISS backtest with:

**30m decision + 5m execution**

Keep the same broker, symbol, direction, and historical data.

NVDA is a particularly useful stress test because the previous NVDA SHORT result showed entry and exit were both much too late.

Judge the experiment by more than total profit:

1. Number of losers

2. Average losing trade

3. Maximum adverse movement

4. Entry timing

5. Exit timing

6. Win rate

7. Total P&L

8. Whether entry occurs after the move is already exhausted

9. Whether exit occurs after the reversal is already large

10. Whether 5m execution actually reduces those problems

## Do Not Reinvent the Strategy

The goal is one consistent strategy used by:

- backtesting

- tuning

- eventually live trading

Experiments should initially remain isolated so they can be compared cleanly.

Do not:

- change broker selection

- change symbol selection

- change direction selection

- add a pile of indicators

- rewrite working parts unnecessarily

- assume 5m is better before testing

- mix the experiment into the existing tuner without comparison

Do:

- inspect the current repository

- understand the KISS backtest

- understand the routes and templates

- test the 30m/5m experiment

- concentrate on losing trades

- compare entry and exit timing

- make one change at a time

- use Trade IDs for individual losers

- keep the strategy simple and explainable

## The Core Philosophy

Most trades do not make money.

We want to be on the other side of that statistic.

A strategy should be simple enough that an ordinary person looking at a losing chart can understand why the trade was bad.

**KISS — Keep It Simple.**

### One-sentence version

**30m tells us WHAT the market is doing; 5m helps determine WHEN to act; the KISS trend transition remains the strategy.**

