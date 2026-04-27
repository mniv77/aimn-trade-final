# auto_executor.py - AiMN V3.1 Auto-Execution Engine
# Full logging version — see every cycle in engine.log
import mysql.connector
import time
from datetime import datetime
import db_config as config

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

def check_and_execute_signals():
    """
    Scan for MATCH-MATCH conditions and auto-execute paper trades.
    Only executes ONE trade per broker at a time.
    """
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                sp.id,
                sp.broker_product_id,
                sp.direction,
                sp.candle_time,
                sp.rsi_real,
                sp.rsi_entry,
                sp.macd,
                sp.last_price,
                sp.active_order_id,
                bp.local_ticker as symbol,
                b.name as broker_name
            FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            JOIN brokers b ON bp.broker_id = b.id
            WHERE sp.active = 1
            ORDER BY sp.id
        """)

        strategies = cursor.fetchall()

        # First pass: identify brokers with active trades
        active_brokers = set()
        for strat in strategies:
            if strat['active_order_id'] is not None:
                active_brokers.add(strat['broker_name'])

        # Second pass: execute new signals
        for strat in strategies:
            broker = strat['broker_name']

            if broker in active_brokers:
                continue
            if strat['active_order_id'] is not None:
                continue

            rsi_val  = float(strat['rsi_real']  or 0)
            rsi_goal = float(strat['rsi_entry'] or 0)
            macd_val = float(strat['macd']      or 0)
            direction = strat['direction']
            price    = float(strat['last_price'] or 0)

            if price <= 0:
                continue

            rsi_ready  = (direction == 'LONG'  and rsi_val <= rsi_goal) or \
                         (direction == 'SHORT' and rsi_val >= rsi_goal)
            macd_ready = (direction == 'LONG'  and macd_val > 0) or \
                         (direction == 'SHORT' and macd_val < 0)

            if rsi_ready and macd_ready:
                log(f"🚀 MATCH-MATCH: {strat['symbol']} {direction} {strat['candle_time']} @ ${price:,.2f} | RSI={rsi_val:.2f} MACD={macd_val:.4f}")

                cursor.execute("""
                    UPDATE strategy_params
                    SET active_order_id = %s,
                        entry_price = %s,
                        entry_time = NOW()
                    WHERE id = %s
                """, (999999, price, strat['id']))

                log(f"✅ Paper trade opened: Strategy #{strat['id']} {strat['symbol']} {direction} {strat['candle_time']}")
                active_brokers.add(broker)

    except Exception as e:
        log(f"❌ Signal check error: {e}")
    finally:
        cursor.close()
        conn.close()


def monitor_and_exit_trades():
    """
    Monitor all active trades and apply exit logic:
    1. Stop Loss
    2. Trailing Stop
    3. RSI Target
    4. CurrentGate decay
    """
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                sp.id,
                sp.direction,
                sp.candle_time,
                sp.entry_price,
                sp.entry_time,
                sp.last_price,
                sp.rsi_real,
                sp.rsi_exit,
                sp.stop_loss,
                sp.trailing_start,
                sp.trailing_drop,
                sp.take_profit as init_profit,
                sp.decay_start,
                sp.decay_rate,
                sp.peak_profit,
                bp.local_ticker as symbol,
                b.name as broker_name
            FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            JOIN brokers b ON bp.broker_id = b.id
            WHERE sp.active = 1 AND sp.active_order_id IS NOT NULL
        """)

        trades = cursor.fetchall()

        if not trades:
            return  # No active trades — silent

        for trade in trades:
            try:
                strategy_id   = trade['id']
                symbol        = trade['symbol']
                direction     = trade['direction']
                candle_time   = trade['candle_time']
                entry_price   = float(trade['entry_price']  or 0)
                current_price = float(trade['last_price']   or 0)
                entry_time    = trade['entry_time']

                if entry_price <= 0 or current_price <= 0:
                    log(f"⚠️  #{strategy_id} {symbol} — missing price, skipping")
                    continue

                # Calculate P&L
                if direction == 'LONG':
                    pnl = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl = ((entry_price - current_price) / entry_price) * 100

                # Calculate duration
                if entry_time:
                    duration_seconds = (datetime.now() - entry_time).total_seconds()
                    duration_hours   = duration_seconds / 3600.0
                else:
                    duration_seconds = 0
                    duration_hours   = 0

                # Exit parameters
                stop_loss      = float(trade['stop_loss']      or 2.0)
                rsi_exit_target= float(trade['rsi_exit']       or 70.0)
                rsi_current    = float(trade['rsi_real']        or 0)
                trailing_start = float(trade['trailing_start'] or 5.0)
                trailing_drop  = float(trade['trailing_drop']  or 1.0)
                init_profit    = float(trade['init_profit']    or 3.0)
                decay_start    = float(trade['decay_start']    or 2.0)
                decay_rate     = float(trade['decay_rate']     or 0.2)

                # CurrentGate — profit floor with decay
                if duration_hours > decay_start:
                    decay_amount = (duration_hours - decay_start) * decay_rate
                    current_gate = max(0, init_profit - decay_amount)
                else:
                    current_gate = init_profit

                # Peak profit tracking
                peak_profit = float(trade['peak_profit'] or -999.0)
                if pnl > peak_profit:
                    peak_profit = pnl
                    cursor.execute(
                        "UPDATE strategy_params SET peak_profit = %s WHERE id = %s",
                        (peak_profit, strategy_id)
                    )

                # ── LOG every cycle so you can watch in engine.log ──
                dur_str = f"{int(duration_hours)}h{int((duration_hours%1)*60)}m"
                log(f"  👁  #{strategy_id} {symbol} {direction} {candle_time} | "
                    f"P&L: {pnl:+.2f}% | Peak: {peak_profit:.2f}% | "
                    f"Gate: {current_gate:.2f}% | RSI: {rsi_current:.1f} | "
                    f"Dur: {dur_str}")

                # ═══════════════════════════════════════════════
                # EXIT LOGIC — matches TradingView Pine Script
                # ═══════════════════════════════════════════════
                exit_reason = None

                # 1. STOP LOSS — always exits regardless of gate
                if pnl <= -stop_loss:
                    exit_reason = "STOP"
                    log(f"  🛑 STOP LOSS: {symbol} {direction} | P&L: {pnl:.2f}% | Stop: -{stop_loss:.2f}%")

                # 2. TRAILING STOP
                elif peak_profit >= trailing_start and pnl <= (peak_profit - trailing_drop):
                    if pnl >= current_gate:
                        exit_reason = "TRAIL-EXIT"
                        log(f"  📉 TRAIL EXIT: {symbol} {direction} | Peak: {peak_profit:.2f}% | Current: {pnl:.2f}% | Gate: {current_gate:.2f}%")

                # 3. RSI TARGET EXIT
                elif (direction == 'LONG'  and rsi_current >= rsi_exit_target) or \
                     (direction == 'SHORT' and rsi_current <= rsi_exit_target):
                    if pnl >= current_gate:
                        exit_reason = "RSI-EXIT"
                        log(f"  🎯 RSI EXIT: {symbol} {direction} | RSI: {rsi_current:.2f} target: {rsi_exit_target:.2f} | P&L: {pnl:.2f}%")

                # ── EXECUTE EXIT ─────────────────────────────
                if exit_reason:
                    # Save to orders table
                    cursor.execute("""
                        INSERT INTO orders (
                            strategy_id, symbol, broker, side, candle_time,
                            entry_price, exit_price, pnl_percent, duration_seconds,
                            status, exit_reason, rsi_real_entry,
                            entry_rsi_max, entry_rsi_min, created_at
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                    """, (
                        strategy_id,
                        symbol,
                        trade['broker_name'],
                        direction,
                        candle_time,
                        entry_price,
                        current_price,
                        round(pnl, 4),
                        int(duration_seconds),
                        'CLOSED',
                        exit_reason,
                        rsi_current,
                        0,
                        0
                    ))

                    # Clear active order from strategy
                    cursor.execute("""
                        UPDATE strategy_params
                        SET active_order_id = NULL,
                            entry_price = NULL,
                            entry_time = NULL,
                            peak_profit = -999.0
                        WHERE id = %s
                    """, (strategy_id,))

                    log(f"  ✅ ORDER CLOSED: #{strategy_id} {symbol} {direction} {candle_time} | "
                        f"Reason: {exit_reason} | P&L: {pnl:+.2f}% | "
                        f"Entry: ${entry_price:,.2f} Exit: ${current_price:,.2f} | "
                        f"Duration: {dur_str}")

            except Exception as e:
                log(f"  ❌ Error monitoring #{trade.get('id','?')}: {e}")
                continue

    except Exception as e:
        log(f"❌ Monitor error: {e}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    """Run standalone for testing"""
    print("=" * 60)
    print("AiMN V3.1 - AUTO EXECUTOR (standalone)")
    print("=" * 60)
    cycle = 0
    while True:
        try:
            cycle += 1
            log(f"[Cycle {cycle}]")
            check_and_execute_signals()
            monitor_and_exit_trades()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n⛔ Stopped")
            break
        except Exception as e:
            log(f"🔥 ERROR: {e}")
            time.sleep(5)