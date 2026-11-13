# AIMn AI Vision — independent research pilot

This is **research-only**. The independent runner never imports EXP53 or any
broker module, never places orders, and never reads future OHLC candles.

## First pilot

1. Review the draft pull request and use a separate PythonAnywhere research
   environment. Do not merge or deploy to the trading app yet.
2. Configure `OPENAI_API_KEY` in the environment, never in GitHub or HTML.
   API calls are billable; verify API access and model availability first.
3. Run offline tests with Python's unittest discovery for
   `tests/test_ai_vision_independent.py`.
4. Start with a **small** pilot, using the runner's
   `--max-assessments 5` option. Default sampling is every 5 candles after
   100 candles of warmup. Review each returned decision and its saved cache.
5. Only after checking causal visibility and next-open fills, increase the
   assessment count and run the full dataset. Do not treat the full run as
   independently validated without inspecting its trade ledger.
6. In AIMn Visual Laboratory, select NVDA, load the chart, and upload the
   runner's output JSON using **Load independent AI predictions (JSON)**.
   The existing EXP53 chart markers remain separate. The page displays the
   independent AI trade ledger and net P&L.

## Two historical perspectives

At decision candle T, the model receives:
- A detailed recent 100-candle OHLC window (configurable).
- Up to 500 historical candles of broader context, with the older portion
  aggregated into consecutive five-candle OHLC blocks. Every block preserves
  its open, high, low, close and time boundaries.
- Its own paper position, but no EXP53 decisions or results.

Both perspectives terminate at T. The research direction is a focus, not a
mandate to trade in that direction. The model must distinguish major structure
from local countertrend bounces. Neither trend classification nor trade
performance is guaranteed.

## Execution and accounting

Entry and exit signals are decided at completed candle closes and filled at
the next available candle's **open**. This is a simulation convention, not a
guarantee of live fill quality. Each closed trade includes gross and net P&L,
with `commission_pct` charged per side. The reported total is a **sum of
per-trade percentage returns**, not compounded account performance.
Open paper positions are excluded from realized P&L.

## Current limitations

- The page currently **imports the saved JSON manually**; the automatic
  backtest-to-page trigger and a shared comparison table are not yet wired.
- The runner's first implementation only opens the selected research
  direction, not both directions at once.
- The model is queried every five candles by default, not every candle.
- No real AI Vision run, model-response audit, or EXP53 comparison has yet
  been completed.
- API charges, model support, market session gaps, data timestamp semantics,
  and next-open execution assumptions must be verified before scaling up.
- Avoid displaying any API key or secrets in browser code or saved research
  files.

## Validation gates

- Offline unit tests pass.
- Model responses have exactly the expected schema.
- No look-ahead in historical packets, fills, or big-picture blocks.
- Independent AI decision logs and paper trades reconcile to source candles.
- Commission treatment matches the EXP53 comparison configuration.
- Both engines are compared over the **same dates and candle coverage**.
- Human inspection confirms major-trend/local-trend distinction on selected
  bearish rallies and genuine reversals.
