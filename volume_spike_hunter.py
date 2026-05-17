# volume_spike_hunter.py - AiMN V3.1
# HIGH SPEED Volume Spike Detector — runs every 500ms

import mysql.connector
import time
import requests
from datetime import datetime
import pytz
import db_config as config

VOLUME_SPIKE_MULTIPLIER = 5.0
PRICE_MOVE_MIN_PCT      = 0.5
VOLUME_LOOKBACK_BARS    = 20
AUTO_EXIT_THRESHOLD     = 0.3

def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True
    )

def log(msg):
    print(f"[VOL-HUNTER {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def is_market_open_for_broker(broker_name):
    if broker_name.upper() == 'GEMINI':
        return True
    if broker_name.upper() in ('ALPACA', 'ALPACA-ETF', 'WEBULL'):
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        return now_et.weekday() < 5 and \
               now_et.hour * 60 + now_et.minute >= 570 and \
               now_et.hour * 60 + now_et.minute < 960
    return False

def fetch_live_candle_gemini(symbol):
    try:
        clean = symbol.replace('/', '').lower()
        url = f"https://api.gemini.com/v2/candles/{clean}/5m"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) >= 2:
                c = sorted(data, key=lambda x: x[0])[-1]
                return {
                    'open'  : float(c[1]),
                    'high'  : float(c[2]),
                    'low'   : float(c[3]),
                    'close' : float(c[4]),
                    'volume': float(c[5]),
                }
    except Exception as e:
        log(f"  Gemini candle error {symbol}: {e}")
    return None

def get_avg_volume(cursor, symbol, lookback=20):
    try:
        cursor.execute("""
            SELECT AVG(volume) as avg_vol
            FROM (
                SELECT volume FROM candles
                WHERE symbol = %s
                ORDER BY timestamp DESC
                LIMIT %s
            ) t
        """, (symbol, lookback + 1))
        row = cursor.fetchone()
        return float(row['avg_vol'] or 0) if row else 0
    except:
        return 0

def auto_exit_trade(cursor, trade, current_price, reason="SPIKE-OVERRIDE"):
    try:
        trade_id    = trade['id']
        entry_price = float(trade['entry_price'])
        direction   = trade['direction']

        if direction == 'LONG':
            pnl = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl = ((entry_price - current_price) / entry_price) * 100

        cursor.execute("""
            INSERT INTO orders (
                strategy_id, symbol, broker, side, candle_time,
                entry_price, exit_price, pnl_percent,
                duration_seconds, status, exit_reason, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        """, (
            trade.get('strategy_id'),
            trade['symbol'],
            trade['broker_name'],
            direction,
            trade.get('candle_time', '1hr'),
            entry_price,
            current_price,
            round(pnl, 4),
            int((datetime.now() - trade['entry_time']).total_seconds()),
            'CLOSED',
            reason,
        ))

        cursor.execute("""
            UPDATE active_trades
            SET status='CLOSED', exit_price=%s, exit_time=NOW(), exit_reason=%s
            WHERE id=%s
        """, (current_price, reason, trade_id))

        log(f"  AUTO-EXIT: {trade['symbol']} {direction} | PnL:{pnl:+.2f}% | {reason}")
        return True
    except Exception as e:
        log(f"  Auto-exit error: {e}")
        return False

def check_volume_spikes():
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT bp.id as product_id, bp.local_ticker as symbol,
                   b.name as broker_name, bp.last_price
            FROM broker_products bp
            JOIN brokers b ON bp.broker_id = b.id
            WHERE bp.is_active = 1
        """)
        products = cursor.fetchall()

        cursor.execute("""
            SELECT at.*, bp.last_price as live_price
            FROM active_trades at
            JOIN broker_products bp ON at.broker_product_id = bp.id
            WHERE at.status = 'OPEN'
        """)
        open_trades = cursor.fetchall()

        broker_trade_map = {}
        for t in open_trades:
            broker_trade_map[t['broker_name'].upper()] = t

        for p in products:
            broker     = p['broker_name']
            symbol     = p['symbol']
            product_id = p['product_id']
            last_price = float(p['last_price'] or 0)

            if last_price <= 0:
                continue
            if not is_market_open_for_broker(broker):
                continue
            if broker.upper() != 'GEMINI':
                continue

            candle = fetch_live_candle_gemini(symbol)
            if not candle or candle['volume'] <= 0:
                continue

            avg_vol = get_avg_volume(cursor, symbol)
            if avg_vol <= 0:
                continue

            volume_ratio = candle['volume'] / avg_vol

            if volume_ratio < VOLUME_SPIKE_MULTIPLIER:
                continue

            price_move = ((candle['close'] - candle['open']) / candle['open']) * 100

            if abs(price_move) < PRICE_MOVE_MIN_PCT:
                log(f"  Spike {symbol} x{volume_ratio:.1f} but move only {price_move:+.2f}% - SKIP")
                continue

            direction = 'LONG' if price_move > 0 else 'SHORT'

            log(f"SPIKE DETECTED: {symbol} {direction} | vol={volume_ratio:.1f}x | move={price_move:+.2f}%")

            existing_trade = broker_trade_map.get(broker.upper())

            if existing_trade:
                live_price  = float(existing_trade.get('live_price') or last_price)
                entry_price = float(existing_trade['entry_price'])
                ex_dir      = existing_trade['direction']
                ex_symbol   = existing_trade['symbol']

                if ex_dir == 'LONG':
                    current_pnl = ((live_price - entry_price) / entry_price) * 100
                else:
                    current_pnl = ((entry_price - live_price) / entry_price) * 100

                # SCENARIO 3: Same symbol — upgrade to spike mode
                if ex_symbol == symbol:
                    log(f"  UPGRADE: {symbol} already open — switching to SPIKE mode")
                    cursor.execute("""
                        UPDATE active_trades SET big_volume=1, candle_time='5m'
                        WHERE id=%s
                    """, (existing_trade['id'],))
                    log(f"  {symbol} now in SPIKE mode — decay disabled, trail only")
                    continue

                # SCENARIO 2: Different symbol — protect winners, exit losers
                if current_pnl >= AUTO_EXIT_THRESHOLD:
                    log(f"  Protecting {ex_symbol} PnL={current_pnl:+.2f}% — skip spike")
                    continue

                log(f"  Closing {ex_symbol} PnL={current_pnl:+.2f}% — making room for spike")
                success = auto_exit_trade(cursor, existing_trade, live_price)
                if not success:
                    continue

            # Duplicate guard
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM active_trades
                WHERE symbol=%s AND direction=%s AND status='OPEN'
            """, (symbol, direction))
            if cursor.fetchone()['cnt'] > 0:
                continue

            # SCENARIO 1: Enter spike trade
            cursor.execute("""
                INSERT INTO active_trades
                (broker_product_id, broker_name, symbol, direction,
                 entry_price, entry_time, last_price, peak_profit,
                 status, strategy_id, candle_time, big_volume)
                VALUES (%s,%s,%s,%s,%s,NOW(),%s,-999.0,'OPEN',NULL,'5m',1)
            """, (product_id, broker, symbol, direction, last_price, last_price))

            log(f"  SPIKE TRADE OPENED: {symbol} {direction} @ ${last_price:,.2f} [vol={volume_ratio:.1f}x]")

    except Exception as e:
        log(f"Spike hunter error: {e}")
        import traceback
        log(traceback.format_exc())
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    log("Volume Spike Hunter — standalone test")
    while True:
        check_volume_spikes()
        time.sleep(0.5)
