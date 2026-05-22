#!/usr/bin/env python3
# test_scanner.py - BTC Multi-Timeframe Test Scanner

import mysql.connector
import requests
import time
import db_config as config
from datetime import datetime

def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True
    )

def fetch_historical_prices(symbol, timeframe, limit=100):
    try:
        clean_symbol = symbol.replace("/", "").lower()
        url = f"https://api.gemini.com/v2/candles/{clean_symbol}/{timeframe}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            candles = response.json()
            prices = [float(c[4]) for c in candles[:limit]]
            prices.reverse()
            return prices
        return None
    except Exception as e:
        print(f"  ❌ Error fetching {symbol} {timeframe}: {e}")
        return None

def calculate_rsi_real(prices, lookback=100):
    if not prices or len(prices) < 2:
        return 0.0, 0.0, 0.0
    actual_lookback = min(lookback, len(prices))
    recent = prices[-actual_lookback:]
    if not recent:
        return 0.0, 0.0, 0.0
    current = prices[-1]
    hi = max(recent)
    lo = min(recent)
    if hi == lo:
        return 50.0, hi, lo
    rsi_real = ((current - lo) / (hi - lo)) * 100
    return rsi_real, hi, lo

def calculate_macd(prices, fast=12, slow=26, signal=9):
    fast = int(fast)
    slow = int(slow)
    signal = int(signal)
    if not prices or len(prices) < slow + signal:
        return 0.0, 0.0
    def ema(data, period):
        period = int(period)
        if len(data) < period:
            return 0.0
        multiplier = 2 / (period + 1)
        ema_values = [sum(data[:period]) / period]
        for price in data[period:]:
            ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
        return ema_values[-1]
    fast_ema = ema(prices, fast)
    slow_ema = ema(prices, slow)
    macd_line = fast_ema - slow_ema
    macd_history = []
    for i in range(slow, len(prices)):
        f = ema(prices[:i+1], fast)
        s = ema(prices[:i+1], slow)
        macd_history.append(f - s)
    if len(macd_history) >= signal:
        signal_line = ema(macd_history, signal)
    else:
        signal_line = macd_line
    return macd_line, signal_line

def scan_strategies():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT sp.*, bp.local_ticker as symbol
            FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            WHERE sp.active = 1 AND bp.id = 1
            ORDER BY sp.candle_time, sp.direction
        """)
        strategies = cursor.fetchall()
        print(f"\n{'='*60}")
        print(f"  📊 Scanning {len(strategies)} BTC Test Strategies")
        print(f"{'='*60}")
        for s in strategies:
            symbol = s['symbol']
            timeframe = s['candle_time']
            direction = s['direction']
            prices = fetch_historical_prices(symbol, timeframe, 100)
            if not prices:
                print(f"  ⚠️  {symbol} {timeframe} {direction:5s} - No data")
                continue
            rsi_real, hi, lo = calculate_rsi_real(prices, lookback=len(prices))
            macd_fast = s.get('macd_fast', 12)
            macd_slow = s.get('macd_slow', 26)
            macd_sig = s.get('macd_sig', 9)
            macd_line, signal_line = calculate_macd(prices, macd_fast, macd_slow, macd_sig)
            cursor.execute("""
                UPDATE strategy_params
                SET rsi_real = %s, rsi_real_max = %s, rsi_real_min = %s,
                    macd = %s, macd_signal_line = %s, last_price = %s
                WHERE id = %s
            """, (rsi_real, hi, lo, macd_line, signal_line, prices[-1], s['id']))
            rsi_entry = float(s.get('rsi_entry', 0))
            rsi_ready = (direction == 'LONG' and rsi_real <= rsi_entry) or (direction == 'SHORT' and rsi_real >= rsi_entry)
            macd_ready = (direction == 'LONG' and macd_line > 0) or (direction == 'SHORT' and macd_line < 0)
            status = "🟢 MATCH" if (rsi_ready and macd_ready) else "⚪ WAIT"
            print(f"  {status} | {symbol} {timeframe:3s} {direction:5s} | RSI={rsi_real:5.1f} MACD={macd_line:8.2f}")
    except Exception as e:
        print(f"  🔥 ERROR: {e}")
    finally:
        cursor.close()
        conn.close()

def main():
    print("=" * 60)
    print("BTC MULTI-TIMEFRAME TEST SCANNER")
    print("Allows Parallel Trades - No Broker Locking")
    print("=" * 60)
    cycle = 0
    while True:
        try:
            cycle += 1
            print(f"\n[Cycle {cycle}] {datetime.now().strftime('%H:%M:%S')}")
            scan_strategies()
            time.sleep(10)
        except KeyboardInterrupt:
            print("\n\n👋 Test scanner stopped")
            break
        except Exception as e:
            print(f"💥 Unexpected error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
