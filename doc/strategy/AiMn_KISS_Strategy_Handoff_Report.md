# AiMn Trade — Project Handoff Report

## KISS Strategy / Backtest / 5-Minute Execution Experiment

**Date: August 30, 2026**

### 1. What we are building

This is the **AiMn trading system**. The most important part of the system is the **trading strategy**.

The guiding philosophy is:

> **KISS — Keep It Simple, Stupid.**

We deliberately moved away from the idea that a trading system needs dozens of indicators and complicated formulas.

The strategy is fundamentally about recognizing only three market states:

- **LONG** — market is trending upward 

- **SHORT** — market is trending downward 

- **FLAT** — sideways market 

The important thing is **the transition between trends**, not the particular shape of the chart.

Examples:

- falling → rising = **V-Long** 

- rising → falling = **V-Short** 

- But the chart can also make W, M, U, inverted U, etc. 

**The shape is not the strategy. The transition is the strategy.**


# 2. Core KISS trading rules

### Entries

We enter when the market changes into a directional trend:

- SHORT → LONG = LONG entry 

- LONG → SHORT = SHORT entry 

- FLAT → LONG = LONG entry 

- FLAT → SHORT = SHORT entry 

We **do not enter** simply because:

- LONG → FLAT 

- SHORT → FLAT 

Those are situations where we wait for the next meaningful directional transition.

### Exits

While in a trade, we follow the trend.

A meaningful reversal should eventually cause an exit.

A trailing mechanism is used to protect the trade, but **minor noise must not immediately throw us out**.

The original strategy specifies confirmation of approximately **2–4 candles** so that a temporary local reversal does not automatically become an exit.

### Protection

RSI is **not the strategy**.

RSI is an emergency safety mechanism for unexpected events.

For example:

- unexpected very bad news while LONG 

- unexpected extremely good news while SHORT 

In those cases, waiting for the normal trend-transition detection may be too slow.

Therefore:

> **Trend transition = normal decision mechanism.**  
**RSI = emergency protection.**  
**Stop loss = final protection.**


# 3. Very important strategic principle

The goal is **not to predict everything**.

The goal is to get on the correct side of the transition as early as reasonably possible.

The problem we discovered is that the system can be **too cautious**.

A trade can be theoretically correct but still lose money because:

> **We entered too late, after much of the move had already happened.**

Then the system may also:

> **exit too late, after the trend has already reversed significantly.**

That is currently one of our biggest concerns.


# 4. What we discovered from the loser charts

We deliberately decided to concentrate on **losing trades**, rather than spending our time studying winners.

The reason is simple:

> We already know the system can make money.  
The losers tell us where the strategy is wasting money.

The new KISS backtest produces a **Losers** section where individual Trade IDs can be selected and inspected.

The chart shows:

- candles 

- entry 

- exit 

- Trade ID 

- entry/exit prices 

- transition 

- exit reason 

- RSI 

- maximum favorable movement 

- maximum adverse movement 

This makes it possible to visually ask:

> "Why did we enter here?"

and

> "Why did we wait until here to exit?"

This is much more useful than simply looking at a total P&L number.


# 5. Important discovery from NVDA

NVDA became an especially important test because its chart contains many rapid reversals / V-shaped transitions and sudden jumps.

We observed:

> **The KISS system entered too late and exited too late.**

This was particularly obvious in NVDA.

The concern was not that the basic direction-selection system was necessarily wrong.

The concern was **execution timing**.

The transition can happen very quickly, so a 30-minute candle can cause the system to recognize the move much later than the actual turning point.


# 6. The timeframe idea

We therefore proposed a very important experiment:

### 30-minute candles

Use **30m for the major/global trend decision**.

This answers:

> "What is the market's major direction?"

### 5-minute candles

Use **5m for execution**.

This answers:

> "When exactly should I enter or exit?"

The idea is:

> **30m decides WHAT.  
5m decides WHEN.**

This should potentially reduce the late-entry and late-exit problem.

But we do **not assume it works**.

The only real test will tell us.


# 7. Current experiment

We deliberately decided:

> **Do not make many changes at once.**

The first experiment is simply:

**30m trend decision + 5m execution.**

We do not want to simultaneously introduce a large collection of indicators, filters, parameters, or optimization tricks.

That would make it impossible to know what actually improved the results.


# 8. Important existing-system constraint

The following already works and should **NOT be changed**:

- broker selection 

- symbol selection 

- direction selection 

- candle/data selection 

The explicit rule is:

> **If it isn't broken, don't touch it.**

The new strategy/execution experiment should therefore be isolated from the existing selection machinery as much as possible.


# 9. Independent implementation

We decided not to modify the existing complicated machinery unnecessarily.

Instead, the new experiment should be **clean and independent**.

A new engine was created:

`engine/kiss\_execution\_5m.py`

It implements the experimental:

> **30m major trend / 5m execution**

approach.

The intent is to compare the result against the previous KISS implementation without contaminating the existing system.


# 10. Current Git status

The latest Git pull was:

```
`Already up to date.`
```

The relevant recent commit added:

```
`engine/kiss\_execution\_5m.py`

`kiss\_backtest\_routes.py`
```

The latest successful commands were:

```
`cd ~/aimn-trade-final`

`git pull origin main`

`python -m py\_compile engine/kiss\_execution\_5m.py kiss\_backtest\_routes.py`

`touch /var/www/meirniv\_pythonanywhere\_com\_wsgi.py`
```

There were no Python compilation errors.


# 11. Existing KISS backtest

The KISS backtest page is working.

Example:

```
`/kiss\_backtest?broker\_id=2&symbol=NVDA&direction=LONG&timeframe=30m`
```

It displays:

- total trades 

- total P&L 

- win rate 

- losers 

- detected transitions 

- list of losing trades 

- Trade IDs 

- individual charts 

- entry/exit markers 

This is exactly the kind of report we wanted because it allows the human to inspect the actual bad trades.


# 12. What we saw in the charts

One NVDA example showed:

```
`KISS-00008`

`LONG`

`Entry: 2026-07-06 15:00 @ 196.514`

`Exit: 2026-07-07 14:30 @ 192.57`

`P&L: -2.007%`

`Exit: TRAILING\_TREND\_CHANGE`
```

The visual conclusion was:

> **Entry was too late. Exit was too late.**

Another important observation was that the system can be **too cautious** around very fast transitions.


# 13. The "ScSt" question

There was a chart displaying something called **ScSt**.

We concluded that this was not important to the KISS strategy and does not need to become part of the strategy.

The strategy should remain simple.


# 14. Strategy documentation

The strategy has already been documented as the central KISS strategy.

The important document is:

```
`doc/strategy/AiMn-KISS-Strategy-V3-full.md`
```

It explicitly describes:

- LONG / SHORT / FLAT 

- transitions 

- V-Long / V-Short 

- transition confirmation 

- separate memory for live/backtest/tuner 

- trailing protection 

- emergency RSI 

- stop loss 

- shared strategy engine concept 

The guiding architectural idea is:

> **ONE STRATEGY, ONE ENGINE, DIFFERENT MEMORIES**

Live trading, backtesting and tuning should each maintain their own state/history rather than interfering with each other.


# 15. Why separate memory matters

This was discussed carefully because it is easy for an AI or programmer to misunderstand.

Think of each application as having its own notebook:

- Live trading has its notebook. 

- Backtest has its notebook. 

- Tuner has its notebook. 

They all use the **same strategy**, but each keeps its own memory of:

- what trend was previously detected 

- when it happened 

- current trade state 

- peak/trough information 

- etc. 

This prevents one application from confusing its state with another application.


# 16. Important "go backward" idea

Another important part of the strategy is how we find the most recent transition.

Instead of repeatedly scanning the entire historical dataset forward from the beginning, the system should:

> **Start at the newest candle and move backward to find the most recent transition.**

Once that transition is known, save it in memory/database.

Next time, start from the newest data and only process what is new.

The purpose is both:

- efficiency 

- avoiding repeatedly rediscovering the same history 

This concept should be explained simply in documentation because even an AI/programmer can misunderstand it.


# 17. Current main problem

The current question is **not**:

> "Can we make a complicated indicator system?"

It is:

> **Can we execute the correct KISS trend-transition strategy earlier and exit at the correct transition without being fooled by minor noise?**

Specifically:

### Entry problem

We may recognize the correct transition but enter after the price has already moved too far.

### Exit problem

We may recognize the reversal but exit after too much of the move has already been lost.

### Noise problem

A temporary local reversal should not immediately close a trade.

We need to distinguish:

**minor noise**

from

**a genuine major trend reversal.**


# 18. Current testing philosophy

We are experimenting scientifically.

Do **not** change ten things at once.

The process should be:

1. Establish the KISS baseline. 

2. Test 30m decision + 5m execution. 

3. Compare the results. 

4. Look primarily at losers. 

5. Inspect individual charts. 

6. Identify the reason for each loss. 

7. Make one meaningful strategy change. 

8. Test again. 

9. Compare. 

The human visual inspection of the losing charts is an important source of feedback for future AI training.


# 19. What we ultimately want

The goal is not merely a higher win rate.

We want:

- fewer unnecessary losing trades 

- earlier correct entries 

- earlier correct exits 

- protection against sudden unexpected reversals 

- resistance to minor noise 

- consistent behavior across symbols 

- a simple strategy that can be understood and audited 

- the **same strategy** used by backtest, tuner and eventually live trading 

Most importantly:

> **We want to be on the other side of the trades that currently lose money.**

The system already demonstrated that it can make money even while carrying substantial losers, so reducing the bad trades could potentially make a meaningful difference.


# 20. Current immediate task

The immediate task is:

### Test the new 30m / 5m execution experiment.

Use NVDA as an important test because:

- it has rapid transitions 

- it contains many V-shaped reversals 

- it has sudden jumps 

- the old implementation was clearly too late 

Then compare the new results with the old KISS results.

**Do not modify broker/symbol/direction selection.**

**Do not add a pile of indicators.**

**Do not optimize blindly.**

First determine whether the simple 30m → 5m change actually solves the timing problem.


## The guiding sentence for the new chat

> **We already know what strategy we want. Now we are trying to make the execution happen at the right time without making KISS complicated.**

### Current state

The latest code has been pulled successfully and compiled successfully.

```
`engine/kiss\_execution\_5m.py`
```

is now in the project.

The next job is to **run it, inspect the fresh results, especially NVDA losers, and compare them against the previous KISS 30m implementation.**

**Do not reinvent the strategy. Improve the execution of the strategy we already agreed on.**


You can paste **this entire report** into the new chat. It should give the new chat enough context to pick up the work without you having to tell the whole story again.




# \#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#



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




\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#\#

===============================================================================================================================================================================================================================


AiMn TRADE — PROJECT HANDOFF

We are developing the AiMn Trade system.

IMPORTANT: Do NOT reinvent the existing broker / symbol / direction / candle selection. That part works. If it isn't broken, DO NOT TOUCH IT.

MAIN STRATEGY — KISS Keep It Simple.

We moved away from the indicator-heavy strategy.

Market has only 3 important states: LONG SHORT FLAT

The important thing is the TRANSITION between states.

ENTER: FLAT → LONG FLAT → SHORT LONG → SHORT SHORT → LONG

WAIT / DO NOT ENTER: LONG → FLAT SHORT → FLAT

V shapes, inverted V, W, M, U, etc. are useful descriptions but are NOT the strategy. The transition is the strategy.

During a trade: Small reversals are NOISE. Do not immediately exit because of one candle or a small local reversal.

A real transition should be confirmed over roughly 2–4 candles. Trailing take profit is used to detect/protect against a meaningful reversal.

RSI is NOT the strategy. RSI is emergency protection only — especially for a sudden event/news shock where waiting for normal trend detection would be too slow.

Stop loss is the final protection.

MAIN PROBLEM WE ARE SOLVING: Our entries and exits were often TOO LATE.

This was especially obvious on NVDA, which has many rapid V-shaped transitions and sudden jumps. We can enter near the end of a move and then exit near the bottom — exactly backwards from what we want.

IMPORTANT NEW EXPERIMENT: Use two timeframes:

30 MINUTES = major/global trend decision 5 MINUTES = execution timing

The idea: 30m tells us WHAT the market is doing. 5m tells us WHEN to actually enter or exit.

We are deliberately making only one major change at a time so we can compare results.

CURRENT EXPERIMENT FILE: engine/kiss\_execution\_5m.py

It is intentionally independent from the old system.

Recent Git commit: c14b81c

The current experiment uses:

- 30m trend

- 5m execution

- 2-of-3 confirmation

- trailing protection

- RSI emergency exit

- Trade IDs

- loser-focused charts

We have a KISS backtest page: /kiss\_backtest

The chart displays losing trades and gives each trade an ID so we can inspect individual bad trades.

The user does NOT care about looking at winners right now. The losers teach us where the strategy is wrong.

OBSERVATIONS:

1. Some previous entries were clearly too late.

2. Some exits were clearly too late.

3. Despite many losers, the strategy can still make money.

4. Therefore the goal is NOT simply "more trades."

5. The goal is to substantially reduce bad/late trades while preserving the good transition logic.

6. NVDA is an especially useful test because its transitions can happen very quickly.

7. The user believes the core KISS strategy is correct and wants execution timing improved.

CURRENT THINKING: The 30m timeframe should determine the major transition. The 5m timeframe should allow us to act much closer to the actual transition instead of waiting 30 minutes for the next large candle.

DO NOT:

- add a pile of indicators

- modify broker selection

- modify symbol selection

- modify direction selection

- redesign the whole application

- mix this experiment into the old tuner unnecessarily

- optimize blindly for one symbol

TESTING PHILOSOPHY: One change at a time. Run real backtests. Look primarily at losers. Compare old KISS versus new KISS 30m/5m. Use the Trade ID and chart to understand WHY each loser happened.

NEXT LIKELY IMPROVEMENT: The current 5m experiment waits for confirmation before execution. Because our main problem is "too late," investigate whether execution should happen on the SECOND confirming 5m candle rather than waiting for the full three-candle window.

This keeps the safety idea (2-candle confirmation) but reduces execution delay.

Do NOT change anything else until that comparison is tested.

The user prefers complete files/code or very simple Bash commands rather than patches.

