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
            bp.price_prev1,
            bp.price_prev2,
            bp.price_prev3,
            bp.price_updated_at,
            sp.candle_prev1,
            sp.candle_prev2,
            sp.candle_prev3,
            sp.candle_prev4,
            sp.trend_bars,
            b.name         AS broker_name
        FROM strategy_params sp
        JOIN broker_products bp ON sp.broker_product_id = bp.id
        LEFT JOIN active_trades at ON at.id = sp.active_order_id AND at.status = 'OPEN'
        JOIN brokers b          ON bp.broker_id = b.id
        WHERE sp.active = 1
          AND bp.is_active = 1
          AND b.trading_enabled = 1
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
                # ── Higher Timeframe Trend Check ──────────────
                try:
                    import requests as _req
                    _clean = symbol.replace("/", "").lower()
                    _r = _req.get(f"https://api.gemini.com/v2/candles/{_clean}/1hr", timeout=5)
                    if _r.status_code == 200:
                        _candles = sorted(_r.json(), key=lambda x: x[0])
                        if len(_candles) >= 2:
                            _last = _candles[-1]
                            _open, _close = float(_last[1]), float(_last[4])

                            rsi_check = float(s.get("rsi_real") or 50.0)
                            if direction == "LONG" and _close <= _open and rsi_check > 20:
                                log(f"  HTF BLOCK: {symbol} 1hr bearish - skip LONG")
                                continue
                            if direction == "SHORT" and _close >= _open and rsi_check < 80:
                                log(f"  HTF BLOCK: {symbol} 1hr bullish - skip SHORT")
                                continue

                except Exception:
                    pass

                rsi_real      = float(s["rsi_real"]   or 50.0)
                rsi_prev_val  = float(s["rsi_prev"]   or 50.0)
                macd_val      = float(s["macd"]        or 0.0)
                macd_prev_val = float(s["macd_prev"]   or 0.0)
                rsi_entry     = float(s["rsi_entry"]   or DEFAULT_PARAMS["rsi_entry"])
                if direction == "LONG":
                    rsi_signal    = rsi_real <= rsi_entry
                    rsi_bouncing  = rsi_real > rsi_prev_val
                    macd_rising   = macd_val > macd_prev_val or macd_prev_val == 0.0
                    rsi_extreme   = rsi_real <= 20
                    macd_signal   = macd_rising or rsi_extreme
                    bounce_signal = rsi_bouncing or rsi_extreme
                    trend_ok      = macd_val > 0 or rsi_extreme or (symbol == "NVDA" and rsi_real <= 15)
                else:
                    rsi_signal    = rsi_real >= (100 - rsi_entry)
                    rsi_bouncing  = rsi_real < rsi_prev_val
                    macd_falling  = macd_val < macd_prev_val or macd_prev_val == 0.0
                    rsi_extreme   = rsi_real >= 80
                    macd_signal   = macd_falling or rsi_extreme
                    bounce_signal = rsi_bouncing or rsi_extreme
                    trend_ok      = macd_val < 0 or rsi_extreme
                if not trend_ok:
                    log(f"  🚫 TREND BLOCK: {symbol} {direction} MACD={macd_val:.4f} — skip")
                    continue
                # ── PULLBACK FILTER: never enter at peak ──────
                price_prev1 = float(s.get("price_prev1") or price)
                price_prev2 = float(s.get("price_prev2") or price)
                price_prev3 = float(s.get("price_prev3") or price)
                cp1 = float(s.get("candle_prev1") or price_prev1)
                cp2 = float(s.get("candle_prev2") or price_prev2)
                cp3 = float(s.get("candle_prev3") or price_prev3)
                cp4 = float(s.get("candle_prev4") or price_prev3)
                recent_high = max(price, cp1, cp2, cp3)
                recent_low  = min(price, cp1, cp2, cp3)
                # ── TREND STATE (NVDA/TSLA) ───────────────────
                prices = [price_prev3, price_prev2, price_prev1, price]
                ups = sum(1 for j in range(1,4) if prices[j]>prices[j-1])
                trend_state = "CLIMBING" if ups>=3 else ("DESCENDING" if ups<=1 else "SIDEWAYS")
                # ── ACTIVITY FILTER: skip flat/sideways moves ──
                if symbol in ("NVDA", "TSLA"):
                    price_range = recent_high - recent_low
                    activity_pct = price_range / price * 100 if price > 0 else 0
                    is_active = activity_pct >= 0.30  # must have moved 0.30%+ in last 4 bars
                    if not is_active:
                        log(f"  💤 FLAT BLOCK: {symbol} {direction} range={activity_pct:.2f}% — skip")
                        continue
                if direction == "LONG":
                    # Price must be at least 0.2% below recent high (not entering at peak)
                    pullback_ok = price <= recent_high * 0.998
                    # V-BOTTOM: rapid drop then recovery
                    # price_prev3 was high, price_prev1 was the low, now recovering
                    drop_pct   = (cp3 - cp1) / cp3 * 100 if cp3 > 0 else 0
                    vb_threshold = 0.5 if symbol in ('NVDA', 'TSLA', 'LINK/USD') else 0.3
                    rapid_drop = drop_pct >= vb_threshold
                    recovering = price > cp1
                    true_bottom = cp1 < cp2 < cp3
                    # For NVDA: only enter LONG when trend was DESCENDING (real V-bottom)
                    state_ok = (trend_state == "DESCENDING") if symbol == "NVDA" else True
                    # V-Score: major V filter for NVDA
                    if symbol == "NVDA":
                        prices_list = [price_prev3, price_prev2, price_prev1, price]
                        bottom = min(prices_list)
                        drop_pct2 = (price_prev3 - bottom) / price_prev3 * 100 if price_prev3 > 0 else 0
                        down_bars2 = sum(1 for j in range(1,4) if prices_list[j] < prices_list[j-1])
                        two_bar_rec = price > price_prev1 > price_prev2
                        trend_b = int(s.get("trend_bars") or 0)
                        trend_bonus = min(20, trend_b * 3)  # up to 20 pts for 6+ bars trend
                        v_score = min(100, drop_pct2*15 + down_bars2*6 + max(0,(20-rsi_real)*0.75) + (10 if two_bar_rec else 0) + trend_bonus)
                        log(f"  📊 V-SCORE: {symbol} {direction} score={v_score:.0f} trend={trend_b}bars")
                        log(f"  📊 V-SCORE: {symbol} {direction} score={v_score:.0f}")
                        state_ok = state_ok and v_score >= 50
                    v_bottom   = rapid_drop and recovering and true_bottom and state_ok
                else:
                    # Price must be at least 0.2% above recent low (not entering at bottom)
                    pullback_ok = price >= recent_low * 1.002
                    # V-TOP: rapid rise then reversal
                    # price_prev3 was low, price_prev1 was the high, now dropping
                    rise_pct   = (cp1 - cp3) / cp3 * 100 if cp3 > 0 else 0
                    vb_threshold = 0.5 if symbol in ('NVDA', 'TSLA', 'LINK/USD') else 0.3
                    rapid_rise = rise_pct >= vb_threshold
                    reversing  = price < cp1
                    true_top   = cp1 > cp2 > cp3
                    # For NVDA: only enter SHORT when trend was CLIMBING (real V-top)
                    state_ok = (trend_state == "CLIMBING") if symbol == "NVDA" else True
                    v_bottom   = rapid_rise and reversing and true_top and state_ok

                # V-bottom gives extra confidence - can relax MACD requirement
                if v_bottom and rsi_signal and bounce_signal and pullback_ok:
                    log(f"  🎯 V-BOTTOM: {symbol} {direction} rapid reversal detected!")
                elif not (rsi_signal and macd_signal and bounce_signal and pullback_ok):
                    if not pullback_ok:
                        log(f"  ⛔ PEAK BLOCK: {symbol} {direction} price at peak/low - skip")
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
                # ── NVDA Trade Logger ─────────────────────────
                if symbol == "NVDA":
                    with open("/home/MeirNiv/aimn-trade-final/nvda_trades.log", "a") as f:
                        from datetime import datetime as dt
                        v_scr = int(s.get("v_score") or 0)
                        f.write(f"{dt.utcnow().strftime('%Y-%m-%d %H:%M')} | ENTRY | {direction} | ${price:.2f} | RSI={rsi_real:.1f} | MACD={macd_val:.4f}\n")
                candle_time = s["candle_time"] or DEFAULT_PARAMS["candle_time"]
                cursor.execute("""
                    INSERT INTO active_trades
                        (broker_product_id, broker_name, symbol, direction,
                         candle_time, entry_price, entry_time, last_price, status,
                         stop_loss, trailing_start, init_profit, decay_start, decay_rate, rsi_exit,
                         strategy_id)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, 'OPEN',
                            %s, %s, %s, %s, %s, %s, %s)
                """, (s["product_id"], broker, symbol, direction, candle_time, price, price,                        float(s.get("stop_loss") or DEFAULT_PARAMS["stop_loss"]),
                        float(s.get("trailing_start") or DEFAULT_PARAMS["trailing_start"]),
                        float(s.get("init_profit") or DEFAULT_PARAMS["init_profit"]),
                        float(s.get("decay_start") or DEFAULT_PARAMS["decay_start"]),
                        float(s.get("decay_rate") or DEFAULT_PARAMS["decay_rate"]),
                        float(s.get("rsi_exit") or DEFAULT_PARAMS["rsi_exit"]),
                        s["id"]))

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
                WHERE sp.active_order_id = %s
                LIMIT 1
            """, (trade['id'],))
            sp = cursor.fetchone()
            if not sp:
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
                'stop_loss': float(trade.get('stop_loss') or sp.get('stop_loss') or DEFAULT_PARAMS['stop_loss']),
                'trailing_start': float(trade.get('trailing_start') or sp.get('trailing_start') or DEFAULT_PARAMS['trailing_start']),
                'trailing_drop': float(sp.get('trailing_drop') or DEFAULT_PARAMS['trailing_drop']),
                'rsi_exit': float(trade.get('rsi_exit') or sp.get('rsi_exit') or DEFAULT_PARAMS['rsi_exit']),
                'init_profit': float(trade.get('init_profit') or sp.get('init_profit') or DEFAULT_PARAMS['init_profit']),
                'decay_start': float(trade.get('decay_start') or sp.get('decay_start') or DEFAULT_PARAMS['decay_start']),
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
                        "UPDATE active_trades SET peak_profit = %s WHERE id = %s",
                        (peak, s['active_order_id'])
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

                # ── RULE 2: TRAILING STOP (two-phase) ─────
                if peak >= trail_start:
                    # Phase 1: small profit — give 15% room
                    # NVDA special: very tight until 0.3% then loose to ride major V
                    if symbol == "NVDA":
                        if peak < 0.3:
                            trail_level = peak * 0.70  # very tight — filter minor V
                        else:
                            trail_level = peak * 0.85  # loose — ride the major V!
                    elif peak < 1.0:
                        trail_level = peak * 0.85
                    # Phase 2: larger profit — tighten to 10%
                    else:
                        trail_level = peak * 0.90
                    # Break-even floor — trail never below entry
                    if trail_level < 0:
                        trail_level = 0.0  # minimum break-even
                    if pnl <= trail_level and trail_level >= 0:
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
        # Guard: check if trade already closed to prevent duplicate exits
        cursor.execute("SELECT id FROM active_trades WHERE id=%s AND status='OPEN'", (s['active_order_id'],))
        if not cursor.fetchone():
            log(f'  ⚠️ DUPLICATE EXIT BLOCKED: {symbol} trade already closed')
            return
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
        # ── NVDA Trade Logger ─────────────────────────
        if symbol == "NVDA":
            with open("/home/MeirNiv/aimn-trade-final/nvda_trades.log", "a") as f:
                from datetime import datetime as dt
                dur_str = f"{int(duration_seconds//3600)}h{int((duration_seconds%3600)//60)}m"
                f.write(f"{dt.utcnow().strftime('%Y-%m-%d %H:%M')} | EXIT  | {direction} | ${current_price:.2f} | {pnl:+.2f}% | {exit_reason} | {dur_str}\n")

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