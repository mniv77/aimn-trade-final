# auto_executor.py - AiMN V3.1
# FIXED: Reads all params from strategy_params (not broker_products)
# FIXED: RSI entry filter added
# FIXED: RSI exit added
# FIXED: Trail exit bug fixed (no gate check)
# FIXED: Hardcoded params replaced with tuned values per symbol/direction
# ═══════════════════════════════════════════════════════════

import mysql.connector
import time
from datetime import datetime
import db_config as config

# ── Fallback defaults (only if strategy_params missing) ─────
DEFAULT_STOP_LOSS    = 2.0
DEFAULT_TRAIL_START  = 2.0
DEFAULT_TRAIL_DROP   = 0.5
DEFAULT_INIT_PROFIT  = 1.5
DEFAULT_DECAY_START  = 1.0
DEFAULT_DECAY_RATE   = 0.5
DEFAULT_RSI_ENTRY    = 35.0
DEFAULT_RSI_EXIT     = 70.0

def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True
    )

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ═══════════════════════════════════════════════════════════
# LOAD STRATEGY PARAMS — reads tuned values from strategy_params
# ═══════════════════════════════════════════════════════════
def load_strategies(cursor):
    """
    Load all active strategies with their tuned parameters.
    Returns list of dicts — one per symbol/direction/timeframe.
    """
    cursor.execute("""
        SELECT
            sp.id            as strategy_id,
            sp.direction,
            sp.candle_time,
            sp.rsi_len,
            sp.rsi_entry,
            sp.rsi_exit,
            sp.stop_loss,
            sp.trailing_start,
            sp.trailing_drop,
            sp.init_profit,
            sp.decay_start,
            sp.decay_rate,
            sp.rsi_real,
            sp.macd,
            sp.active,
            bp.id            as product_id,
            bp.local_ticker  as symbol,
            bp.last_price,
            b.name           as broker_name
        FROM strategy_params sp
        JOIN broker_products bp ON sp.broker_product_id = bp.id
        JOIN brokers b          ON bp.broker_id = b.id
        WHERE sp.active = 1
          AND bp.is_active = 1
        ORDER BY bp.local_ticker, sp.direction, sp.candle_time
    """)
    return cursor.fetchall()


# ═══════════════════════════════════════════════════════════
# ENTRY ENGINE
# Checks RSI + MACD signals from strategy_params
# One open trade per broker at a time
# ═══════════════════════════════════════════════════════════
def check_and_execute_signals():
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # Find brokers with open trades
        cursor.execute("""
            SELECT DISTINCT broker_name FROM active_trades
            WHERE status = 'OPEN'
        """)
        locked_brokers = {r['broker_name'] for r in cursor.fetchall()}

        # Find symbols with open trades (no duplicate symbol)
        # Find symbols with open trades OR recently closed (30 min cooldown)
        cursor.execute("""
            SELECT DISTINCT CONCAT(symbol, '_', direction) as symbol_dir FROM active_trades
            WHERE status = 'OPEN'
               OR (status = 'CLOSED' AND exit_time > DATE_SUB(NOW(), INTERVAL 30 MINUTE)
                   AND exit_reason NOT LIKE '%PANIC%')
        """)
        locked_symbols = {r['symbol_dir'] for r in cursor.fetchall()}
        
        # Load all active strategies with tuned params
        strategies = load_strategies(cursor)

        for s in strategies:
            broker     = s['broker_name']
            symbol     = s['symbol']
            direction  = s['direction']
            product_id = s['product_id']
            price      = float(s['last_price'] or 0)

            # Read RSI and MACD from strategy_params (written by calculate_indicators)
            rsi_real   = float(s['rsi_real'] or 50.0)
            macd_val   = float(s['macd']     or 0.0)

            # Tuned entry params
            rsi_entry  = float(s['rsi_entry'] or DEFAULT_RSI_ENTRY)

            if price <= 0:
                continue

            # Skip if market is closed for this broker
            if broker.upper() in ('ALPACA', 'ALPACA-ETF', 'WEBULL'):
                from datetime import datetime
                import pytz
                et = pytz.timezone('US/Eastern')
                now_et = datetime.now(et)
                market_open = now_et.weekday() < 5 and \
                              now_et.hour * 60 + now_et.minute >= 570 and \
                              now_et.hour * 60 + now_et.minute < 960
                if not market_open:
                    continue

            # Skip if broker or symbol already has open trade
            if broker in locked_brokers:
                continue
            if f"{symbol}_{direction}" in locked_symbols:
                continue
            # ── ENTRY CONDITIONS ─────────────────────────
            # Match exactly what the tuner backtests:
            # LONG:  RSI Real <= rsi_entry  AND  MACD > 0
            # SHORT: RSI Real >= (100 - rsi_entry)  AND  MACD < 0

            if direction == 'LONG':
                rsi_signal  = rsi_real <= rsi_entry
                macd_signal = macd_val > 0
            else:  # SHORT
                rsi_signal  = rsi_real >= (100 - rsi_entry)
                macd_signal = macd_val < 0

            if rsi_signal and macd_signal:
                log(f"🚀 SIGNAL: {symbol} {direction} @ ${price:,.2f} | "
                    f"RSI={rsi_real:.1f} (threshold={rsi_entry:.1f}) | "
                    f"MACD={macd_val:.4f}")

                # Open trade in active_trades
                cursor.execute("""
                    INSERT INTO active_trades
                    (broker_product_id, broker_name, symbol, direction,
                     entry_price, entry_time, last_price, peak_profit,
                     status, strategy_id)
                    VALUES (%s, %s, %s, %s, %s, NOW(), %s, -999.0, 'OPEN', %s)
                """, (product_id, broker, symbol, direction,
                      price, price, s['strategy_id']))

                log(f"✅ Trade opened: {symbol} {direction} @ ${price:,.2f} "
                    f"[strategy_id={s['strategy_id']}]")

                # Lock broker and symbol
                locked_brokers.add(broker)
                locked_symbols.add(symbol)

    except Exception as e:
        log(f"❌ Entry error: {e}")
    finally:
        cursor.close()
        conn.close()


# ═══════════════════════════════════════════════════════════
# EXIT ENGINE
# Monitors active_trades using TUNED params from strategy_params
# Exit rules (matching backtest exactly):
#   1. Stop Loss     — always active
#   2. Trail Exit    — no gate check (fixed bug)
#   3. RSI Exit      — when RSI crosses exit threshold + profit >= gate
#   4. Decay Exit    — after decay_start hours, gate decays to 0
# ═══════════════════════════════════════════════════════════
def monitor_and_exit_trades():
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        # Get all open trades with their strategy params
        cursor.execute("""
            SELECT
                at.*,
                sp.stop_loss,
                sp.trailing_start,
                sp.trailing_drop,
                sp.init_profit,
                sp.decay_start,
                sp.decay_rate,
                sp.rsi_exit,
                sp.rsi_real,
                sp.candle_time
            FROM active_trades at
            LEFT JOIN strategy_params sp ON at.strategy_id = sp.id
            WHERE at.status = 'OPEN'
        """)
        trades = cursor.fetchall()

        if not trades:
            return

        for trade in trades:
            try:
                trade_id      = trade['id']
                symbol        = trade['symbol']
                direction     = trade['direction']
                entry_price   = float(trade['entry_price']  or 0)
                current_price = float(trade['last_price']   or 0)
                entry_time    = trade['entry_time']

                if entry_price <= 0 or current_price <= 0:
                    continue

                # ── Load tuned params (fallback to defaults if no strategy) ──
                stop_loss    = float(trade['stop_loss']      or DEFAULT_STOP_LOSS)
                trail_start  = float(trade['trailing_start'] or DEFAULT_TRAIL_START)
                trail_drop   = float(trade['trailing_drop']  or DEFAULT_TRAIL_DROP)
                init_profit  = float(trade['init_profit']    or DEFAULT_INIT_PROFIT)
                decay_start  = float(trade['decay_start']    or DEFAULT_DECAY_START)
                decay_rate   = float(trade['decay_rate']     or DEFAULT_DECAY_RATE)
                rsi_exit     = float(trade['rsi_exit']       or DEFAULT_RSI_EXIT)
                rsi_real     = float(trade['rsi_real']       or 50.0)

                # ── Calculate P&L ──────────────────────────
                if direction == 'LONG':
                    pnl = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl = ((entry_price - current_price) / entry_price) * 100
                    
               # ── SANITY CHECK — reject bad price data ───
                if abs(pnl) > 20:
                    log(f"  ⚠️  SANITY CHECK FAILED: {symbol} P&L={pnl:.2f}% — likely bad price data, skipping")
                    continue 

                # ── Duration ───────────────────────────────
                duration_seconds = (datetime.now() - entry_time).total_seconds() if entry_time else 0
                duration_hours   = duration_seconds / 3600.0

                # ── Current Gate with decay ────────────────
                if duration_hours >= decay_start:
                    decay_amount = (duration_hours - decay_start) * decay_rate
                    current_gate = max(0.0, init_profit - decay_amount)
                else:
                    current_gate = init_profit

                # ── Peak profit tracking ───────────────────
                peak_profit = float(trade['peak_profit'] or -999.0)
                if pnl > peak_profit:
                    peak_profit = pnl
                    cursor.execute(
                        "UPDATE active_trades SET peak_profit=%s WHERE id=%s",
                        (peak_profit, trade_id)
                    )

                # ── Log every cycle ────────────────────────
                dur_str = f"{int(duration_hours)}h{int((duration_hours%1)*60)}m"
                log(f"  👁  {symbol} {direction} | "
                    f"P&L:{pnl:+.2f}% | Peak:{peak_profit:.2f}% | "
                    f"Gate:{current_gate:.2f}% | RSI:{rsi_real:.1f} | "
                    f"Dur:{dur_str}")

                # ══ EXIT LOGIC — matches backtest exactly ══
                exit_reason = None

                # ── RULE 1: STOP LOSS — always active ──────
                if pnl <= -stop_loss:
                    exit_reason = "STOP"
                    log(f"  🛑 STOP LOSS: {symbol} | P&L:{pnl:.2f}%")

                # ── RULE 2: TRAIL EXIT — NO gate check ─────
                # Trail catches sudden moves — fires whenever
                # peak drops by trail_drop regardless of gate
                elif peak_profit >= trail_start:
                    trail_level = peak_profit - trail_drop
                    if pnl <= trail_level:
                        exit_reason = "TRAIL-EXIT"
                        log(f"  📉 TRAIL EXIT: {symbol} | "
                            f"Peak:{peak_profit:.2f}% → Now:{pnl:.2f}% "
                            f"(trail={trail_level:.2f}%)")

                # ── RULE 3: RSI EXIT ────────────────────────
                # Exit when RSI crosses exit threshold
                # AND current profit >= current gate
                if not exit_reason:
                    if direction == 'LONG' and rsi_real >= rsi_exit and pnl >= current_gate:
                        exit_reason = "RSI-EXIT"
                        log(f"  📊 RSI EXIT: {symbol} LONG | "
                            f"RSI:{rsi_real:.1f} >= {rsi_exit:.1f} | "
                            f"P&L:{pnl:.2f}% >= Gate:{current_gate:.2f}%")
                    elif direction == 'SHORT' and rsi_real <= (100 - rsi_exit) and pnl >= current_gate:
                        exit_reason = "RSI-EXIT"
                        log(f"  📊 RSI EXIT: {symbol} SHORT | "
                            f"RSI:{rsi_real:.1f} <= {100-rsi_exit:.1f} | "
                            f"P&L:{pnl:.2f}% >= Gate:{current_gate:.2f}%")

                # ── RULE 4: DECAY EXIT ──────────────────────
                # After decay_start hours, gate decays toward 0
                # Exit when current profit >= decayed gate
                if not exit_reason and duration_hours >= decay_start:
                    if pnl >= current_gate:
                        exit_reason = "DECAY-EXIT"
                        log(f"  ⏰ DECAY EXIT: {symbol} | "
                            f"P&L:{pnl:.2f}% >= Gate:{current_gate:.2f}% "
                            f"after {duration_hours:.1f}h")

                # ── EXECUTE EXIT ───────────────────────────
                if exit_reason:
                    # Save to orders table
                    cursor.execute("""
                        INSERT INTO orders (
                            strategy_id, symbol, broker, side, candle_time,
                            entry_price, exit_price, pnl_percent,
                            duration_seconds, status, exit_reason,
                            created_at
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                    """, (
                        trade.get('strategy_id'),
                        symbol,
                        trade['broker_name'],
                        direction,
                        trade.get('candle_time', '1hr'),
                        entry_price,
                        current_price,
                        round(pnl, 4),
                        int(duration_seconds),
                        'CLOSED',
                        exit_reason,
                    ))

                    # Close the active trade
                    cursor.execute("""
                        UPDATE active_trades
                        SET status      = 'CLOSED',
                            exit_price  = %s,
                            exit_time   = NOW(),
                            exit_reason = %s
                        WHERE id = %s
                    """, (current_price, exit_reason, trade_id))

                    log(f"  ✅ CLOSED: {symbol} {direction} | "
                        f"{exit_reason} | P&L:{pnl:+.2f}% | "
                        f"Entry:${entry_price:,.2f} Exit:${current_price:,.2f} | "
                        f"{dur_str}")

            except Exception as e:
                import traceback
                log(f"  ❌ Error trade #{trade.get('id','?')}: {e}")
                log(f"  TRACEBACK: {traceback.format_exc()}")
                continue

    except Exception as e:
        log(f"❌ Monitor error: {e}")
    finally:
        cursor.close()
        conn.close()


# ═══════════════════════════════════════════════════════════
# STANDALONE — for testing outside aimn_engine.py
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("AiMN V3.1 - AUTO EXECUTOR (Fixed)")
    print("=" * 60)
    print("✅ Reads params from strategy_params (tuned values)")
    print("✅ RSI entry filter: RSI Real + MACD sign")
    print("✅ RSI exit: fires when RSI crosses threshold + profit >= gate")
    print("✅ Trail exit: no gate check (catches sudden moves)")
    print("✅ Decay exit: after decay_start hours")
    print("=" * 60)
    cycle = 0
    while True:
        try:
            cycle += 1
            check_and_execute_signals()
            monitor_and_exit_trades()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n⛔ Stopped")
            break
        except Exception as e:
            log(f"🔥 ERROR: {e}")
            time.sleep(5)