# calculate_indicators.py - AiMN V3.1 Real-Time Indicator Engine
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

# ==========================================
# PRICE HISTORY CACHE (For MACD Calculation)
# ==========================================
price_history = defaultdict(list)  # Key: (broker_product_id, candle_time) -> list of prices
MAX_HISTORY_BARS = 200  # Keep enough history for longest MACD calculation

def fetch_historical_prices(symbol, candle_time, bars=100):
    """
    Fetches historical price data from a public API.
    You can replace this with your preferred data source.
    
    Returns: List of closing prices [oldest...newest]
    """
    try:
        # Using Binance as example for crypto (you can change this)
        if "/" in symbol:
            # Crypto: BTC/USD -> BTCUSD
            clean_symbol = symbol.replace("/", "")
            
            # Map candle_time to Binance interval
            interval_map = {
                "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1d"
            }
            interval = interval_map.get(candle_time, "1h")
            
            url = f"https://api.binance.com/api/v3/klines"
            params = {
                "symbol": clean_symbol + "T",  # BTCUSDT
                "interval": interval,
                "limit": bars
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                klines = response.json()
                # Kline format: [open_time, open, high, low, close, ...]
                closes = [float(k[4]) for k in klines]  # Index 4 is close price
                return closes
        
        # For stocks, you'd use a different API here (Yahoo, Alpaca, etc.)
        # Placeholder for now
        return None
            
    except Exception as e:
        print(f"Error fetching historical prices for {symbol}: {e}")
        return None

def update_price_history(broker_product_id, candle_time, current_price):
    """
    Updates the price history cache with the latest price.
    This simulates real-time candle building.
    """
    key = (broker_product_id, candle_time)
    
    if key not in price_history or len(price_history[key]) == 0:
        # First time - we don't have history yet, just add current price
        price_history[key].append(current_price)
    else:
        # Add current price to history
        price_history[key].append(current_price)
        
        # Keep only last MAX_HISTORY_BARS
        if len(price_history[key]) > MAX_HISTORY_BARS:
            price_history[key] = price_history[key][-MAX_HISTORY_BARS:]
    
    return price_history[key]

def calculate_rsi_real(current_price, hi, lo):
    """
    Calculates RSI Real using the TradingView formula:
    RSI Real = ((close - lo) / (hi - lo)) * 100
    
    Returns: RSI value (0-100) or None if invalid
    """
    try:
        if hi <= lo:
            return None
        
        rsi_real = ((current_price - lo) / (hi - lo)) * 100
        
        # Clamp between 0 and 100
        rsi_real = max(0, min(100, rsi_real))
        
        return round(rsi_real, 2)
    except:
        return None

def calculate_ema(prices, period):
    """
    Calculates Exponential Moving Average.
    """
    if len(prices) < period:
        return None
    
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period  # Start with SMA
    
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    
    return ema

def calculate_macd(prices, fast, slow, signal):
    """
    Calculates MACD, Signal, and Histogram.
    Returns: (macd_value, signal_value, histogram) or (None, None, None)
    """
    try:
        if len(prices) < slow + signal:
            return None, None, None
        
        # Calculate EMAs
        ema_fast = calculate_ema(prices, fast)
        ema_slow = calculate_ema(prices, slow)
        
        if ema_fast is None or ema_slow is None:
            return None, None, None
        
        # MACD Line = Fast EMA - Slow EMA
        macd_line = ema_fast - ema_slow
        
        # For Signal line, we need MACD history
        # Simplified: Calculate signal on last 'signal' periods of MACD values
        # (In production, you'd maintain MACD history properly)
        
        # For now, return just the MACD line value
        # You can enhance this later with proper signal calculation
        
        return round(macd_line, 4), None, None
        
    except Exception as e:
        print(f"MACD calculation error: {e}")
        return None, None, None

def check_and_update_range(strategy_id, current_price, current_hi, current_lo):
    """
    Checks if price has broken out of the stored range.
    If yes, updates rsi_real_max and rsi_real_min in database.
    
    This FIXES THE BUG where it was setting values to 0!
    """
    conn = get_db()
    cursor = conn.cursor()
    
    needs_update = False
    new_hi = current_hi
    new_lo = current_lo
    
    # Check if price broke above max
    if current_price > current_hi:
        new_hi = current_price
        needs_update = True
        print(f"⚠️ Strategy {strategy_id}: Price {current_price} broke above max {current_hi}. Updating range.")
    
    # Check if price broke below min
    if current_price < current_lo:
        new_lo = current_price
        needs_update = True
        print(f"⚠️ Strategy {strategy_id}: Price {current_price} broke below min {current_lo}. Updating range.")
    
    if needs_update:
        # UPDATE THE RANGE - THIS IS THE FIX!
        cursor.execute("""
            UPDATE strategy_params 
            SET rsi_real_max = %s, rsi_real_min = %s
            WHERE id = %s
        """, (new_hi, new_lo, strategy_id))
        print(f"✅ Strategy {strategy_id}: Range updated to [{new_lo}, {new_hi}]")
    
    cursor.close()
    conn.close()
    
    return new_hi, new_lo

def run_calculator():
    print("=" * 60)
    print("AiMN V3.1 - INDICATOR CALCULATION ENGINE")
    print("=" * 60)
    print("Calculating: RSI Real + MACD for all active strategies")
    print("Auto-updating ranges when price breaks out")
    print("=" * 60)
    
    cycle_count = 0
    
    while True:
        conn = None
        try:
            cycle_count += 1
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            
            # Fetch all active strategies
            cursor.execute("""
                SELECT 
                    sp.id,
                    sp.broker_product_id,
                    sp.direction,
                    sp.candle_time,
                    sp.rsi_len,
                    sp.rsi_entry,
                    sp.rsi_exit,
                    sp.macd_fast,
                    sp.macd_slow,
                    sp.macd_sig,
                    sp.rsi_real_max,
                    sp.rsi_real_min,
                    sp.last_price,
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
                        print(f"  ⏭️  Strategy #{strategy_id} ({symbol}): No price data yet")
                        continue
                    
                    # Get range values
                    hi = float(strat['rsi_real_max'] or 0)
                    lo = float(strat['rsi_real_min'] or 0)
                    
                    # Check if range is valid
                    if hi <= 0 or lo <= 0 or hi <= lo:
                        print(f"  ⚠️  Strategy #{strategy_id} ({symbol}): Invalid range [{lo}, {hi}] - needs retuning")
                        # Set to 0 to signal user to retune
                        cursor.execute("""
                            UPDATE strategy_params 
                            SET rsi_real = 0, macd = 0
                            WHERE id = %s
                        """, (strategy_id,))
                        continue
                    
                    # ==========================================
                    # CHECK AND UPDATE RANGE IF NEEDED (BUG FIX)
                    # ==========================================
                    hi, lo = check_and_update_range(strategy_id, current_price, hi, lo)
                    
                    # ==========================================
                    # CALCULATE RSI REAL
                    # ==========================================
                    rsi_real = calculate_rsi_real(current_price, hi, lo)
                    
                    if rsi_real is None:
                        print(f"  ❌ Strategy #{strategy_id} ({symbol}): RSI calculation failed")
                        continue
                    
                    # ==========================================
                    # CALCULATE MACD
                    # ==========================================
                    broker_product_id = strat['broker_product_id']
                    candle_time = strat['candle_time']
                    macd_fast = int(strat['macd_fast'] or 12)
                    macd_slow = int(strat['macd_slow'] or 26)
                    macd_sig = int(strat['macd_sig'] or 9)
                    
                    # Update price history
                    prices = update_price_history(broker_product_id, candle_time, current_price)
                    
                    # Calculate MACD
                    macd_value, signal_value, histogram = calculate_macd(prices, macd_fast, macd_slow, macd_sig)
                    
                    if macd_value is None:
                        # Not enough history yet
                        macd_value = 0.0
                        print(f"  ⏳ Strategy #{strategy_id} ({symbol}): Building MACD history ({len(prices)}/{macd_slow + macd_sig} bars)")
                    
                    # ==========================================
                    # UPDATE DATABASE
                    # ==========================================
                    cursor.execute("""
                        UPDATE strategy_params 
                        SET rsi_real = %s, macd = %s
                        WHERE id = %s
                    """, (rsi_real, macd_value, strategy_id))
                    
                    print(f"  ✅ Strategy #{strategy_id} ({symbol} {strat['direction']}): RSI={rsi_real:.2f} | MACD={macd_value:.4f} | Price=${current_price:.2f}")
                    
                except Exception as e:
                    print(f"  ❌ Error processing strategy #{strat.get('id', '?')}: {e}")
                    continue
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"\n🔥 CALCULATOR ERROR: {e}")
            if conn:
                conn.close()
        
        # Wait before next cycle
        time.sleep(3)

if __name__ == "__main__":
    run_calculator()