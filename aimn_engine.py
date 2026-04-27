# aimn_engine.py - AiMN V3.1 Combined Engine
# Runs THREE threads in one always-on task:
# Thread 1: price_updater        — every 5 seconds
# Thread 2: calculate_indicators — every 3 seconds
# Thread 3: auto_executor        — every 1 second

import threading
import time
import os
from datetime import datetime

# ── Import all modules ───────────────────────────────────────
from price_updater import update_prices
from auto_executor import check_and_execute_signals, monitor_and_exit_trades
from calculate_indicators import run_calculator_cycle

# ── Log rotation settings ────────────────────────────────────
LOG_FILE     = '/home/MeirNiv/aimn-trade-final/engine.log'
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB max

def rotate_log():
    """Clear log if it exceeds MAX_LOG_SIZE"""
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
            with open(LOG_FILE, 'w') as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] Log rotated — previous log exceeded 10MB\n")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Log rotated!", flush=True)
    except Exception as e:
        print(f"Log rotation error: {e}", flush=True)

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ════════════════════════════════════════════════════════════
# THREAD 1: PRICE UPDATER — every 5 seconds
# ════════════════════════════════════════════════════════════
def price_loop():
    log("💰 Price Updater thread started")
    cycle = 0
    while True:
        try:
            cycle += 1
            update_prices()
            log(f"[PRICE Cycle {cycle}] Prices updated")
            time.sleep(5)
        except Exception as e:
            log(f"❌ Price error: {e}")
            time.sleep(5)

# ════════════════════════════════════════════════════════════
# THREAD 2: CALCULATE INDICATORS — every 3 seconds
# ════════════════════════════════════════════════════════════
def indicators_loop():
    log("📊 Indicators thread started")
    cycle = 0
    while True:
        try:
            cycle += 1
            run_calculator_cycle()
            if cycle % 10 == 0:
                log(f"[INDICATORS Cycle {cycle}] Done")
            time.sleep(3)
        except Exception as e:
            log(f"❌ Indicators error: {e}")
            time.sleep(5)

# ════════════════════════════════════════════════════════════
# THREAD 3: AUTO EXECUTOR — every 1 second
# ════════════════════════════════════════════════════════════
def executor_loop():
    log("🤖 Auto Executor thread started")
    cycle = 0
    while True:
        try:
            cycle += 1
            check_and_execute_signals()
            monitor_and_exit_trades()
            if cycle % 30 == 0:
                log(f"[EXEC Cycle {cycle}] Monitoring...")
            time.sleep(2)
        except Exception as e:
            log(f"❌ Executor error: {e}")
            time.sleep(5)

# ════════════════════════════════════════════════════════════
# MAIN — start all three threads
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("AiMN V3.1 - COMBINED ENGINE")
    print("=" * 60)
    print("✅ Thread 1: Price Updater        — every 5 seconds")
    print("✅ Thread 2: Calculate Indicators — every 3 seconds")
    print("✅ Thread 3: Auto Executor        — every 1 second")
    print("✅ Log rotation at 10MB")
    print("=" * 60)

    # Start price updater first
    t1 = threading.Thread(target=price_loop, daemon=True)
    t1.start()

    # Wait 3 seconds for first prices
    time.sleep(3)

    # Start indicators thread
    t2 = threading.Thread(target=indicators_loop, daemon=True)
    t2.start()

    # Wait 3 more seconds for first indicators
    time.sleep(3)

    # Start executor last
    t3 = threading.Thread(target=executor_loop, daemon=True)
    t3.start()

    log("🚀 All 3 threads running!")

    # Keep main thread alive + check log rotation every 5 minutes
    while True:
        time.sleep(300)
        rotate_log()
        log("💓 Engine heartbeat — all threads active")