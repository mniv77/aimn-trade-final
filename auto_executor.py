# auto_executor.py - AiMN V3.1
# Called by aimn_engine.py Thread 3
#
# Functions exported:
#   check_volume_signals()       — volume pre-filter (stub, expandable)
#   check_and_execute_signals()  — entry logic
#   monitor_and_exit_trades()    — exit logic
#
# ═══════════════════════════════════════════════════════════
# FIXES vs old safe_auto_executor.py:
#
# FIX 1  — price always from broker_products.last_price (no direct Gemini call)
# FIX 2  — locked_symbols keyed on symbol+direction (not broker-level lock)
# FIX 3  — 300-second minimum before STOP or TRAIL can fire
# FIX 4  — 20% sanity check blocks phantom losses (MSFT -61% fix)
# FIX 5  — TIME-STOP: exit stagnant/losing trades after TIME_STOP_HOURS
# FIX 6  — smart cooldown: STOP locks both directions 2hr; TRAIL/RSI frees opposite immediately
# FIX 7  — MACD rising/falling directional filter with extreme RSI override
# FIX 8  — stale price guard: skip if price_updated_at > MAX_PRICE_AGE_SECONDS
# FIX 9  — duplicate trade guard: one open trade per symbol+direction
# ═══════════════════════════════════════════════════════════

import mysql.connector
import time
from datetime import datetime, timedelta
import pytz
import db_config as config

# ── Constants ────────────────────────────────────────────────
MAX_PRICE_AGE_SECONDS  = 60      # skip stale prices older than this
MIN_TRADE_SECONDS      = 300     # STOP/TRAIL cannot fire in first 5 minutes
STOP_COOLDOWN_MINUTES  = 120     # after STOP: both directions locked 2 hours
TRAIL_COOLDOWN_MINUTES = 30      # after TRAIL/RSI/DECAY: only same direction locked
TIME_STOP_HOURS        = 3.0     # exit trade if stagnant/losing after this many hours
TIME_STOP_MIN_PNL      = 0.00   # TIME-STOP only fires if P&L below this threshold
SANITY_MAX_PNL         = 20.0    # skip if abs(pnl) > 20% — phantom loss guard

# Default fallback params (used if strategy_params value is NULL)
DEFAULT_PARAMS = {
    'rsi_entry':      25.0,
    'rsi_exit':       70.0,
    'stop_loss':       2.0,
    'trailing_start':  1.5,
    'trailing_drop':   0.5,
    'init_profit':     1.0,
    'decay_start':     2.0,
    'decay_rate':      0.5,
    'candle_time':    '1h',
}

# In-memory lock set: entries are "SYMBOL_DIRECTION" e.g. "ETH/USD_SHORT"
# Values: datetime when lock expires
locked_symbols = {}   # { "ETH/USD_SHORT": datetime_expires }

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ── DB ───────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True
    )

# ── Lock helpers ─────────────────────────────────────────────
def is_locked(symbol, direction):
    """Check if symbol+direction is currently locked"""
    key = f"{symbol}_{direction}"
    expires = locked_symbols.get(key)
    if expires and datetime.now() < expires:
        return True
    if key in locked_symbols:
        del locked_symbols[key]  # expired, clean up
    return False

def lock_symbol(symbol, direction, minutes):
    key = f"{symbol}_{direction}"
    locked_symbols[key] = datetime.now() + timedelta(minutes=minutes)
    log(f"  🔒 Locked {key} for {minutes} min")

def apply_exit_cooldown(symbol, direction, exit_reason):
    """
    Smart cooldown after exit:
    - STOP  → lock BOTH directions for 2 hours
    - TRAIL/RSI/DECAY/TIME-STOP → lock same direction only for 30 min
                                   opposite direction freed immediately
    """
    opposite = 'SHORT' if direction == 'LONG' else 'LONG'
    if 'STOP' in exit_reason:
        lock_symbol(symbol, direction, STOP_COOLDOWN_MINUTES)
        lock_symbol(symbol, opposite,  STOP_COOLDOWN_MINUTES)
        log(f"  🔒 STOP cooldown: {symbol} BOTH directions locked {STOP_COOLDOWN_MINUTES}min")
    else:
        lock_symbol(symbol, direction, TRAIL_COOLDOWN_MINUTES)
        # Remove opposite lock if it exists — free for immediate re-entry
        opp_key = f"{symbol}_{opposite}"
        if opp_key in locked_symbols:
            del locked_symbols[opp_key]
        log(f"  ✅ {exit_reason}: {symbol}_{opposite} FREE for immediate re-entry")

# ── Market hours ─────────────────────────────────────────────
def is_market_open(broker_name):
    """Return True if broker market is open right now"""
    if broker_name.upper() in ('GEMINI',):
        return True  # Crypto is 24/7
    # Alpaca / stocks: NYSE Mon-Fri 9:30-16:00 ET
    et = pytz.timezone('US/Eastern')
    now_et = datetime.now(et)
    if now_et.weekday() >= 5:
        return False
    minutes = now_et.hour * 60 + now_et.minute
    return 570 <= minutes < 960  # 9:30am to 4:00pm

# ── Price helpers ────────────────────────────────────────────
def get_live_price_from_db(symbol):
    """
    Always read from broker_products.last_price — written by price_updater thread.
    Returns (price, age_seconds) or (0, 9999) on failure.
    """
    try:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT last_price, price_updated_at
            FROM broker_products
            WHERE local_ticker = %s
            LIMIT 1
        """, (symbol,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row and row['last_price']:
            price = float(row['last_price'])
            age   = 9999
            if row['price_updated_at']:
                age = (datetime.now() - row['price_updated_at']).total_seconds()
            return price, age
    except Exception as e:
        log(f"  ⚠️ get_live_price_from_db error ({symbol}): {e}")
    return 0.0, 9999

# ── Load strategies ──────────────────────────────────────────
def load_strategies(cursor):
    """Load all active strategies with their tuned params and live indicator values"""
    cursor.execute("""
        SELECT
            sp.id,
            sp.direction,
            sp.rsi_entry,
            sp.rsi_exit,
            sp.stop_loss,
            sp.trailing_start,
            sp.trailing_drop,
            sp.init_profit,
            sp.decay_start,
            sp.decay_rate,
            sp.candle_time,
            sp.entry_price,
            sp.entry_time,
            sp.peak_profit,
            sp.active_order_id,
            sp.rsi_real,
            sp.macd,
            sp.macd_prev,
            sp.cooldown_until,
            sp.rsi_prev,
            sp.macd_signal,
            bp.id          AS product_id,
            bp.local_ticker AS symbol,
            at.entry_time  AS at_entry_time,
            bp.last_price,
            bp.price_prev3,
            bp.price_updated_at,
            b.name         AS broker_name
        FROM strategy_params sp
        JOIN broker_products bp ON sp.broker_product_id = bp.id
        LEFT JOIN active_trades at ON at.id = sp.active_order_id AND at.status = 'OPEN'
        JOIN brokers b          ON bp.broker_id = b.id
        WHERE sp.active = 1
          AND bp.is_active = 1
        ORDER BY sp.id
    """)
    return cursor.fetchall()

# ══════════════════════════════════════════════════════════════
# THREAD ENTRY POINT 1: VOLUME SIGNALS (stub — expandable)
# ══════════════════════════════════════════════════════════════
def relink_open_trades():
    """On engine startup, relink any open active_trades back to strategy_params"""
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT at.id, at.symbol, at.direction, at.entry_price, at.entry_time
            FROM active_trades at
            WHERE at.status = 'OPEN'
        """)
        open_trades = cursor.fetchall()
        for t in open_trades:
            # Find best matching strategy (highest pl_pct)
            cursor.execute("""
                SELECT sp.id FROM strategy_params sp
                JOIN broker_products bp ON sp.broker_product_id = bp.id
                WHERE bp.local_ticker = %s
                  AND sp.direction    = %s
                  AND sp.active       = 1
                  AND sp.active_order_id IS NULL
                ORDER BY sp.pl_pct DESC
                LIMIT 1
            """, (t['symbol'], t['direction']))
            best = cursor.fetchone()
            if not best:
                continue
            cursor.execute("""
                UPDATE strategy_params
                SET active_order_id = %s,
                    entry_price     = %s,
                    entry_time      = %s,
                    peak_profit     = -999.00
                WHERE id = %s
            """, (t['id'], t['entry_price'], t['entry_time'], best['id']))
            log(f"  🔗 Relinked {t['symbol']} {t['direction']} trade {t['id']} to strategy_params")
        log(f"  ✅ Relinked {len(open_trades)} open trades on startup")
    except Exception as e:
        log(f"  ❌ relink_open_trades error: {e}")
    finally:
        cursor.close()
        conn.close()

def check_volume_signals():
    """
    Placeholder for volume spike pre-filter.
    Currently a no-op — volume_spike_hunter.py handles this separately.
    """
    pass

# ══════════════════════════════════════════════════════════════
# THREAD ENTRY POINT 2: ENTRY SIGNALS
# ══════════════════════════════════════════════════════════════
def check_and_execute_signals():
    """Scan all active strategies, check entry conditions, open trades."""
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        strategies = load_strategies(cursor)
        log(f"  📡 Entry scan: {len(strategies)} strategies")
        for s in strategies:
            try:
                symbol    = s["symbol"]
                direction = s["direction"]
                broker    = s["broker_name"]
                if s["active_order_id"] is not None:
                    continue
                if s.get("cooldown_until") and datetime.now() < s["cooldown_until"]:
                    continue
                if is_locked(symbol, direction):
                    continue
                if not is_market_open(broker):
                    continue
                price_prev3 = float(s.get("price_prev3") or 0)
                current_px  = float(s.get("last_price") or 0) or price_prev3
                if price_prev3 > 0 and current_px > 0:
                    if direction == "LONG" and current_px < price_prev3:
                        continue
                    if direction == "SHORT" and current_px > price_prev3:
                        continue
                price, age = get_live_price_from_db(symbol)
                if price <= 0:
                    continue
                if age > MAX_PRICE_AGE_SECONDS:
                    continue
                rsi_real      = float(s["rsi_real"]   or 50.0)
                rsi_prev_val  = float(s["rsi_prev"]   or 50.0)
                macd_val      = float(s["macd"]        or 0.0)
                macd_prev_val = float(s["macd_prev"]   or 0.0)
                rsi_entry     = float(s["rsi_entry"]   or DEFAULT_PARAMS["rsi_entry"])
                if direction == "LONG":
                    rsi_signal    = rsi_real <= rsi_entry
                    rsi_bouncing  = rsi_real > rsi_prev_val
                    macd_rising   = macd_val > macd_prev_val
                    rsi_extreme   = rsi_real <= 8
                    macd_signal   = macd_rising or rsi_extreme
                    bounce_signal = rsi_bouncing or rsi_extreme
                else:
                    rsi_signal    = rsi_real >= (100 - rsi_entry)
                    rsi_bouncing  = rsi_real < rsi_prev_val
                    macd_falling  = macd_val < macd_prev_val
                    rsi_extreme   = rsi_real >= 92
                    macd_signal   = macd_falling or rsi_extreme
                    bounce_signal = rsi_bouncing or rsi_extreme
                if not (rsi_signal and macd_signal and bounce_signal):
                    continue
                cursor.execute("SELECT id, direction FROM active_trades WHERE symbol=%s AND status='OPEN' LIMIT 1", (symbol,))
                existing = cursor.fetchone()
                if existing:
                    log(f"  ⚠️ DUPLICATE GUARD: {symbol} already has {existing['direction']} open")
                    continue
                cursor.execute("SELECT COUNT(*) as cnt FROM active_trades WHERE status='OPEN'")
                if cursor.fetchone()["cnt"] >= 3:
                    log(f"  ⚠️ MAX TRADES: skipping {symbol}")
                    continue
                log(f"  🚀 SIGNAL: {symbol} {direction} @ ${price:,.4f} | RSI={rsi_real:.1f}")
                candle_time = s["candle_time"] or DEFAULT_PARAMS["candle_time"]
                cursor.execute("""
                    INSERT INTO active_trades
                        (broker_product_id, broker_name, symbol, direction,
                         candle_time, entry_price, entry_time, last_price, status)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, 'OPEN')
                """, (s["product_id"], broker, symbol, direction, candle_time, price, price))
                trade_id = cursor.lastrowid
                cursor.execute("""
                    UPDATE strategy_params SET active_order_id=%s, entry_price=%s,
                    entry_time=NOW(), peak_profit=-999.00 WHERE id=%s
                """, (trade_id, price, s["id"]))
                log(f"  ✅ OPENED: {symbol} {direction} @ ${price:,.4f} | trade_id={trade_id}")
            except Exception as e:
                log(f"  ❌ Entry error ({s.get('symbol','?')}): {e}")
                continue
    except Exception as e:
        log(f"❌ check_and_execute_signals error: {e}")
    finally:
        cursor.close()
        conn.close()

def monitor_and_exit_trades():
    """Monitor all open trades and execute exits."""
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # Read directly from active_trades — single source of truth
        cursor.execute("""
            SELECT at.id, at.symbol, at.direction, at.entry_price,
                   at.entry_time, at.broker_name, at.candle_time, at.peak_profit
            FROM active_trades at
            WHERE at.status = 'OPEN'
              AND at.entry_price IS NOT NULL AND at.entry_price > 0
        """)
        open_trades = cursor.fetchall()
        if not open_trades:
            return
        log(f"  👁️ Monitoring {len(open_trades)} open trade(s)")
        for trade in open_trades:
            cursor.execute("""
                SELECT sp.* FROM strategy_params sp
                JOIN broker_products bp ON sp.broker_product_id = bp.id
                WHERE bp.local_ticker = %s AND sp.direction = %s AND sp.active = 1
                ORDER BY sp.pl_pct DESC LIMIT 1
            """, (trade['symbol'], trade['direction']))
            sp = cursor.fetchone() or {}

            s = {
                'id': sp.get('id'),
                'symbol': trade['symbol'],
                'direction': trade['direction'],
                'entry_price': float(trade['entry_price']),
                'entry_time': trade['entry_time'],
                'peak_profit': float(trade.get('peak_profit') or -999),
                'active_order_id': trade['id'],
                'broker_name': trade.get('broker_name', 'Gemini'),
                'candle_time': trade.get('candle_time') or '1h',
                'rsi_real': float(sp.get('rsi_real') or 50),
                'stop_loss': float(sp.get('stop_loss') or DEFAULT_PARAMS['stop_loss']),
                'trailing_start': float(sp.get('trailing_start') or DEFAULT_PARAMS['trailing_start']),
                'trailing_drop': float(sp.get('trailing_drop') or DEFAULT_PARAMS['trailing_drop']),
                'rsi_exit': float(sp.get('rsi_exit') or DEFAULT_PARAMS['rsi_exit']),
                'init_profit': float(sp.get('init_profit') or DEFAULT_PARAMS['init_profit']),
                'decay_start': float(sp.get('decay_start') or DEFAULT_PARAMS['decay_start']),
                'decay_rate': float(sp.get('decay_rate') or DEFAULT_PARAMS['decay_rate']),
            }
            try:
                symbol = s['symbol']
                direction = s['direction']
                entry_price = float(s['entry_price'])

                # Get fresh price
                current_price, age = get_live_price_from_db(symbol)
                if current_price <= 0:
                    log(f"  ⏭️ {symbol}: no price")
                    continue

                # Calculate raw P&L
                if direction == 'LONG':
                    pnl = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl = ((entry_price - current_price) / entry_price) * 100

                # ── RULE 0: Sanity check ───────────────────
                if abs(pnl) > SANITY_MAX_PNL:
                    log(f"  🚫 SANITY: {symbol} {direction} pnl={pnl:+.2f}% — phantom loss? Skipping")
                    continue

                # Calculate duration
                entry_time = s.get("entry_time") or s.get("at_entry_time")
                if entry_time:
                    if isinstance(entry_time, str):
                        entry_dt = datetime.strptime(entry_time, '%Y-%m-%d %H:%M:%S')
                    else:
                        entry_dt = entry_time
                    duration_seconds = (datetime.now() - entry_dt).total_seconds()
                    hours = duration_seconds / 3600
                else:
                    duration_seconds = 0
                    hours = 0

                # Update peak profit
                peak = float(s.get('peak_profit') or -999)
                if pnl > peak:
                    peak = pnl
                    cursor.execute(
                        "UPDATE strategy_params SET peak_profit = %s WHERE id = %s",
                        (peak, s['id'])
                    )

                # Get exit params
                stop_loss      = float(s.get('stop_loss')       or DEFAULT_PARAMS['stop_loss'])
                rsi_exit_thr   = float(s.get('rsi_exit')        or DEFAULT_PARAMS['rsi_exit'])
                trail_start    = float(s.get('trailing_start')   or DEFAULT_PARAMS['trailing_start'])
                trail_drop     = float(s.get('trailing_drop')    or DEFAULT_PARAMS['trailing_drop'])
                init_profit    = float(s.get('init_profit')      or DEFAULT_PARAMS['init_profit'])
                decay_start    = float(s.get('decay_start')      or DEFAULT_PARAMS['decay_start'])
                decay_rate     = float(s.get('decay_rate')       or DEFAULT_PARAMS['decay_rate'])
                rsi_current    = float(s.get('rsi_real')         or 50.0)

                # Decayed profit gate
                if hours > decay_start:
                    gate = max(0, init_profit - ((hours - decay_start) * decay_rate))
                else:
                    gate = init_profit

                log(f"  👁️  {symbol} {direction} | "
                    f"P&L:{pnl:+.2f}% | Peak:{peak:.2f}% | Gate:{gate:.2f}% | "
                    f"RSI:{rsi_current:.1f} | {hours:.1f}h | {duration_seconds:.0f}s")

                exit_reason = None

                # ── RULE 1: STOP LOSS (only after 300s) ───
                if pnl <= -stop_loss:
                    if duration_seconds >= MIN_TRADE_SECONDS:
                        exit_reason = f"STOP (pnl={pnl:+.2f}%, limit=-{stop_loss}%)"
                    else:
                        log(f"  ⏳ STOP suppressed: only {duration_seconds:.0f}s old (need {MIN_TRADE_SECONDS}s)")

                # ── RULE 2: TRAILING STOP (only after 300s) ─
                if peak >= trail_start:
                    trail_level = peak * 0.90  # 10% of peak
                    if pnl <= trail_level and trail_level > 0:
                        if duration_seconds >= MIN_TRADE_SECONDS:
                            exit_reason = f"TRAIL (peak={peak:.2f}%, trail={trail_level:.2f}%)"
                        else:
                            log(f"  ⏳ TRAIL suppressed: only {duration_seconds:.0f}s old")

                # ── RULE 3: RSI EXIT ───────────────────────
                elif pnl >= gate and gate > 0:
                    if direction == 'LONG' and rsi_current >= rsi_exit_thr:
                        exit_reason = f"RSI-EXIT (RSI={rsi_current:.1f} >= {rsi_exit_thr})"
                    elif direction == 'SHORT' and rsi_current <= (100 - rsi_exit_thr):
                        exit_reason = f"RSI-EXIT (RSI={rsi_current:.1f} <= {100 - rsi_exit_thr:.1f})"

                # ── RULE 4: DECAY GATE ─────────────────────
                if not exit_reason and hours > decay_start and pnl > 0 and pnl >= gate:
                    exit_reason = f"DECAY (pnl={pnl:+.2f}%, gate={gate:.2f}%, {hours:.1f}h)"

                # ── RULE 5: TIME-STOP ──────────────────────
                if not exit_reason and hours >= TIME_STOP_HOURS and pnl < TIME_STOP_MIN_PNL:
                    exit_reason = f"TIME-STOP ({hours:.1f}h, pnl={pnl:+.2f}%)"

                # ── Execute exit ───────────────────────────
                if exit_reason:
                    _close_trade(cursor, s, current_price, pnl, duration_seconds, exit_reason)
                    apply_exit_cooldown(symbol, direction, exit_reason)

            except Exception as e:
                log(f"  ❌ Exit error ({s.get('symbol','?')}): {e}")
                continue

    except Exception as e:
        log(f"❌ monitor_and_exit_trades error: {e}")
    finally:
        cursor.close()
        conn.close()

# ── Close trade ───────────────────────────────────────────────
def _close_trade(cursor, s, current_price, pnl, duration_seconds, exit_reason):
    """Save closed trade to orders and clear active_order_id in strategy_params"""
    strategy_id = s['id']
    symbol      = s['symbol']
    direction   = s['direction']
    broker      = s['broker_name']
    entry_price = float(s['entry_price'])
    candle_time = s.get('candle_time') or '1h'

    try:
        # Save to orders
        cursor.execute("""
            INSERT INTO orders
                (strategy_id, symbol, broker, side, candle_time,
                 entry_price, exit_price, pnl_percent, duration_seconds,
                 status, exit_reason, exit_time, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'CLOSED', %s, NOW(), NOW())
        """, (
            strategy_id, symbol, broker, direction, candle_time,
            entry_price, current_price, round(pnl, 4), int(duration_seconds),
            exit_reason
        ))

        # Also update active_trades if table exists
        try:
            cursor.execute("""
                UPDATE active_trades
                SET status = 'CLOSED', exit_price = %s, exit_time = NOW(),
                    pnl_percent = %s, exit_reason = %s
                WHERE id = %s
            """, (current_price, round(pnl, 4), exit_reason, s['active_order_id']))
        except Exception as e:
            log(f'  ⚠️ active_trades update error: {e}')

        # Clear strategy_params active state
        cursor.execute("""
            UPDATE strategy_params
            SET active_order_id = NULL,
                entry_price     = NULL,
                entry_time      = NULL,
                peak_profit     = -999.00
            WHERE id = %s
        """, (strategy_id,))

        log(f"  🚪 EXIT: {symbol} {direction} @ ${current_price:.4f} | "
            f"{exit_reason} | P&L: {pnl:+.2f}% | {duration_seconds:.0f}s")

    except Exception as e:
        log(f"  ❌ _close_trade error ({symbol}): {e}")

# ══════════════════════════════════════════════════════════════
# STANDALONE TEST
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 65)
    print("AiMN V3.1 — AUTO EXECUTOR (standalone mode)")
    print("=" * 65)
    print(f"MIN_TRADE_SECONDS : {MIN_TRADE_SECONDS}s (STOP/TRAIL suppressed before this)")
    print(f"SANITY_MAX_PNL    : {SANITY_MAX_PNL}% (phantom loss guard)")
    print(f"TIME_STOP_HOURS   : {TIME_STOP_HOURS}h at pnl < {TIME_STOP_MIN_PNL}%")
    print(f"STOP_COOLDOWN     : {STOP_COOLDOWN_MINUTES}min both directions")
    print(f"TRAIL_COOLDOWN    : {TRAIL_COOLDOWN_MINUTES}min same direction only")
    print("=" * 65)
    while True:
        try:
            check_volume_signals()
            check_and_execute_signals()
            monitor_and_exit_trades()
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n⛔ Stopped")
            break
        except Exception as e:
            log(f"🔥 ERROR: {e}")
            time.sleep(5)