# calculate_indicators.py - AiMN V3.1
# All parameters read from strategy_params per symbol — no hardcoded values!
# Gemini crypto  — fetches candles from Gemini API (24/7)
# Alpaca stocks  — fetches bars from Alpaca API (NYSE hours only)
# Writes last_price, rsi_real, macd, price_updated_at to broker_products

import mysql.connector
import requests
import time
from datetime import datetime
import pytz
import db_config as config

# ── Fallback defaults (only used if DB read fails) ────────────
DEFAULT_RSI_LOOKBACK = 100
DEFAULT_CANDLE_TIME  = '1h'
SLEEP_SECONDS        = 10

INTERVAL_MAP = {
    '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
    '1h': '1hr', '1hr': '1hr', '2h': '2hr', '6h': '6hr', '1d': '1day'
}
ALPACA_TIMEFRAME = {
    '1m': '1Min', '5m': '5Min', '15m': '15Min', '30m': '30Min',
    '1h': '1Hour', '1hr': '1Hour', '2h': '2Hour', '1d': '1Day'
}

def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST, user=config.DB_USER,
        password=config.DB_PASSWORD, database=config.DB_NAME,
        autocommit=True
    )

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# ── Market hours check ────────────────────────────────────────
def is_market_open(session):
    if session['is_24_7']:
        return True
    try:
        tz  = pytz.timezone(session['timezone'] or 'US/Eastern')
        now = datetime.now(tz)
        if now.weekday() >= 5 and not session['trade_weekends']:
            return False
        start = datetime.strptime(str(session['start_time']), '%H:%M:%S').time()
        end   = datetime.strptime(str(session['end_time']),   '%H:%M:%S').time()
        return start <= now.time() <= end
    except Exception as e:
        log(f"  ⚠️  Market hours error: {e}")
        return False

# ── Load strategy params per product ─────────────────────────
def load_strategy_params(cursor, product_id):
    """
    Load best active strategy params for this product.
    Returns dict with rsi_len, candle_time.
    Falls back to defaults if nothing found.
    """
    try:
        cursor.execute("""
            SELECT rsi_len, candle_time
            FROM strategy_params
            WHERE broker_product_id = %s
              AND active = 1
            ORDER BY pl_pct DESC
            LIMIT 1
        """, (product_id,))
        row = cursor.fetchone()
        if row:
            return {
                'rsi_len'    : int(row['rsi_len'])    if row['rsi_len']    else DEFAULT_RSI_LOOKBACK,
                'candle_time': row['candle_time']      if row['candle_time'] else DEFAULT_CANDLE_TIME,
            }
    except Exception as e:
        log(f"  ⚠️  load_strategy_params error for product {product_id}: {e}")

    return {
        'rsi_len'    : DEFAULT_RSI_LOOKBACK,
        'candle_time': DEFAULT_CANDLE_TIME,
    }

# ── Gemini price fetch ────────────────────────────────────────
def fetch_prices_gemini(symbol, candle_time='1h', bars=200):
    try:
        clean    = symbol.replace('/', '').lower()
        interval = INTERVAL_MAP.get(candle_time, '1hr')
        url      = f"https://api.gemini.com/v2/candles/{clean}/{interval}"
        r        = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if not isinstance(data, list):
                log(f"  ❌ Gemini unexpected response for {symbol}: {data}")
                return None
            candles = sorted(data, key=lambda x: x[0])
            return {
                'closes': [float(c[4]) for c in candles[-bars:]],
                'highs' : [float(c[2]) for c in candles[-bars:]],
                'lows'  : [float(c[3]) for c in candles[-bars:]],
            }
        log(f"  ❌ Gemini HTTP {r.status_code} for {symbol}")
        return None
    except Exception as e:
        log(f"  ❌ Gemini fetch error {symbol}: {e}")
        return None

# ── Alpaca bars fetch ─────────────────────────────────────────
def fetch_prices_alpaca(symbol, api_key, api_secret, candle_time='1h', bars=200):
    try:
        timeframe = ALPACA_TIMEFRAME.get(candle_time, '1Hour')
        url       = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
        headers   = {
            'APCA-API-KEY-ID':     api_key,
            'APCA-API-SECRET-KEY': api_secret
        }
        params = {'timeframe': timeframe, 'limit': 10000,
          'adjustment': 'raw', 'feed': 'sip',
          'start': '2020-01-01', 'sort': 'asc'}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            bars_ = r.json().get('bars', [])
            if not bars_:
                log(f"  ⚠️  Alpaca: no bars for {symbol}")
                return None
            return {
                'closes': [float(b['c']) for b in bars_],
                'highs' : [float(b['h']) for b in bars_],
                'lows'  : [float(b['l']) for b in bars_],
            }
        log(f"  ❌ Alpaca HTTP {r.status_code} for {symbol}: {r.text[:100]}")
        return None
    except Exception as e:
        log(f"  ❌ Alpaca fetch error {symbol}: {e}")
        return None

# ── Indicator math ────────────────────────────────────────────
def calculate_ema(prices, period):
    if len(prices) < period:
        return None
    mult = 2 / (period + 1)
    ema  = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = (p - ema) * mult + ema
    return ema

def calculate_macd(prices, fast=12, slow=26, signal=9):
    try:
        if len(prices) < slow + signal + 10:
            return None, None
        macd_values = []
        for i in range(slow, len(prices)):
            ef = calculate_ema(prices[:i+1], fast)
            es = calculate_ema(prices[:i+1], slow)
            if ef and es:
                macd_values.append(ef - es)
        if len(macd_values) < signal:
            return None, None
        macd_line   = macd_values[-1]
        signal_line = calculate_ema(macd_values, signal)
        return round(macd_line, 6), round(signal_line, 6) if signal_line else None
    except:
        return None, None

def calculate_rsi_real(closes, highs, lows, lookback):
    """RSI Real using high/low range over lookback bars"""
    try:
        hi = max(highs[-lookback:])
        lo = min(lows[-lookback:])
        if hi <= lo:
            return None
        current = closes[-1]
        return round(max(0, min(100, ((current - lo) / (hi - lo)) * 100)), 2)
    except:
        return None

# ── Core processing ───────────────────────────────────────────
def process_strategies(cursor, alpaca_key, alpaca_secret):
    """Calculate RSI and MACD per strategy — each gets its own rsi_len and candle_time"""
    cursor.execute("""
        SELECT
            sp.id as strategy_id,
            sp.rsi_len,
            sp.candle_time,
            sp.direction,
            bp.id as product_id,
            bp.local_ticker as symbol,
            b.name as broker_name,
            ms.is_24_7, ms.start_time, ms.end_time,
            ms.timezone, ms.trade_weekends
        FROM strategy_params sp
        JOIN broker_products bp ON sp.broker_product_id = bp.id
        JOIN brokers b ON bp.broker_id = b.id
        LEFT JOIN market_sessions ms ON bp.session_id = ms.id
        WHERE sp.active = 1
          AND bp.is_active = 1
          AND b.name IN ('Gemini', 'Alpaca')
        ORDER BY bp.local_ticker, sp.direction, sp.candle_time
    """)
    strategies = cursor.fetchall()

    # Cache candles per symbol+timeframe to avoid re-fetching
    candle_cache = {}

    for s in strategies:
        symbol      = s['symbol']
        broker_name = s['broker_name']
        strategy_id = s['strategy_id']
        product_id  = s['product_id']
        rsi_len     = int(s['rsi_len']    or DEFAULT_RSI_LOOKBACK)
        candle_time = s['candle_time']    or DEFAULT_CANDLE_TIME
        direction   = s['direction']

        if not is_market_open(s):
            if broker_name == 'Alpaca':
                log(f"  ⏰ NYSE CLOSED: {symbol} — skipping")
            continue

        try:
            # Cache key per symbol+timeframe
            cache_key = f"{symbol}_{candle_time}"

            if cache_key not in candle_cache:
                data = None
                if broker_name == 'Gemini':
                    data = fetch_prices_gemini(symbol, candle_time, rsi_len + 50)
                elif broker_name == 'Alpaca':
                    if not alpaca_key:
                        log(f"  ⚠️ No Alpaca credentials — skipping {symbol}")
                        continue
                    data = fetch_prices_alpaca(
                        symbol, alpaca_key, alpaca_secret,
                        candle_time, rsi_len + 50)
                candle_cache[cache_key] = data
            else:
                data = candle_cache[cache_key]

            if not data or len(data['closes']) < 30:
                log(f"  ❌ {symbol} {candle_time} — insufficient data")
                continue

            closes = data['closes']
            highs  = data['highs']
            lows   = data['lows']

            current_price = closes[-1]

            # RSI Real — per strategy rsi_len
            rsi_real = calculate_rsi_real(closes, highs, lows, rsi_len) or 0.0

            # MACD
            macd_val, _ = calculate_macd(closes)
            if macd_val is None:
                macd_val = 0.0

            # ✅ Write RSI/MACD to strategy_params row
            cursor.execute("""
                UPDATE strategy_params
                SET rsi_real = %s, macd = %s
                WHERE id = %s
            """, (rsi_real, macd_val, strategy_id))

            # ✅ Also update broker_products price
            cursor.execute("""
                UPDATE broker_products
                SET last_price = %s, price_updated_at = NOW()
                WHERE id = %s
            """, (current_price, product_id))

            # ✅ Update active_trades price
            cursor.execute("""
                UPDATE active_trades
                SET last_price = %s
                WHERE broker_product_id = %s AND status = 'OPEN'
            """, (current_price, product_id))

            log(f"  ✅ {broker_name} {symbol} {direction} [{candle_time}] | "
                f"${current_price:,.2f} | RSI={rsi_real:.1f} | "
                f"MACD={macd_val:.4f} | rsi_len={rsi_len}")

        except Exception as e:
            log(f"  ❌ Error {symbol} {direction} [{candle_time}]: {e}")
            continue
# ── Main loop ─────────────────────────────────────────────────
def run_calculator():
    log("=" * 60)
    log("HaGolem Auto Trading by AiMN - INDICATOR ENGINE")
    log("✅ All params read from strategy_params per symbol")
    log("=" * 60)

    alpaca_key = alpaca_secret = None
    cycle = 0

    while True:
        conn = None
        try:
            cycle += 1
            conn   = get_db()
            cursor = conn.cursor(dictionary=True)

            if not alpaca_key:
                cursor.execute("SELECT api_key, api_secret FROM brokers WHERE name = 'Alpaca' LIMIT 1")
                row = cursor.fetchone()
                if row and row['api_key']:
                    alpaca_key    = row['api_key']
                    alpaca_secret = row['api_secret']
                    log("  ✅ Alpaca credentials loaded")

            log(f"\n[Cycle {cycle}]")
            process_strategies(cursor, alpaca_key, alpaca_secret)
            cursor.close()
            conn.close()

        except Exception as e:
            log(f"🔥 ERROR: {e}")
            if conn:
                conn.close()

        time.sleep(SLEEP_SECONDS)

# ── Single cycle for external callers ─────────────────────────
def run_calculator_cycle():
    conn = None
    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)

        alpaca_key = alpaca_secret = None
        cursor.execute("SELECT api_key, api_secret FROM brokers WHERE name='Alpaca' LIMIT 1")
        row = cursor.fetchone()
        if row and row['api_key']:
            alpaca_key    = row['api_key']
            alpaca_secret = row['api_secret']

        process_strategies(cursor, alpaca_key, alpaca_secret)
        cursor.close()
        conn.close()

    except Exception as e:
        log(f"❌ Cycle error: {e}")
        if conn:
            conn.close()

if __name__ == "__main__":
    run_calculator()