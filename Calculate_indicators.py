# calculate_indicators.py - AiMN V3.1 Real-Time Indicator Engine
import mysql.connector
import requests
import time
import db_config as config

def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True
    )

def run_calculator():
    print("=" * 60)
    print("AiMN V3.1 - INDICATOR CALCULATION ENGINE")
    print("✅ RSI Real from real Gemini candles")
    print("✅ MACD from real Gemini candles")
    print("=" * 60)
    cycle_count = 0

    while True:
        conn = None
        try:
            cycle_count += 1
            conn, cursor = get_db_connection()

            cursor.execute("""
                SELECT sp.id, sp.broker_product_id, sp.direction,
                       sp.candle_time, sp.rsi_len,
                       bp.last_price, bp.local_ticker as symbol
                FROM strategy_params sp
                JOIN broker_products bp ON sp.broker_product_id = bp.id
                WHERE sp.active = 1
                ORDER BY sp.id
            """)
            strategies = cursor.fetchall()

            if not strategies:
                time.sleep(5)
                continue

            for strat in strategies:
                try:
                    strategy_id = strat['id']
                    symbol      = strat['symbol']
                    candle_time = strat['candle_time'] or '1hr'
                    rsi_len     = int(strat['rsi_len'] or 100)

                    # Map candle_time to Gemini interval
                    interval_map = {
                        '1m':'1m','5m':'5m','15m':'15m','30m':'30m',
                        '1h':'1hr','1hr':'1hr','2h':'2hr','6h':'6hr','1d':'1day'
                    }
                    gemini_tf = interval_map.get(candle_time, '1hr')
                    clean     = symbol.replace('/', '').lower()
                    url       = f"https://api.gemini.com/v2/candles/{clean}/{gemini_tf}"

                    r = requests.get(url, timeout=10)
                    if r.status_code != 200:
                        continue
                    data = r.json()
                    if not isinstance(data, list) or len(data) < rsi_len:
                        continue

                    candles = sorted(data, key=lambda x: x[0])
                    highs   = [float(c[2]) for c in candles]
                    lows    = [float(c[3]) for c in candles]
                    closes  = [float(c[4]) for c in candles]

                    # RSI Real from real candles
                    hi = max(highs[-rsi_len:])
                    lo = min(lows[-rsi_len:])
                    if hi <= lo:
                        continue
                    rsi_real = round(((closes[-1] - lo) / (hi - lo)) * 100, 2)
                    rsi_real = max(0, min(100, rsi_real))

                    # MACD from real candles
                    def ema(prices, period):
                        mult = 2 / (period + 1)
                        e = sum(prices[:period]) / period
                        for p in prices[period:]:
                            e = (p - e) * mult + e
                        return e

                    macd_val = 0.0
                    if len(closes) >= 35:
                        macd_val = round(ema(closes, 12) - ema(closes, 26), 4)

                    cursor.execute("""
                        UPDATE broker_products
                        SET rsi_real = %s, macd = %s
                        WHERE id = %s
                    """, (rsi_real, macd_val, strat['broker_product_id']))

                    if cycle_count % 10 == 0:
                        print(f"  ✅ {symbol} [{candle_time}] RSI={rsi_real} MACD={macd_val}")

                except Exception as e:
                    print(f"  ❌ Error {strat.get('id','?')}: {e}")
                    continue

            conn.close()

        except Exception as e:
            print(f"\n🔥 CALCULATOR ERROR: {e}")
            if conn:
                conn.close()

        time.sleep(3)

# Alias so aimn_engine.py can import it correctly
run_calculator_cycle = run_calculator

if __name__ == "__main__":
    run_calculator()