# /home/MeirNiv/aimn-trade-final/engine/tuning/run_tuning_all.py
# AiMN V3.1 - Daily Auto Tuner
# Runs every day via PythonAnywhere scheduled task

import sys
sys.path.insert(0, '/home/MeirNiv/aimn-trade-final')

from engine.tuning.auto_tuner import tune_strategy
from db import get_db_connection
from datetime import datetime

# Timeframes by broker type
CRYPTO_TFS = [
    {'tf': '1hr', 'candle_time': '1hr', 'bar_minutes': 60,  'bars': 2016},
    {'tf': '30m', 'candle_time': '30m', 'bar_minutes': 30,  'bars': 2016},
    {'tf': '5m',  'candle_time': '5m',  'bar_minutes': 5,   'bars': 2016},
]
STOCK_TFS = [
    {'tf': '5m',  'candle_time': '5m',  'bar_minutes': 5,   'bars': 2016},
]
FOREX_TFS = [
    {'tf': '1hr', 'candle_time': '1hr', 'bar_minutes': 60,  'bars': 1000},
    {'tf': '30m', 'candle_time': '30m', 'bar_minutes': 30,  'bars': 1000},
]
FUTURES_TFS = [
    {'tf': '1hr', 'candle_time': '1hr', 'bar_minutes': 60,  'bars': 1000},
    {'tf': '30m', 'candle_time': '30m', 'bar_minutes': 30,  'bars': 1000},
]

BROKER_TFS = {
    'GEMINI'    : CRYPTO_TFS,
    'COINBASE'  : CRYPTO_TFS,
    'ALPACA'    : STOCK_TFS,
    'ALPACA-ETF': STOCK_TFS,
    'WEBULL'    : STOCK_TFS,
    'FOREX'     : FOREX_TFS,
    'FUTURES'   : FUTURES_TFS,
}

DIRECTIONS = ['LONG', 'SHORT']

DEFAULT_STRATEGY = {
    'rsi_len': 100, 'rsi_entry': 30.0, 'stop_loss': 1.0,
    'trailing_start': 2.0, 'trailing_drop': 0.5, 'rsi_exit': 70.0,
    'init_profit': 1.0, 'decay_start': 0.5, 'decay_rate': 0.5,
    'active': 1, 'test_active': 1,
}

GRID_CFG = {
    'rsi_len_options'    : [20, 50, 100, 168, 200],
    'rsi_entry_options'  : [20, 30, 40],
    'macd_fast'          : 12,
    'macd_slow'          : 26,
    'macd_sig'           : 9,
    'stop_loss_options'  : [0.3, 0.5, 0.7, 1.0],
    'trail_start_options': [1.0, 2.0, 3.0],
    'trail_minus_options': [0.3, 0.5, 0.7],
    'rsi_exit_options'   : [65, 70, 75, 80],
    'init_profit_options': [0.5, 1.0, 1.5, 2.0],
    'decay_start'        : 0.5,
    'decay_rate'         : 0.5,
    'min_trades'         : 5,
    'score_metric'       : 'total_pnl',
}

run_id    = None
log_lines = []

def log(msg):
    ts   = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    log_lines.append(line)

def get_symbols():
    """Load all symbols from DB dynamically."""
    conn, cursor = get_db_connection()
    try:
        cursor.execute("""
            SELECT bp.id as broker_product_id, bp.local_ticker as symbol, b.name as broker_name
            FROM broker_products bp
            JOIN brokers b ON bp.broker_id = b.id
            ORDER BY b.name, bp.local_ticker
        """)
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        log(f"❌ get_symbols error: {e}")
        return []
    finally:
        conn.close()

def start_run_log():
    global run_id
    conn, cursor = get_db_connection()
    if not conn:
        return
    try:
        cursor.execute("""
            INSERT INTO tuning_runs (started_at, status, summary, log_text)
            VALUES (NOW(), 'running', 'Starting...', '')
        """)
        run_id = cursor.lastrowid
        log(f"Run ID: {run_id}")
    except Exception as e:
        print(f"❌ start_run_log error: {e}")
    finally:
        conn.close()

def save_run_log(status, summary):
    conn, cursor = get_db_connection()
    if not conn:
        return
    try:
        cursor.execute("""
            UPDATE tuning_runs
            SET status = %s, summary = %s, log_text = %s, finished_at = NOW()
            WHERE id = %s
        """, (status, summary, "\n".join(log_lines), run_id))
    except Exception as e:
        print(f"❌ save_run_log error: {e}")
    finally:
        conn.close()

def get_or_create_strategy(broker_product_id, direction, candle_time):
    conn, cursor = get_db_connection()
    if not conn:
        return None
    try:
        cursor.execute("""
            SELECT id FROM strategy_params
            WHERE broker_product_id = %s AND direction = %s AND candle_time = %s
            LIMIT 1
        """, (broker_product_id, direction, candle_time))
        row = cursor.fetchone()
        if row:
            return row['id']

        log(f"  ➕ Creating new strategy_params: bp_id={broker_product_id} {direction} {candle_time}")
        cursor.execute("""
            INSERT INTO strategy_params (
                broker_product_id, direction, candle_time,
                rsi_len, rsi_entry, stop_loss, trailing_start, trailing_drop,
                rsi_exit, init_profit, decay_start, decay_rate, active, test_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            broker_product_id, direction, candle_time,
            DEFAULT_STRATEGY['rsi_len'], DEFAULT_STRATEGY['rsi_entry'],
            DEFAULT_STRATEGY['stop_loss'], DEFAULT_STRATEGY['trailing_start'],
            DEFAULT_STRATEGY['trailing_drop'], DEFAULT_STRATEGY['rsi_exit'],
            DEFAULT_STRATEGY['init_profit'], DEFAULT_STRATEGY['decay_start'],
            DEFAULT_STRATEGY['decay_rate'], DEFAULT_STRATEGY['active'],
            DEFAULT_STRATEGY['test_active'],
        ))
        new_id = cursor.lastrowid
        log(f"  ✅ Created strategy_params id={new_id}")
        return new_id
    except Exception as e:
        log(f"❌ get_or_create_strategy error: {e}")
        return None
    finally:
        conn.close()

def run_all():
    global log_lines
    log_lines = []
    log("=" * 60)
    log("AiMN V3.1 - DAILY AUTO TUNER")
    log(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)
    start_run_log()

    symbols = get_symbols()
    log(f"Found {len(symbols)} symbols in DB")

    total = success = failed = 0
    results = []

    for sym in symbols:
        broker_upper = sym['broker_name'].upper()
        timeframes = BROKER_TFS.get(broker_upper, STOCK_TFS)

        for direction in DIRECTIONS:
            for tf in timeframes:
                total += 1
                label = f"{sym['symbol']} {direction} [{tf['tf']}]"
                log(f"\n{'─'*50}")
                log(f"▶ {label}")

                strategy_id = get_or_create_strategy(
                    sym['broker_product_id'], direction, tf['candle_time'])
                if not strategy_id:
                    failed += 1
                    continue

                cfg = {**GRID_CFG, 'timeframe': tf['tf'],
                       'bar_minutes': tf['bar_minutes'], 'bars': tf['bars']}
                try:
                    result = tune_strategy(
                        strategy_id, sym['symbol'], direction,
                        cfg=cfg, broker_name=sym['broker_name'])
                    if result:
                        success += 1
                        results.append(result)
                        log(f"✅ {label} → TotalPnL={result['result']['total_pnl']}%")
                    else:
                        failed += 1
                        log(f"❌ {label} → No valid combinations")
                except Exception as e:
                    failed += 1
                    log(f"❌ {label} → Error: {e}")

    summary = f"✅ {success} succeeded | ❌ {failed} failed"
    if results:
        best = sorted(results, key=lambda r: r['result']['total_pnl'], reverse=True)[0]
        summary += f" | Best: {best['symbol']} {best['direction']} {best['result']['total_pnl']}%"

    status = "success" if failed == 0 else "partial" if success > 0 else "failed"
    save_run_log(status, summary)
    log(f"\nRun ID {run_id} complete")

if __name__ == "__main__":
    run_all()

