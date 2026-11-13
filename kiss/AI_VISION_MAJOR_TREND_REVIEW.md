# AIMn AI Vision — Major Trend Blind Review Protocol

## Research question
Can OHLC-only AI Vision identify the dominant NVDA 5-minute trend and distinguish
local countertrend recoveries from emerging major reversals, earlier than
Supertrend without excessive false reversals?

## Separation of evidence
1. **At-time packet**: historical OHLC visible through the selected cutoff.
   No future candles, Supertrend, RSI, EXP53, or later outcomes.
2. **AI judgment**: major_trend, local_trend, local_transition_type,
   major_trend_confidence, major_trend_evidence, major_reversal_evidence.
   Save the raw response before revealing future data.
3. **Blind human judgment (optional)**: reviewer sees the identical cutoff
   chart and records major/local trend and confidence before future reveal.
4. **Hindsight adjudication**: reviewer reveals subsequent candles and records
   what price did. Hindsight is not assumed to establish the uniquely correct
   at-time decision.
5. **Supertrend comparator**: calculate ST independently on the same
   historical candles; do not expose it to the OHLC-only assessor.

## Audit table fields
case_id, symbol, timeframe, cutoff_unix, cutoff_price,
ai_major_trend, ai_local_trend, ai_local_transition_type,
ai_major_trend_confidence, ai_major_trend_evidence,
ai_major_reversal_evidence, human_blind_major_trend,
human_blind_local_trend, human_blind_confidence,
hindsight_major_trend_label, hindsight_label_basis,
hindsight_label_ambiguity, first_confirmed_transition_unix,
supertrend_flip_unix, ai_first_transition_unix,
ai_lead_vs_st_candles, false_major_reversal_alarm,
review_notes.

## Scoring rules
- **Major-trend agreement**: compare AI and blinded reference labels only
  where a reference label is defensible; report uncertain cases separately.
- **Noise error**: AI labels POSSIBLE_MAJOR_REVERSAL when a reviewer later
  classifies the move as only a local recovery, using a written rule.
- **Transition timing**: compare the first AI major-trend change to the
  first Supertrend change for the same event, in 5-minute candles.
  A positive lead means AI changed earlier; report false positives too.
- **No lookahead**: compute all at-time signals only from candles through
  their respective cutoff. Hindsight is for evaluation, never model input.
- **Sampling**: five widely spaced cutoffs are a diagnostic smoke test, not
  a statistical accuracy study. Follow with contiguous time-series replay
  and additional dates/symbols to estimate accuracy and lead time.
- **No trading claim**: recognition metrics are not profitability metrics.
  No orders, entries, exits, or broker calls in this phase.

## Immediate checkpoint
The pilot runner and offline tests exist on the independent research branch.
Actual model judgments and ST lead/lag numbers have **not** yet been produced.
Do not report improvement over ST until paired historical results exist.
