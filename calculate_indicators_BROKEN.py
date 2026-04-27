# calculate_indicators.py - AiMN V3.1 with MACD Crossover Detection
import mysql.connector
import requests
import time
from collections import defaultdict
import db_config as config

def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True
    )

price_history = defaultdict(list)
MAX_HISTORY_BARS = 200

def fetch_historical_prices(symbol, candle_time, bars=100):
    try:
        clean_symbol = symbol.replace("/", "").lower()
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1hr", "6h": "6hr", "1d": "1day"
        }
        interval = interval_map.get(candle_time, "1hr")
        url = f"https://api.gemini.com/v2/candles/{clean_symbol}/{interval}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            candles = response.json()
            closes = [float(k[4]) for k in reversed(candles[:bars])]
            return closes
        return None
    except Exception as e:
        print(f"❌ Error fetching from Gemini for {symbol}: {e}")
        return None

key = (broker_product_id, candle_time)
# ALWAYS fetch fresh data from Gemini instead of relying on cache
fetched_prices = fetch_historical_prices(symbol, candle_time, 100)
if fetched_prices and len(fetched_prices) > 0:
    price_history[key] = fetched_prices
else:
    # Fallback to cache if fetch fails
    if key not in price_history:
        price_history[key] = []
        
        
        
def calculate_rsi_real(current_price, hi, lo):
    try:
        if hi <= lo:
            return None
        rsi_real = ((current_price - lo) / (hi - lo)) * 100
        rsi_real = max(0, min(100, rsi_real))
        return round(rsi_real, 2)
    except:
        return None

def calculate_ema(prices, period):
    if len(prices) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_macd(prices, fast, slow, signal):
    """
    Calculates MACD Line, Signal Line, and Histogram.
    Returns: (macd_value, signal_value, histogram) or (None, None, None)
    """
    try:
        if len(prices) < slow + signal + 10:  # Need extra bars for signal calculation
            return None, None, None
        
        # Calculate MACD history (for signal line calculation)
        macd_values = []
        for i in range(slow, len(prices)):
            subset = prices[:i+1]
            ema_f = calculate_ema(subset, fast)
            ema_s = calculate_ema(subset, slow)
            if ema_f is not None and ema_s is not None:
                macd_values.append(ema_f - ema_s)
        
        if len(macd_values) < signal:
            return None, None, None
        
        # Current MACD line value
        macd_line = macd_values[-1]
        
        # Signal line = EMA of MACD values
        signal_line = calculate_ema(macd_values, signal)
        
        if signal_line is None:
            return round(macd_line, 4), None, None
        
        histogram = macd_line - signal_line
        
        return round(macd_line, 4), round(signal_line, 4), round(histogram, 4)
        
    except Exception as e:
        print(f"MACD calculation error: {e}")
        return None, None, None

def check_and_update_range(strategy_id, current_price, current_hi, current_lo):
    conn = get_db()
    cursor = conn.cursor()
    needs_update = False
    new_hi = current_hi
    new_lo = current_lo
    if current_price > current_hi:
        new_hi = current_price
        needs_update = True
    if current_price < current_lo:
        new_lo = current_price
        needs_update = True
    if needs_update:
        cursor.execute("""
            UPDATE strategy_params 
            SET rsi_real_max = %s, rsi_real_min = %s
            WHERE id = %s
        """, (new_hi, new_lo, strategy_id))
    cursor.close()
    conn.close()
    return new_hi, new_lo

def run_calculations_for_strategy(strategy_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT sp.id, sp.broker_product_id, sp.direction, sp.candle_time,
                   sp.rsi_len, sp.macd_fast, sp.macd_slow, sp.macd_sig,
                   sp.rsi_real_max, sp.rsi_real_min, sp.last_price,
                   bp.local_ticker as symbol
            FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            WHERE sp.id = %s AND sp.active = 1
        """, (strategy_id,))
        strat = cursor.fetchone()
        if not strat:
            return None
        symbol = strat['symbol']
        candle_time = strat['candle_time']
        current_price = float(strat['last_price'] or 0)
        if current_price <= 0:
            return {'rsi_real': 0.0, 'last_price': 0.0}
        prices = fetch_historical_prices(symbol, candle_time, bars=100)
        if not prices or len(prices) < 2:
            return {'rsi_real': 0.0, 'last_price': current_price}
        rsi_real_max = float(strat['rsi_real_max'] or 0)
        rsi_real_min = float(strat['rsi_real_min'] or 0)
        if rsi_real_max > 0 and rsi_real_min > 0:
            rsi_real_value = calculate_rsi_real(current_price, rsi_real_max, rsi_real_min)
        else:
            rsi_real_value = 0.0
        macd_fast = int(strat['macd_fast'] or 12)
        macd_slow = int(strat['macd_slow'] or 26)
        macd_sig = int(strat['macd_sig'] or 9)
        macd_value, signal_value, histogram = calculate_macd(prices, macd_fast, macd_slow, macd_sig)
        if macd_value is None:
            macd_value = 0.0
        if signal_value is None:
            signal_value = 0.0
        return {'rsi_real': rsi_real_value, 'macd_display': macd_value, 'macd_signal_display': signal_value, 'last_price': current_price}
    except Exception as e:
        print(f"Error calculating indicators for strategy {strategy_id}: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def run_calculator():
    print("=" * 60)
    print("AiMN V3.1 - MACD CROSSOVER DETECTION ENGINE")
    print("=" * 60)
    print("✅ Fetching from Gemini API")
    print("✅ Calculating RSI Real + MACD + Signal Line")
    print("✅ Detecting MACD Crossovers (Bullish/Bearish)")
    print("=" * 60)
    cycle_count = 0
    while True:
        conn = None
        try:
            cycle_count += 1
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT sp.id, sp.broker_product_id, sp.direction, sp.candle_time,
                       sp.rsi_len, sp.rsi_entry, sp.rsi_exit,
                       sp.macd_fast, sp.macd_slow, sp.macd_sig,
                       sp.rsi_real_max, sp.rsi_real_min, sp.last_price,
                       sp.macd_prev, sp.signal_prev,
                       bp.local_ticker as symbol
                FROM strategy_params sp
                JOIN broker_products bp ON sp.broker_product_id = bp.id
                WHERE sp.active = 1
                ORDER BY sp.id
            """)
            strategies = cursor.fetchall()
            if not strategies:
                print(f"[{time.strftime('%H:%M:%S')}] No active strategies found. Waiting...")
                time.sleep(5)
                continue
            print(f"\n[Cycle {cycle_count}] Processing {len(strategies)} strategies at {time.strftime('%H:%M:%S')}")
            for strat in strategies:
                try:
                    strategy_id = strat['id']
                    symbol = strat['symbol']
                    current_price = float(strat['last_price'] or 0)
                    if current_price <= 0:
                        continue
                    hi = float(strat['rsi_real_max'] or 0)
                    lo = float(strat['rsi_real_min'] or 0)
                    if hi <= 0 or lo <= 0 or hi <= lo:
                        cursor.execute("UPDATE strategy_params SET rsi_real = 0 WHERE id = %s", (strategy_id,))
                        continue
                    hi, lo = check_and_update_range(strategy_id, current_price, hi, lo)
                    rsi_real = calculate_rsi_real(current_price, hi, lo)
                    if rsi_real is None:
                        continue
                    broker_product_id = strat['broker_product_id']
                    candle_time = strat['candle_time']
                    macd_fast = int(strat['macd_fast'] or 12)
                    macd_slow = int(strat['macd_slow'] or 26)
                    macd_sig = int(strat['macd_sig'] or 9)
                    key = (broker_product_id, candle_time)
                    if key not in price_history or len(price_history[key]) < macd_slow + macd_sig + 10:
                        fetched_prices = fetch_historical_prices(symbol, candle_time, 100)
                        if fetched_prices and len(fetched_prices) > 0:
                            price_history[key] = fetched_prices
                            print(f"  📊 Initialized {symbol} with {len(fetched_prices)} bars from Gemini")
                    prices = update_price_history(broker_product_id, candle_time, current_price)
                    macd_value, signal_value, histogram = calculate_macd(prices, macd_fast, macd_slow, macd_sig)
                    if macd_value is None:
                        macd_value = 0.0
                    if signal_value is None:
                        signal_value = 0.0
                    
                    # CROSSOVER DETECTION
                    prev_macd = float(strat.get('macd_prev', 0))
                    prev_signal = float(strat.get('signal_prev', 0))
                    crossover_status = 'NONE'
                    
                    if macd_value != 0 and signal_value != 0 and prev_macd != 0 and prev_signal != 0:
                        # Bullish crossover: MACD crosses above signal
                        if prev_macd <= prev_signal and macd_value > signal_value:
                            crossover_status = 'BULLISH'
                            print(f"  🟢 BULLISH CROSSOVER DETECTED: {symbol} {strat['direction']}")
                        # Bearish crossover: MACD crosses below signal
                        elif prev_macd >= prev_signal and macd_value < signal_value:
                            crossover_status = 'BEARISH'
                            print(f"  🔴 BEARISH CROSSOVER DETECTED: {symbol} {strat['direction']}")
                    
                    # Update database
                    cursor.execute("""
                        UPDATE strategy_params 
                        SET rsi_real = %s,
                            macd = %s,
                            macd_signal = %s,
                            macd_prev = %s,
                            signal_prev = %s,
                            macd_crossover = %s
                        WHERE id = %s
                    """, (rsi_real, macd_value, signal_value, macd_value, signal_value, crossover_status, strategy_id))
                    
                    xover_icon = "🟢" if crossover_status == "BULLISH" else ("🔴" if crossover_status == "BEARISH" else "⚪")
                    print(f"  ✅ #{strategy_id} ({symbol} {strat['direction']}): RSI={rsi_real:.2f} | MACD={macd_value:.4f} | Signal={signal_value:.4f} | {xover_icon} {crossover_status}")
                    
                except Exception as e:
                    print(f"  ❌ Error #{strat.get('id', '?')}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"\n🔥 ERROR: {e}")
            import traceback
            traceback.print_exc()
            if conn:
                conn.close()
        time.sleep(3)

if __name__ == "__main__":
    run_calculator()