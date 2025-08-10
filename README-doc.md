# /README-doc.md

# AIMn Automated Trading System — Beginner Guide

## What is this?
AIMn is a **single-user crypto/asset trading bot** with a **web dashboard**. It:
- **Scans markets**, enters/exits trades using a simple rules/indicator strategy.
- Lets you **tune parameters (TradingView-style)** and **bulk-apply** them to many symbols.
- **Logs trades**, pops a **live chart window** on each exit, auto-saves a **snapshot**, and closes it.
- Runs 24/7 on **PythonAnywhere** with an Always-on worker and a Flask web app.

---

## High-level architecture

+-----------------------+ +---------------------+
| Web UI (Flask) | <------> | MySQL (SQLAlchemy) |
| / dashboard | +---------------------+
| /bulk (copy params) | ^
| /orders (trades log) | | ORM models
| /trade/<id> (chart) | |
| /api/* (JSON) | |
+-----------^-----------+ |
|
| pops windows on exits |
| |
+-----------+-----------+ +---------+-----------+
| Worker (loop) | -------> | Broker (adapter) |
| - fetch_bars() | orders | Alpaca/Gemini/... |
| - indicators (RSI...) |----------| place_order() |
| - should_enter() | +---------------------+
| - evaluate_exit() |
+-----------------------+

markdown
Copy
Edit

**Key idea:** the **worker** makes decisions and writes to DB; the **Web UI** reads from DB and shows controls, charts, and logs.

---

## Main features

1. **Dashboard `/`**
   - Edit **one Strategy Profile** (symbol + timeframe).
   - **Bulk Apply** source profile to many targets.
   - Set **Alpaca keys** (encrypted).

2. **Bulk Apply**
   - Copy all tunables from a **source** to **selected targets**.
   - Optionally **auto-create** profiles from a CSV of symbols.

3. **Orders Log `/orders`**
   - Table of trades with P&L% and reason.
   - Snapshot link (auto-generated after exits, or on-demand via “Generate”).

4. **Live Chart Popper**
   - `/popper` keeps a tiny page open. On each **exit**, it pops `/trade/<id>`.
   - The chart shows **entry/exit price, trailing lines, peak**, etc.
   - After **N bars** (default 4), it **saves**, then **closes** automatically.

5. **Health check**
   - `/api/health` returns **200 OK** and runtime info when DB + app are healthy.

6. **Symbols in loop** *(optional page)*
   - `/loop` lets you pick which profiles the worker scans. If none picked, worker scans all profiles.

---

## Strategy — TV-style tunables

Stored in `StrategyParam` (per `symbol` + `timeframe`):

- **RSI**: `rsi_period`, entry/exit thresholds (split into whole + decimal for TV-like input).
- **MACD**: `macd_fast`, `macd_slow`, `macd_signal`.
- **Volume window**: `vol_window`.
- **Weights**: `weight_rsi`, `weight_macd`, `weight_vol`.
- **Entry threshold**: combined score must be ≥ this value.
- **Risk**:
  - Trailing start: `trailing_start_%`
  - Two trailing drops: `trailing_pct_primary`, `trailing_pct_secondary`
  - Hard stop: `stop_loss_%`
  - RSI-based exit: `rsi_exit_%`
- **Position size**: `position_size_usd`.

**Entry logic (simplified):**
- Compute indicators (RSI/MACD/Vol), combine via weights → **score**.
- If score ≥ `entry_threshold` and no open position → **buy**.

**Exit priority:**
1) **Hard stop (L)** if price ≤ stop loss line  
2) **Trailing (T)** if trailing active and price ≤ trailing line  
3) **RSI exit (R)** if RSI ≥ exit threshold

The exit stores metadata (entry, peak, trailing lines) so the **chart overlays** can be drawn later.

---

## Important pages & endpoints

- `GET /` — Dashboard: editor + bulk apply
- `POST /api/save_params` — Save profile params
- `POST /api/create_profile` — Create a new profile
- `POST /api/bulk_apply` — Copy params to targets (+ optional auto-create)
- `POST /api/save_keys` — Save encrypted Alpaca keys
- `POST /api/toggle` — Toggle bot enabled/disabled
- `GET /orders` — Orders log
- `GET /trade/<id>` — Live Plotly chart tab; auto-saves snapshot after N bars
- `GET /api/trade/<id>/snapshot` — Save snapshot HTML
- `GET /snapshots/<file>` — Serve saved charts
- `GET /api/events/latest_trade` — Worker UI events (entry/exit notifications)
- `GET /api/latest_exit` — Latest SELL trade for popper
- `GET /api/bar_count?trade_id=...` — Bars since trade time
- `GET /api/health` — Health JSON

---

## Database (SQLAlchemy models)

- **StrategyParam**: strategy settings per (symbol, timeframe)
- **ApiCredential**: encrypted keys (venue, key id, secret, paper/live)
- **RuntimeState**: `bot_enabled`, mode (`paper`/`live`), last_heartbeat
- **Position**: current open position (qty, entry price, peak, trailing)
- **Trade**: each buy/sell; `meta` holds chart overlay info and timeframe
- **LogEvent**: structured logs
- **UiEvent**: UI notifications (e.g., trade_entry, trade_exit)
- **LoopTarget** *(optional)*: selected (symbol, timeframe) pairs the worker scans

**DB init:** `scripts/bootstrap_seed.py` creates tables and seeds a default profile if missing.

---

## Broker & market data

- **Market data**: `fetch_bars(symbol, timeframe="1Min", limit=...)`
- **Broker adapters**: `app/broker_*.py` (e.g., Alpaca, Gemini), selected via `app/broker.py`
- **Orders**: routed by `place_order(symbol, side, qty, mode="paper"/"live")`

---

## Deploy on PythonAnywhere (quick)

1) **Virtualenv**
   ```bash
   mkdir -p "$HOME/.venvs"
   python3.11 -m venv "$HOME/.venvs/aimn" || python3.10 -m venv "$HOME/.venvs/aimn"
   source "$HOME/.venvs/aimn/bin/activate"
cd ~/aimn-trade-final   # or your folder name
pip install --upgrade pip wheel
pip install -r Requirements.txt


Install

bash
Copy
Edit
cd ~/aimn-trade-final   # or your folder name
pip install --upgrade pip wheel
pip install -r Requirements.txt
Env vars (Console and Web → Environment variables)

ini
Copy
Edit
PA_MYSQL_USER=<YourPAUser>
PA_MYSQL_DB=<YourPAUser>$default
PA_MYSQL_PW=<YourDBPassword>
PA_MYSQL_HOST=<YourPAUser>.mysql.pythonanywhere-services.com
FLASK_SECRET=<random>
ENCRYPTION_KEY=<run in console: python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())">
Init DB

bash
Copy
Edit
python scripts/bootstrap_seed.py
Web tab

WSGI file: /home/<USER>/<project>/wsgi.py

Virtualenv: /home/<USER>/.venvs/aimn

Reload web app.

Always-on worker

bash
Copy
Edit
source /home/<USER>/.venvs/aimn/bin/activate && python /home/<USER>/<project>/run_worker.py >> /home/<USER>/worker.log 2>&1
Smoke test

Visit /api/health → {"status":"ok",...}

Open / → Dashboard loads.

/orders → table loads (empty is OK).

/popper in a background tab (pops charts on exits).

Common troubleshooting
Push worked locally but not on GitHub: run a clean script to git add -A && git push. Ensure you target the right remote/branch.

PythonAnywhere venv not found: create it at /home/<USER>/.venvs/aimn and point Web → Virtualenv to it.

DB errors: verify the 4 MySQL env vars are set in console and Web tab; rerun bootstrap_seed.py.

No charts: ensure plotly is installed and snapshots folder exists (app/snapshots auto-created).

No trades popping: keep /popper open, and verify /api/latest_exit returns an ID when a trade closes.

Worker idle: ensure Always-on Task is running and /api/health heartbeat updates.

Safety & modes
Default paper mode. Switch to live only when credentials and risk settings are correct.

API keys are encrypted at rest using a Fernet ENCRYPTION_KEY you provide.

Where to change logic
Indicator math: app/indicators.py

Entry decision: app/scanner.py::should_enter

Exit logic: app/position_manager.py::evaluate_exit

Broker routing: app/broker.py (+ adapters)

UI: app/views.py

Worker loop: app/worker.py

csharp
Copy
Edit

**a.** Want me to tailor this doc with your exact broker(s) and supported symbols/timeframes?  
**b.** Should I add a mini diagram image (PNG) and link it from the README?
::contentReference[oaicite:0]{index=0}






Sources
You said:
yes


ChatGPT said:

Thought for 15s
perfect—here’s a polished README.md you can drop into the repo, tailored to your setup (Alpaca + Gemini, 1-minute default). I included a Mermaid diagram that GitHub will render automatically.

Plan
Add/update /README.md with broker/symbol/timeframe specifics.

Include a Mermaid architecture diagram.

Keep PythonAnywhere steps short.

markdown
Copy
Edit
# AIMn Automated Trading System

AIMn is a single-user trading bot with a web dashboard. It scans symbols on a schedule, enters/exits using indicator rules, logs trades, pops a live chart at exits, and auto-saves snapshots.

---

## What’s included

- **Web UI (Flask):**
  - `/` dashboard with TradingView-style **parameter tuning** per (symbol, timeframe)
  - **Bulk Apply** to copy a source profile to many symbols (+ auto-create)
  - `/orders` orders log + snapshot links
  - `/trade/<id>` live chart pop-up with **auto-snapshot after N bars**
  - `/popper` background tab that pops charts on new exits
  - `/api/health` health JSON

- **Worker**:
  - Loops over selected symbols, computes indicators, decides **entry/exit**, places orders, updates DB, and emits UI events.

- **DB (SQLAlchemy + MySQL)**:
  - `StrategyParam`, `ApiCredential`, `RuntimeState`, `Position`, `Trade`, `LogEvent`, `UiEvent`, `LoopTarget`

---

## Architecture

```mermaid
flowchart LR
  UI[Flask Web UI\n(/, /bulk, /orders, /trade/<id>, /popper)] <--> DB[(MySQL via SQLAlchemy)]
  WORKER[Worker loop\n(fetch bars, decide, place orders)] --> DB
  WORKER --> BROKER[Broker Adapter\nAlpaca/Gemini]
  UI -. fetch bars .-> MKT[Market Data\nfetch_bars()]
  WORKER -. fetch bars .-> MKT
Brokers & Market Data
Broker	File	Mode(s)	Notes
Alpaca	app/broker_alpaca.py	paper + live	Set in UI; keys stored encrypted
Gemini	app/broker_gemini.py	spot (as coded)	Optional adapter

Market data: app/market_data.py::fetch_bars(symbol, timeframe="1Min", limit=...)
Default timeframe: 1m (worker param). If you enable more (e.g., 5m, 15m, 1h), create StrategyParam rows for those.

Symbols & Timeframes
Symbol format: BTC/USD, ETH/USD, SOL/USD, …

Supported timeframes now: 1m (default). You can add more if your fetch_bars supports them.

Set one Strategy Profile per (symbol, timeframe) in the dashboard. Use Bulk Apply to stamp the same settings across many symbols.

Strategy (short)
Indicators: RSI, MACD, Volume (windows/weights configurable).

Entry: weighted score ≥ entry_threshold, no open position → buy.

Exit priority:

Hard stop (L)

Trailing (T) (two levels; activates after trailing_start_%)

RSI exit (R)

Position sizing: fixed USD per trade (position_size_usd).

Trade metadata stores entry_price, peak_price, and trailing lines so the chart overlays render later.

Key Pages & APIs
/ — Dashboard (Editor + Bulk Apply + Set Keys)

/orders — Orders log (P&L%, reason, snapshot)

/trade/<id> — Live chart; auto-saves after N bars (default: 4)

/popper — Keep open; pops on exits

/snapshots/<file> — Serve saved HTML charts

/api/health — Status JSON

/api/events/latest_trade — Latest UI event

/api/latest_exit — Latest sell trade for popper

/api/trade/<id>/snapshot — Save snapshot now

/api/bar_count?trade_id=... — Bars since trade time

Deploy on PythonAnywhere (quick)
bash
Copy
Edit
# venv
mkdir -p "$HOME/.venvs"
python3.11 -m venv "$HOME/.venvs/aimn" || python3.10 -m venv "$HOME/.venvs/aimn"
source "$HOME/.venvs/aimn/bin/activate"

# install
cd ~/aimn-trade-final   # use your folder name
pip install --upgrade pip wheel
pip install -r Requirements.txt

# env vars (also set them in Web → Environment variables)
export PA_MYSQL_USER="$USER"
export PA_MYSQL_DB="$USER\$default"
export PA_MYSQL_PW="YOUR_DB_PASSWORD"
export PA_MYSQL_HOST="$USER.mysql.pythonanywhere-services.com"
export FLASK_SECRET="random-string"
export ENCRYPTION_KEY=$(python - <<'PY'
from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())
PY
)

# init DB
python scripts/bootstrap_seed.py
Web tab:

WSGI: /home/$USER/aimn-trade-final/wsgi.py

Virtualenv: /home/$USER/.venvs/aimn

Add the same env vars → Reload

Always-on task:

bash
Copy
Edit
source /home/$USER/.venvs/aimn/bin/activate && python /home/$USER/aimn-trade-final/run_worker.py >> /home/$USER/worker.log 2>&1
Smoke test:

Visit /api/health → {"status":"ok", ...}

Open / (dashboard), /orders (ok empty), /popper (background)

Security
API keys stored encrypted (cryptography.fernet) using your ENCRYPTION_KEY.

Start in paper mode; flip to live only when ready.

Change points
Indicators: app/indicators.py

Entry: app/scanner.py::should_enter

Exit: app/position_manager.py::evaluate_exit

Broker: app/broker.py (+ broker_alpaca.py, broker_gemini.py)

Worker: app/worker.py

UI: app/views.py

pgsql
Copy
Edit

**Next**
- Save this as `/README.md`, run your push script.

**a.** Want me to generate a tiny `/docs/quickstart.md` with only 10 lines (ultra-short install + run)?  
**b.** Should I add `/api/health?deep=1` to verify Alpaca creds and recent bar fetch?
::contentReference[oaicite:0]{index=0}