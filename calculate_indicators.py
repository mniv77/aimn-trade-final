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

def ema(prices, period):
    mult = 2 / (period + 1)
    e = sum(prices[:period]) / period
    for p in prices[period:]:
        e = (p - e) * mult + e
    return e

def run_calculator():
    print("AiMN V3.1 - INDICATOR CALCULATION ENGINE")
    cycle_count = 0
    while True:
        conn = None
        try:
            cycle_count += 1
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
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
                    strategy_id = strat["id"]
                    symbol      = strat["symbol"]
                    candle_time = strat["candle_time"] or "1hr"
                    rsi_len     = int(strat["rsi_len"] or 100)
                    is_crypto = '/' in symbol
                    interval_map = {"1m":"1m","5m":"5m","15m":"15m","30m":"30m","1h":"1hr","1hr":"1hr","2h":"2hr","6h":"6hr","1d":"1day"}
                    if is_crypto:
                        gemini_tf = interval_map.get(candle_time, "1hr")
                        clean     = symbol.replace("/", "").lower()
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
                    else:
                        try:
                            tf_map = {"5m":"5Min","30m":"30Min","1hr":"1Hour","1h":"1Hour"}
                            alpaca_tf = tf_map.get(candle_time, "1Hour")
                            cursor2 = conn.cursor(dictionary=True)
                            cursor2.execute("SELECT api_key, api_secret FROM brokers WHERE name='Alpaca' LIMIT 1")
                            creds = cursor2.fetchone()
                            cursor2.close()
                            if not creds:
                                continue
                            headers = {
                                'APCA-API-KEY-ID': creds['api_key'],
                                'APCA-API-SECRET-KEY': creds['api_secret']
                            }
                            url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
                            params = {'timeframe': alpaca_tf, 'limit': 500, 'adjustment': 'raw'}
                            resp = requests.get(url, headers=headers, params=params, timeout=10)
                            if resp.status_code != 200:
                                continue
                            raw = resp.json().get('bars', [])
                            if not raw or len(raw) < rsi_len:
                                continue
                            highs  = [float(b['h']) for b in raw]
                            lows   = [float(b['l']) for b in raw]
                            closes = [float(b['c']) for b in raw]
                        except Exception as ae:
                            print(f"  Stock candle error {symbol}: {ae}")
                            continue
                    hi = max(highs[-rsi_len:])
                    lo = min(lows[-rsi_len:])
                    if hi <= lo:
                        continue
                    rsi_real = round(((closes[-1] - lo) / (hi - lo)) * 100, 2)
                    rsi_real = max(0, min(100, rsi_real))
                    hi_prev = max(highs[-rsi_len-1:-1])
                    lo_prev = min(lows[-rsi_len-1:-1])
                    rsi_prev = 0.0
                    if hi_prev > lo_prev:
                        rsi_prev = round(((closes[-2] - lo_prev) / (hi_prev - lo_prev)) * 100, 2)
                        rsi_prev = max(0, min(100, rsi_prev))
                    macd_val = 0.0
                    macd_prev_val = 0.0
                    if len(closes) >= 35:
                        macd_val      = round(ema(closes, 12) - ema(closes, 26), 4)
                        macd_prev_val = round(ema(closes[:-1], 12) - ema(closes[:-1], 26), 4)
                    cursor.execute("UPDATE broker_products SET rsi_real = %s, macd = %s WHERE id = %s", (rsi_real, macd_val, strat["broker_product_id"]))
                    cursor.execute("""
                        UPDATE strategy_params
                        SET rsi_prev  = rsi_real,
                            rsi_real  = %s,
                            macd      = %s,
                            macd_prev = %s
                        WHERE id = %s
                    """, (rsi_real, macd_val, macd_prev_val, strategy_id))
                    if cycle_count % 10 == 0:
                        print(f"  RSI={rsi_real} prev={rsi_prev} MACD={macd_val} {symbol}")
                except Exception as e:
                    print(f"  Error {strat.get('id','?')}: {e}")
                    continue
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"CALCULATOR ERROR: {e}")
            if conn:
                conn.close()
        time.sleep(3)

run_calculator_cycle = run_calculator

if __name__ == "__main__":
    run_calculator()
