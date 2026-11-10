# AIMn Major Trend — Standalone Baseline Before Supertrend

## Objective
Identify the dominant LONG/SHORT trend from completed 5-minute OHLC candles,
ignoring minor countertrend V movements where possible. Do not optimize trade
profit or produce entry/exit recommendations at this stage.

## Frozen comparison order
1. Standalone price-structure baseline: no Supertrend, RSI, broker, or paid AI API.
2. Record timestamped historical assessments, including UNCERTAIN outcomes.
3. Conduct blind chart reviews: freeze prediction before revealing future candles.
4. Evaluate major-trend correctness against separately defined reference segments,
   false directional changes, and detection delays. Report ambiguous cases.
5. Only after standalone metrics and review protocol are frozen, evaluate
   Supertrend-only and baseline-plus-Supertrend on identical untouched periods.

## Rules
- At each cutoff, use only candles completed at or before that cutoff.
- Keep retrospective reference labels separate from predictions.
- Count changes in classification separately from actual trades.
- Do not claim that fewer changes implies correctness or profitability.
- Do not tune on the final out-of-sample evaluation set.
- Never reinterpret a past prediction after future candles are revealed.
- The present standalone system is a deterministic baseline, not a trained AI.
- Supertrend may help with noise but may also increase reversal delay.
- Entry/exit and P&L studies begin only after major-trend recognition is audited.

## Visual Lab audit
The major-trend panel displays classification-change markers, the selected
horizon, and stability counts. The blind review panel freezes an assessment,
reveals 20 subsequent candles, and exports user feedback as JSON. This is
research-only and does not submit orders.
