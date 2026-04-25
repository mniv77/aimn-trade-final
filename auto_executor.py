# auto_executor.py - AiMN V3.1 Simple Machine Strategy
# Reads signals from broker_products (not strategy_params)
# Tracks open trades in active_trades table
# ═══════════════════════════════════════════════════════════
import mysql.connector
import time
from datetime import datetime
import db_config as config

# ── FIXED STRATEGY PARAMETERS — same for ALL symbols ───────
STOP_LOSS     = 2.0    # Exit if loss >= 2.0%
TRAIL_START   = 2.0    # Trailing activates when peak >= 2%
TRAIL_DROP    = 0.5    # Exit when drops 0.5% from peak
INIT_PROFIT   = 1.5    # Gate starts at 1.5%
DECAY_START   = 1.0    # Decay begins after 1 hour
DECAY_RATE    = 0.5    # Gate drops 0.5% per hour
RSI_LONG_MAX  = 30.0   # LONG: RSI Real must be <= 30
RSI_SHORT_MIN = 70.0   # SHORT: RSI Real must be >= 70

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
# ENTRY ENGINE
# Reads from broker_products + last_price + rsi_real + macd
# One trade per broker at a time
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

        # Get all symbols with their latest indicators
        cursor.execute("""
            SELECT bp.id as product_id,
                   bp.local_ticker as symbol,
                   bp.last_price,
                   bp.rsi_real,
                   bp.macd,
                   b.name as broker_name,
                   ms.is_24_7
            FROM broker_products bp
            JOIN brokers b ON bp.broker_id = b.id
            LEFT JOIN market_sessions ms ON bp.session_id = ms.id
        """)
        products = cursor.fetchall()

        for p in products:
            broker     = p['broker_name']
            symbol     = p['symbol']
            product_id = p['product_id']
            price      = float(p['last_price'] or 0)
            rsi_real   = float(p['rsi_real']   or 50)
            macd_val   = float(p['macd']        or 0)

            if price <= 0:
                continue

            # Skip if broker already has open trade
            if broker in locked_brokers:
                continue

            # Check LONG and SHORT signals
            for direction in ['LONG', 'SHORT']:
                # ENTRY: MACD sign only — no RSI filter
                macd_ready = (direction == 'LONG'  and macd_val > 0) or \
                             (direction == 'SHORT' and macd_val < 0)

                if macd_ready:
                    log(f"🚀 SIGNAL: {symbol} {direction} @ ${price:,.2f} | "
                        f"RSI={rsi_real:.1f} | MACD={macd_val:.4f}")

                    # Open trade in active_trades
                    cursor.execute("""
                        INSERT INTO active_trades
                        (broker_product_id, broker_name, symbol, direction,
                         entry_price, entry_time, last_price, peak_profit, status)
                        VALUES (%s, %s, %s, %s, %s, NOW(), %s, -999.0, 'OPEN')
                    """, (product_id, broker, symbol, direction, price, price))

                    log(f"✅ Trade opened: {symbol} {direction} @ ${price:,.2f}")

                    # Lock this broker
                    locked_brokers.add(broker)
                    break  # only one direction per broker per cycle

    except Exception as e:
        log(f"❌ Entry error: {e}")
    finally:
        cursor.close()
        conn.close()


# ═══════════════════════════════════════════════════════════
# EXIT ENGINE
# Monitors active_trades
# Stop Loss → Trailing Stop → Decay Gate
# ═══════════════════════════════════════════════════════════
def monitor_and_exit_trades():
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM active_trades WHERE status = 'OPEN'
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

                # Calculate P&L
                if direction == 'LONG':
                    pnl = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl = ((entry_price - current_price) / entry_price) * 100

                # Duration
                duration_seconds = (datetime.now() - entry_time).total_seconds() if entry_time else 0
                duration_hours   = duration_seconds / 3600.0

                # Current Gate with decay
                if duration_hours > DECAY_START:
                    decay_amount = (duration_hours - DECAY_START) * DECAY_RATE
                    current_gate = max(0, INIT_PROFIT - decay_amount)
                else:
                    current_gate = INIT_PROFIT

                # Peak profit tracking
                peak_profit = float(trade['peak_profit'] or -999.0)
                if pnl > peak_profit:
                    peak_profit = pnl
                    cursor.execute(
                        "UPDATE active_trades SET peak_profit = %s WHERE id = %s",
                        (peak_profit, trade_id)
                    )

                # Log every cycle
                dur_str = f"{int(duration_hours)}h{int((duration_hours%1)*60)}m"
                log(f"  👁  {symbol} {direction} | P&L:{pnl:+.2f}% | "
                    f"Peak:{peak_profit:.2f}% | Gate:{current_gate:.2f}% | Dur:{dur_str}")

                # ── EXIT LOGIC ──────────────────────────────
                exit_reason = None

                # 1. STOP LOSS
                if pnl <= -STOP_LOSS:
                    exit_reason = "STOP"
                    log(f"  🛑 STOP: {symbol} {direction} | P&L:{pnl:.2f}%")

                # 2. TRAILING STOP
                elif peak_profit >= TRAIL_START and pnl <= (peak_profit - TRAIL_DROP):
                    if pnl >= current_gate:
                        exit_reason = "TRAIL-EXIT"
                        log(f"  📉 TRAIL: {symbol} | Peak:{peak_profit:.2f}% Now:{pnl:.2f}%")

                # 3. DECAY GATE = 0 — exit at any profit
                elif current_gate == 0 and pnl > 0:
                    exit_reason = "DECAY-EXIT"
                    log(f"  ⏰ DECAY EXIT: {symbol} | P&L:{pnl:.2f}%")

                # ── EXECUTE EXIT ─────────────────────────────
                if exit_reason:
                    # Save to orders table
                    cursor.execute("""
                        INSERT INTO orders (
                            strategy_id, symbol, broker, side, candle_time,
                            entry_price, exit_price, pnl_percent,
                            duration_seconds, status, exit_reason,
                            rsi_real_entry, entry_rsi_max, entry_rsi_min,
                            created_at
                        ) VALUES (NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                    """, (
                        symbol,
                        trade['broker_name'],
                        direction,
                        '1h',
                        entry_price,
                        current_price,
                        round(pnl, 4),
                        int(duration_seconds),
                        'CLOSED',
                        exit_reason,
                        float(trade.get('rsi_real') or 0),
                        0, 0
                    ))

                    # Close the trade
                    cursor.execute("""
                        UPDATE active_trades
                        SET status = 'CLOSED',
                            exit_price = %s,
                            exit_time = NOW(),
                            exit_reason = %s
                        WHERE id = %s
                    """, (current_price, exit_reason, trade_id))

                    conn.commit()
                    log(f"  ** CLOSED: {symbol} {direction} | "
                        f"{exit_reason} | P&L:{pnl:+.2f}% | "
                        f"Entry:${entry_price:,.2f} Exit:${current_price:,.2f} | {dur_str}")

            except Exception as e:
                import traceback
                log(f"  ERROR trade #{trade.get('id','?')}: {e}")
                log(f"  TRACEBACK: {traceback.format_exc()}")
                continue

    except Exception as e:
        log(f"❌ Monitor error: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("AiMN V3.1 - AUTO EXECUTOR (Simple Machine)")
    print("=" * 60)
    print(f"ENTRY:  MACD sign + RSI Real (<=30 LONG / >=70 SHORT)")
    print(f"EXIT:   Stop {STOP_LOSS}% | Trail {TRAIL_START}%/{TRAIL_DROP}% | Decay")
    print(f"TABLE:  active_trades (not strategy_params)")
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