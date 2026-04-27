import sqlite3
import time

DB_PATH = "popup.sqlite3"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# --- 1. BROKER STATE ---
c.execute('DROP TABLE IF EXISTS broker_state')
c.execute('''CREATE TABLE broker_state (
    id INTEGER PRIMARY KEY,
    balance REAL,
    equity REAL,
    open_pnl REAL,
    margin_used REAL,
    updated_at INTEGER
)''')
c.execute("INSERT INTO broker_state VALUES (1, 10000.00, 10000.00, 0.00, 1.5, ?)", (int(time.time()),))

# --- 2. MARKET STATE ---
c.execute('DROP TABLE IF EXISTS market_state')
c.execute('''CREATE TABLE market_state (
    symbol TEXT PRIMARY KEY,
    price REAL,
    change_24h REAL,
    high_24h REAL,
    low_24h REAL,
    volatility TEXT,
    updated_at INTEGER
)''')
c.execute("INSERT INTO market_state VALUES ('SOL/USD', 145.20, 5.40, 150.00, 140.00, 'Low', ?)", (int(time.time()),))

# --- 3. STRATEGY PERF ---
c.execute('DROP TABLE IF EXISTS strategy_perf')
c.execute('''CREATE TABLE strategy_perf (
    id INTEGER PRIMARY KEY,
    win_rate REAL,
    profit_factor REAL,
    long_exposure REAL,
    short_exposure REAL,
    total_pnl_money REAL,
    total_pnl_pct REAL,
    updated_at INTEGER
)''')
c.execute("INSERT INTO strategy_perf VALUES (1, 65.0, 1.5, 5000.00, 0.00, 150.00, 1.5, ?)", (int(time.time()),))

# --- 4. AI METRICS ---
c.execute('DROP TABLE IF EXISTS ai_metrics')
c.execute('''CREATE TABLE ai_metrics (
    id INTEGER PRIMARY KEY,
    confidence REAL,
    signal_strength REAL,
    trend_score REAL,
    sentiment REAL,
    updated_at INTEGER
)''')
c.execute("INSERT INTO ai_metrics VALUES (1, 88.0, 4.5, 10.0, 75.0, ?)", (int(time.time()),))

conn.commit()
conn.close()
print("✅ MASTER DATABASE BUILT SUCCESSFULLY.")
