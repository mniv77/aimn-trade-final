# AIMn SHORT Tactic Research V1

## Purpose

This note preserves the SHORT-side tactic discovered during the KISS loser review.
It is a tactic experiment, NOT a replacement for the KISS strategy.

## SHORT ENTRY

The SHORT entry must be based on a **fresh, current LONG -> SHORT transition**.

Principle:

- We want price to have been high / in a LONG state.
- We want price to turn down.
- Once the transition to SHORT is established, enter SHORT without the old delayed 2-of-3 confirmation process.
- Do not carry an old SHORT idea forward while the market has already moved.
- Do not enter at the bottom of an already-developed SHORT move.

In plain language:

> HIGH -> MOVE DOWN -> LONG changes to SHORT -> ENTER SHORT.

We are NOT trying to predict the exact top.

## SHORT EXIT

Once SHORT, protect the trade by following the favorable downward move with the trailing mechanism.

Principle:

- SHORT position follows the move down.
- The lowest favorable price becomes the trailing reference.
- When price reverses upward through the trailing-minus level, exit SHORT immediately.
- Do not wait for the old delayed trend-change confirmation.
- RSI remains emergency protection, not the normal exit.

In plain language:

> LOW -> MOVE UP -> TRAILING REVERSAL -> EXIT SHORT.

The goal is to leave while the trade is still profitable or before a reversal becomes a large loss.

## IMPORTANT TACTICAL PRINCIPLE

The signal that started the process must not become more important than what price is doing NOW.

The two dangerous failures observed repeatedly were:

1. **Late SHORT entry:** entering after the major SHORT move has already happened.
2. **Late SHORT exit:** failing to exit when the downward move first reverses upward.

## END-OF-DAY HYPOTHESIS — NOT YET IMPLEMENTED

Separate research hypothesis:

> A very deep SHORT into the end of the day, followed by a late-session reversal, may be followed by a strong LONG move in the next session.

Mirror case:

> A very deep LONG into the end of the day, followed by a late-session reversal, may be followed by a strong SHORT move in the next session.

This must be tested in data before becoming a rule.

## LONG APPLICATION LATER

Do NOT change the LONG tactic yet.

After the SHORT tactic is tested and understood, apply the same core ideas symmetrically to LONG:

- fresh SHORT -> LONG transition for entry
- avoid stale/late LONG entry
- trailing reversal for faster LONG exit
- investigate end-of-day reversal separately

## SHORT Tactic V3 — Current Entry Implementation

The current implementation refines the entry to avoid the V2 mistake of taking every tiny V-SHORT.

Entry now requires:
- the candidate peak candle was in LONG state,
- that candidate peak has the highest high over the preceding 4 candles,
- the next candle does not make a higher high,
- the next candle closes lower and its low is at or below the peak candle's low.

That means the live/backtest decision is:

> HIGH / local swing peak -> FIRST MOVE DOWN -> ENTER SHORT.

The algorithm uses only data available through the entry candle. It does not look into future candles to confirm the pivot.

The SHORT trailing-reversal exit remains unchanged from V1:

> SHORT -> favorable move down -> price reverses upward through trailing-minus -> EXIT.

This V3 is intentionally a tactical correction only. The LONG tactic remains unchanged.

## Test discipline

Change one tactic at a time.
Keep the existing KISS strategy and UI intact.
Compare the revised SHORT results against the prior baseline and inspect the remaining big losers.
