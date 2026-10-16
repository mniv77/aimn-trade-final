# AIMn Auto Trading — Project Handoff Report

**Version:** 1.0  
**Date:** October 16, 2026  
**Purpose:** Paste this document into a new ChatGPT conversation to continue the AIMn KISS SHORT research without retelling the project history.

## 1. Mission and immediate priorities

AIMn is an automated trading research project focused on detecting transitions between LONG, SHORT, and FLAT market regimes. Current research targets **NVDA SHORT**, 5-minute candles, and attempts to enter near the start of a sustained decline and exit near its end. The strategy has evolved away from traditional multi-indicator entry logic. RSI is retained primarily as a relative-price reference and emergency rescue mechanism.

**Priorities in strict order:**

1. Improve SHORT exits to avoid abandoning profitable downward trends too early.

2. Reduce large losses, especially overnight gap exposures; keep risk controls in place.

3. Investigate missed high-profit SHORT entries (including the July 24–27 area) only after exit research is reliable.

4. Validate findings on real candles, compare identical market events, and only then consider production changes.

**Research principle:** One chart, one comparable candle/entry foundation, experiment-specific exits. Avoid claiming that zero losing trades is achievable.

## 2. Environment and strict workflow

- PythonAnywhere project directory: `~/aimn-trade-final` (historically `/home/MeirNiv/aimn-trade-final`).

- Git branch: `kiss-transition-detector-v5-6-6-final`.

- GitHub repository: [https://github.com/mniv77/aimn-trade-final](https://github.com/mniv77/aimn-trade-final)

- Web Visual Laboratory: [https://meirniv.pythonanywhere.com/aimn\_visual\_lab](https://meirniv.pythonanywhere.com/aimn_visual_lab)

- Backtest page: 🎯 AiMn KISS Backtest, registered via `backtest\_routes.py` / `kiss\_backtest\_routes.py` and using `engine/kiss\_backtest.py`.

- Research symbol: NVDA, SHORT, 5-minute historical candles, June 4–August 28, 2026; 4,680 candles.

**Important user preference:** Give exactly **ONE SHORT Bash command per assistant response**, wait for pasted output before continuing. Avoid fragile long one-line Python and complex quoting; long heredocs have been mangled by the user's copy/paste. Use small, reversible edits with verification. User appreciates complete code when appropriate, but for this live PythonAnywhere workflow prefers one small command at a time.

**Safety:** Do not modify production trading engine, Auto Tuner, or original Exp53/Exp55 engines during visual research. Keep experimental changes in `kiss/visual\_research/` and the lab's own template/static files. Do not use `git reset --hard`, `git clean`, or uncontrolled `git pull`. Preserve backups. Never promise live profitability based on these tests.

## 3. Strategy and exit logic

- Core idea: identify trend transitions; SHORT entry at a credible transition into a downward trend; ideally exit on confirmed reversal/transition out of SHORT.

- RSI emergency exit is retained for sudden adverse moves. Stop-loss must remain in force.

- Exp55 `kiss/visual\_research/exp55\_selective\_v\_engine.py`: `TRAIL\_PCT=0.015`, `STOP\_LOSS\_PCT=0.015`; SHORT exits include `TREND\_CHANGE`, `RSI\_EMERGENCY`, `STOP\_LOSS`, `TRAILING\_REVERSE`. `V\_PROFIT` disabled in Exp55.

- Exp56 `kiss/visual\_research/exp56\_symmetric\_transition\_engine.py`: isolated copy of Exp55 with the trailing-exit branch disabled (`elif False and short\_trail\_hit:`); `TREND\_CHANGE`, RSI emergency, and 1.5% stop-loss remain. This is research-only.

- Overnight gaps mean a nominal 1.5% stop does **not** guarantee realized losses no worse than 1.5%; examine bar timing, gap opens, stop-fill modeling, and trading hours.

## 4. Verified experiment results

All runs used the same 4,680 NVDA candles, SHORT, 5m, V15 entry mode. Reported totals are **sum of individual gross trade percentages**, not compounded account returns, and not necessarily net of realistic commissions/slippage.

| **Experiment** | **Trades** | **Summed gross P&L** | **Win rate** | **Losers** |
| :-: | :-: | :-: | :-: | :-: |
| Exp53 | 45 | **NOT YET CALCULATED** | Not confirmed | Not confirmed |
| Exp55 | 42 | **−6.800%** | 47.62% | 22 |
| Exp56 | 41 | **−1.302%** | 43.90% | 23 |

Exp56 improved summed gross results versus Exp55 by **+5.498 percentage points**, but is still negative and has more losing trades.

Exit reason counts:

- Exp53: 19 `TRAILING\_REVERSE`, 25 `V\_PROFIT`, 1 `TREND\_CHANGE`.

- Exp55: 8 `TRAILING\_REVERSE`, 28 `TREND\_CHANGE`, 5 `STOP\_LOSS`, 1 `RSI\_EMERGENCY`.

- Exp56: 34 `TREND\_CHANGE`, 6 `STOP\_LOSS`, 1 `RSI\_EMERGENCY`, zero trailing exits.

Important example: June 4, 2026 NVDA SHORT at **15:15**, entry ~$220.425. Exp55 exited June 4 at 15:50 near $219.72 (`TRAILING\_REVERSE`); Exp56 held until June 5 at 13:35 and made approximately **+5.613% gross** (`TREND\_CHANGE`). This supports testing smarter exits, but is not proof to remove all trailing protections.

Exp56 worst losses observed:

- `KISS-00032`: Aug 4 13:55 → Aug 5 09:30, **−3.155%**, `TREND\_CHANGE`.

- `KISS-00029`: Jul 30 15:25 → Jul 31 09:30, **−2.761%**, `RSI\_EMERGENCY`.

- `KISS-00034`: Aug 11 15:45 → Aug 12 09:30, **−1.787%**, `STOP\_LOSS`.

Exp56 best gains observed:

- `KISS-00002`: Jun 4 15:15 → Jun 5 13:35, **+5.613%**, `TREND\_CHANGE`.

- `KISS-00037`: Aug 17 10:50 → Aug 18 11:45, **+2.630%**, `TREND\_CHANGE`.

- `KISS-00019`: Jul 13 09:35 → Jul 13 15:00, **+2.233%**, `TREND\_CHANGE`.

## 5. Trade identification and engine parity

Trade IDs such as `KISS-00002` are assigned sequentially **per backtest**, so they can refer to different trades across experiments. Use a stable market-event key **(symbol, direction, entry\_time)** to compare experiments; show each experiment's original trade ID as secondary metadata. Even the datetime key may require verification if input candles or settings differ.

Exp55 has 42 entry times all matching Exp53 entries; Exp53 has three additional entries while Exp55 already held positions:

- Jul 22 13:10, entry ~$213.49.

- Aug 17 11:30, entry ~$227.01.

- Aug 17 12:05, entry ~$227.455.

The 🎯 KISS Backtest uses `engine/kiss\_backtest.py` and has a matching `is\_short\_peak\_reversal()` function in earlier comparison, but **do not assume identical complete backtest outcomes** until candles, settings, exit rules, and position state are checked. The eventual aim is a common trading/entry engine with experimental exit rules rather than duplicated divergent engines.

## 6. Visual Laboratory — files and implementation

Live URL: [https://meirniv.pythonanywhere.com/aimn\_visual\_lab](https://meirniv.pythonanywhere.com/aimn_visual_lab)

Template: `templates/aimn\_visual\_lab.html`  
Flask route: `/aimn\_visual\_lab` in `app.py`

Data:

- `static/aimn\_visual\_lab/aimn\_nvda\_candles.json` — 4,680 candles.

- `static/aimn\_visual\_lab/aimn\_nvda\_exp53.json` — 45 trades.

- `static/aimn\_visual\_lab/aimn\_nvda\_exp55\_visual.json` — 42 trades.

- `static/aimn\_visual\_lab/aimn\_nvda\_exp56\_visual.json` — 41 trades.

JavaScript constructs fetch paths with `base='/static/aimn\_visual\_lab/aimn\_nvda\_'` and suffixes `candles.json`, `exp53.json`, `exp55\_visual.json`, `exp56\_visual.json`. Uses TradingView Lightweight Charts 4.1.0.

Colors: Exp53 yellow `\#f5b942`, Exp55 blue `\#58a6ff`, Exp56 teal `\#20bfa9`.

Recent edits made to template:

1. Added Exp56 JSON to fetch list and `trades56=data\[3\]`.

2. Added Exp56 selector and changed title to `AIMn Visual Laboratory — Exp53 vs Exp55 vs Exp56`.

3. Added Exp56 to trade list and distinct marker colors.

4. Changed trade dropdown loop to iterate unique entry datetimes using `const groups=\[...new Set(rows.map(t=\>t.entry\_time))\]`.

5. Added `window.labGroups=groups`, changed `selectTrade()` to find a trade matching selected datetime.

6. Replaced details panel text to join all matching experiment results by entry datetime, including trade ID, exit timestamp/price, P&L, reason.

**Important remaining defects / verification:**

- Screenshot on October 16 showed the live chart title includes Exp56 and teal markers are visible, but the trade dropdown still displayed the **old format** `2026-06-04 13:00:00 | Exp53 \#KISS-00001 -0.38%`, and the status text only showed Exp53 and Exp55 counts. This suggests the live page may have been serving an older template, or the new selector label code was not fully applied. **Do not claim the grouped selector is working in browser yet.**

- The current code for dropdown may still use `o.textContent=t.entry\_time+' | '+t.exp+' \#'+t.trade\_id+' '+Number(t.pnl\_pct).toFixed(2)+'%'`, even after changing the loop to group timestamps. It needs an explicit grouped label.

- The chart's zoom uses `t.exit\_time` for the first matching experiment and can hide later Exp56 exits. Change to latest exit among all experiments for the selected datetime.

- `el('status')` currently lists Exp53 and Exp55 counts but not Exp56.

- `window.labTrades` contains experiment-specific rows; `window.labGroups` contains grouped timestamps; ensure selector indexes align.

- Current `selectTrade()` details line around line 91 is:  
`el("details").textContent="NVDA SHORT | Entry: "+dt+"\\n\\n"+window.labTrades.filter(x=\>x.entry\_time===dt).map(x=\>x.exp+" | "+x.trade\_id+"\\nExit: "+x.exit\_time+" @ "+x.exit\_price+"\\nP&L: "+Number(x.pnl\_pct).toFixed(3)+"%\\nReason: "+(x.exit\_reason||"Not recorded")).join("\\n\\n");`

- Need browser-side validation of JavaScript and details, not just HTTP 200.

- PythonAnywhere does not have `node` installed; `node --check` failed with FileNotFoundError, **not** a proven JS syntax error.

- The webpage returned HTTP 200, but this alone doesn't establish functional JS.

Template backups created:

- `templates/aimn\_visual\_lab\_before\_exp56.html`

- `templates/aimn\_visual\_lab.html.bak328`

- `templates/aimn\_visual\_lab.html.bak339`

- `templates/aimn\_visual\_lab.html.bak341`

- `templates/aimn\_visual\_lab.html.bak346`

## 7. Last user request and exact next work

**Most recent user request:** "Can we summarize for each Exp the total %PnL" above the chart, then requested this handoff report to avoid retelling the project in a new conversation.

**Next priority:** Add a compact experiment summary above the chart with Exp53, Exp55, Exp56 total summed gross P&L, trade counts, and preferably win rates/large-loss counts. **Calculate Exp53 from its actual JSON; do not invent it.** Decide whether summary is computed from loaded trade JSON (recommended for consistency with chart) and clearly label summed gross trade % vs compounded portfolio returns.

Before more edits, inspect the current template and its JS because the screenshot showed older selector labels and missing Exp56 status despite the newer source edits. Confirm PythonAnywhere app reload / browser cache if needed.

Then fix grouped datetime selector, synchronized exit details, zoom through latest matching exit, and validate in browser. Only then resume exit-risk research: distinguish overnight gaps from in-session reversals; test risk controls without hindsight, with fees/slippage and out-of-sample validation. Then investigate missed profitable entries.

## 8. First message to paste into a new chat

"We are continuing AIMn Auto Trading on PythonAnywhere. Please read this handoff report and follow it as our project context. Do NOT restart the strategy discussion. We are at the Visual Laboratory comparison of Exp53/55/56. My latest request is to show total % P&L for each experiment above the chart, using actual experiment data. We must verify the grouped entry datetime selector and chart behavior. Our top research priorities are correcting premature SHORT exits, reducing large losses, then investigating missed profitable entries. Give ONE SHORT Bash command at a time, wait for my pasted output, and never modify production engines during this research."

## 9. Known limitations of this handoff

This report reflects the prior conversation and the user's terminal outputs/screenshot; it is not a fresh inspection of the current Git repository or PythonAnywhere server. Some template edits may not yet be live. No Exp53 aggregate return has been computed or verified. Research results are historical, not proof of future or live performance.

