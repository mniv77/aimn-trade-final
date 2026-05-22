# calculate_indicators.py - AiMN V3.1 WITH VOLUME SPIKE DETECTION
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
# PRICE & VOLUME HISTORY CACHE
# ==========================================
price_history = defaultdict(list)
volume_history = defaultdict(list)
MAX_HISTORY_BARS = 200

def fetch_historical_data_gemini(symbol, candle_time, bars=30):
    """
    Fetches historical candles from Gemini including VOLUME.
    Returns: (prices_list, volumes_list) or (None, None)
    """
    try:
        clean_symbol = symbol.replace("/", "").lower()
        url = f"https://api.gemini.com/v2/candles/{clean_symbol}/{candle_time}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            candles = response.json()
            # Gemini format: [timestamp, open, high, low, close, volume]
            prices = [float(c[4]) for c in candles[:bars]]  # close prices
            volumes = [float(c[5]) for c in candles[:bars]]  # volumes
            
            prices.reverse()  # oldest first
            volumes.reverse()  # oldest first
            
            return prices, volumes
        
        return None, None
        
    except Exception as e:
        print(f"  ❌ Error fetching {symbol} {candle_time}: {e}")
        return None, None

def detect_volume_spike(volumes, threshold=3.0):
    """
    Detects if current volume is abnormally high (spike).
    
    Args:
        volumes: List of volume values [oldest...newest]
        threshold: Multiplier (default 3.0 = current > 3x average)
    
    Returns: (is_spike, current_volume, avg_volume)
    """
    if not volumes or len(volumes) < 2:
        return False, 0.0, 0.0
    
    current_volume = volumes[-1]
    
    # Calculate average of previous bars (exclude current)
    avg_volume = sum(volumes[:-1]) / len(volumes[:-1])
    
    # Avoid division by zero
    if avg_volume == 0:
        return False, current_volume, avg_volume
    
    # Check if spike
    is_spike = current_volume > (avg_volume * threshold)
    
    return is_spike, current_volume, avg_volume

def calculate_rsi_real(current_price, hi, lo):
    """
    Calculates RSI Real using the TradingView formula:
    RSI Real = ((close - lo) / (hi - lo)) * 100
    """
    try:
        if hi <= lo:
            return None
        
        rsi_real = ((current_price - lo) / (hi - lo)) * 100
        rsi_real = max(0, min(100, rsi_real))
        
        return round(rsi_real, 2)
    except:
        return None

def calculate_ema(prices, period):
    """Calculates Exponential Moving Average."""
    if len(prices) < period:
        return None
    
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    
    return ema

def calculate_macd(prices, fast, slow, signal):
    """
    Calculates MACD line.
    Returns: macd_value or None
    """
    try:
        if len(prices) < slow + signal:
            return None
        
        ema_fast = calculate_ema(prices, fast)
        ema_slow = calculate_ema(prices, slow)
        
        if ema_fast is None or ema_slow is None:
            return None
        
        macd_line = ema_fast - ema_slow
        return round(macd_line, 4)
        
    except Exception as e:
        print(f"MACD calculation error: {e}")
        return None

def check_and_update_range(strategy_id, current_price, current_hi, current_lo):
    """
    Checks if price has broken out of the stored range.
    Updates rsi_real_max and rsi_real_min if needed.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    needs_update = False
    new_hi = current_hi
    new_lo = current_lo
    
    if current_price > current_hi:
        new_hi = current_price
        needs_update = True
        print(f"⚠️ Strategy {strategy_id}: Price {current_price} broke above max {current_hi}")
    
    if current_price < current_lo:
        new_lo = current_price
        needs_update = True
        print(f"⚠️ Strategy {strategy_id}: Price {current_price} broke below min {current_lo}")
    
    if needs_update:
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
    print("WITH VOLUME SPIKE DETECTION")
    print("=" * 60)
    print("Detecting volume spikes > 3x average (30-bar window)")
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
                    sp.rsi_entry,
                    sp.rsi_exit,
                    sp.macd_fast,
                    sp.macd_slow,
                    sp.macd_sig,
                    sp.rsi_real_max,
                    sp.rsi_real_min,
                    sp.last_price,
                    bp.local_ticker as symbol,
                    b.name as broker_name
                FROM strategy_params sp
                JOIN broker_products bp ON sp.broker_product_id = bp.id
                JOIN brokers b ON bp.broker_id = b.id
                WHERE sp.active = 1
                ORDER BY sp.id
            """)
            
            strategies = cursor.fetchall()
            
            if not strategies:
                print(f"[{time.strftime('%H:%M:%S')}] No active strategies found.")
                time.sleep(5)
                continue
            
            print(f"\n[Cycle {cycle_count}] Processing {len(strategies)} strategies at {time.strftime('%H:%M:%S')}")
            
            for strat in strategies:
                try:
                    strategy_id = strat['id']
                    symbol = strat['symbol']
                    broker_name = strat['broker_name']
                    current_price = float(strat['last_price'] or 0)
                    candle_time = strat['candle_time']
                    
                    if current_price <= 0:
                        continue
                    
                    # Get range values
                    hi = float(strat['rsi_real_max'] or 0)
                    lo = float(strat['rsi_real_min'] or 0)
                    
                    if hi <= 0 or lo <= 0 or hi <= lo:
                        cursor.execute("""
                            UPDATE strategy_params 
                            SET rsi_real = 0, volume_spike = 0
                            WHERE id = %s
                        """, (strategy_id,))
                        continue
                    
                    # ==========================================
                    # FETCH VOLUME DATA (Gemini only for now)
                    # ==========================================
                    volume_spike_flag = 0
                    current_volume = 0.0
                    avg_volume = 0.0
                    
                    if broker_name == 'Gemini':
                        prices, volumes = fetch_historical_data_gemini(symbol, candle_time, bars=30)
                        
                        if volumes:
                            is_spike, current_volume, avg_volume = detect_volume_spike(volumes, threshold=3.0)
                            
                            if is_spike:
                                volume_spike_flag = 1
                                print(f"  🔴 SPIKE! Strategy #{strategy_id} ({symbol}): Vol={current_volume:.0f} vs Avg={avg_volume:.0f} ({current_volume/avg_volume:.1f}x)")
                    
                    # ==========================================
                    # CHECK AND UPDATE RANGE
                    # ==========================================
                    hi, lo = check_and_update_range(strategy_id, current_price, hi, lo)
                    
                    # ==========================================
                    # CALCULATE RSI REAL
                    # ==========================================
                    rsi_real = calculate_rsi_real(current_price, hi, lo)
                    
                    if rsi_real is None:
                        continue
                    
                    # ==========================================
                    # UPDATE DATABASE WITH VOLUME DATA
                    # ==========================================
                    cursor.execute("""
                        UPDATE strategy_params 
                        SET rsi_real = %s,
                            volume_spike = %s,
                            current_volume = %s,
                            avg_volume = %s
                        WHERE id = %s
                    """, (rsi_real, volume_spike_flag, current_volume, avg_volume, strategy_id))
                    
                    spike_indicator = "🔴" if volume_spike_flag else "✅"
                    print(f"  {spike_indicator} Strategy #{strategy_id} ({symbol} {strat['direction']}): RSI={rsi_real:.2f} | Vol={current_volume:.0f} (avg={avg_volume:.0f})")
                    
                except Exception as e:
                    print(f"  ❌ Error processing strategy #{strat.get('id', '?')}: {e}")
                    continue
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"\n🔥 CALCULATOR ERROR: {e}")
            import traceback
            traceback.print_exc()
            if conn:
                conn.close()
        
        time.sleep(3)

if __name__ == "__main__":
    run_calculator()