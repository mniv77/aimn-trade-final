# /home/MeirNiv/aimn-trade-final/engine/tuning/tune_macd.py
# AiMN V3.1 - MACD Auto Tuner with Before/After comparison

import sys
sys.path.insert(0, '/home/MeirNiv/aimn-trade-final')

from engine.tuning.candle_fetcher import fetch_candles
from engine.tuning.auto_tuner import backtest, score, BAR_MINUTES_MAP
from db import get_db_connection
from datetime import datetime
from itertools import product

MACD_FAST_OPTIONS = [8, 12, 16]
MACD_SLOW_OPTIONS = [21, 26, 30]
MACD_SIG_OPTIONS  = [7,  9,  12]
TRAIN_PCT         = 0.5
SCORE_METRIC      = 'profit_per_day'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def tune_macd_for_strategy(strategy_id, symbol, direction, candle_time,
                            current_params, broker_name="Gemini"):
    timeframe   = candle_time if candle_time else '1hr'
    bar_minutes = BAR_MINUTES_MAP.get(timeframe, 60)

    candles = fetch_candles(symbol, timeframe, 2000, broker=broker_name)
    if not candles or len(candles) < 50:
        return None

    candles.sort(key=lambda x: x['timestamp'])
    highs  = [float(c['high'])  for c in candles]
    lows   = [float(c['low'])   for c in candles]
    closes = [float(c['close']) for c in candles]
    split  = int(len(closes) * TRAIN_PCT)

    # ── BASELINE: test with standard 12/26/9 ──
    baseline_params = current_params.copy()
    baseline_params['macd_fast'] = 12
    baseline_params['macd_slow'] = 26
    baseline_params['macd_sig']  = 9
    baseline = backtest(highs[split:], lows[split:], closes[split:],
                       direction, baseline_params, bar_minutes)
    baseline_pnl = round(baseline['total_pnl'], 4) if baseline else 0.0
    baseline_wr  = round(baseline['winrate'], 2) if baseline else 0.0

    # ── GRID SEARCH for best MACD ──
    best_score  = -999
    best_macd   = None
    best_result = None

    for fast, slow, sig in product(MACD_FAST_OPTIONS, MACD_SLOW_OPTIONS, MACD_SIG_OPTIONS):
        if fast >= slow:
            continue
        params = current_params.copy()
        params['macd_fast'] = fast
        params['macd_slow'] = slow
        params['macd_sig']  = sig

        train = backtest(highs[:split], lows[:split], closes[:split],
                        direction, params, bar_minutes)
        if not train:
            continue

        test = backtest(highs[split:], lows[split:], closes[split:],
                       direction, params, bar_minutes)
        if not test or test['total_pnl'] <= 0:
            continue

        s = score(test, SCORE_METRIC)
        if s > best_score:
            best_score  = s
            best_macd   = (fast, slow, sig)
            best_result = test

    if not best_macd:
        return {
            'symbol': symbol, 'direction': direction, 'timeframe': timeframe,
            'baseline_macd': '12/26/9', 'baseline_pnl': baseline_pnl, 'baseline_wr': baseline_wr,
            'best_macd': 'NO IMPROVEMENT', 'best_pnl': baseline_pnl, 'best_wr': baseline_wr,
            'improvement': 0.0
        }

    fast, slow, sig = best_macd
    best_pnl = round(best_result['total_pnl'], 4)
    best_wr  = round(best_result['winrate'], 2)
    improvement = round(best_pnl - baseline_pnl, 4)

    # ── SAVE to DB only if improved ──
    if best_pnl > baseline_pnl:
        conn, cursor = get_db_connection()
        if conn:
            try:
                cursor.execute("""
                    UPDATE strategy_params
                    SET macd_fast = %s, macd_slow = %s, macd_sig = %s, last_tuned = NOW()
                    WHERE id = %s
                """, (fast, slow, sig, strategy_id))
                conn.commit()
            except Exception as e:
                log(f"  ❌ Save error: {e}")
            finally:
                conn.close()

    return {
        'symbol': symbol, 'direction': direction, 'timeframe': timeframe,
        'baseline_macd': '12/26/9', 'baseline_pnl': baseline_pnl, 'baseline_wr': baseline_wr,
        'best_macd': f"{fast}/{slow}/{sig}", 'best_pnl': best_pnl, 'best_wr': best_wr,
        'improvement': improvement
    }


def run_macd_tuning_all():
    log("=" * 75)
    log("AiMN MACD Auto Tuner — Before/After Comparison")
    log("=" * 75)

    conn, cursor = get_db_connection()
    if not conn:
        log("❌ DB connection failed")
        return

    cursor.execute("""
        SELECT sp.id, bp.local_ticker, sp.direction, sp.candle_time,
               sp.rsi_len, sp.rsi_entry, sp.rsi_exit,
               sp.stop_loss, sp.trailing_start, sp.trailing_drop,
               sp.init_profit, sp.decay_start, sp.decay_rate,
               b.name as broker_name
        FROM strategy_params sp
        JOIN broker_products bp ON sp.broker_product_id = bp.id
        JOIN brokers b ON bp.broker_id = b.id
        WHERE sp.active = 1 AND sp.pl_pct > 0
        ORDER BY sp.pl_pct DESC
    """)
    strategies = cursor.fetchall()
    conn.close()

    log(f"Found {len(strategies)} active strategies")
    log("")

    results = []
    for s in strategies:
        params = {
            'rsi_len'    : s['rsi_len'],
            'rsi_entry'  : float(s['rsi_entry']),
            'rsi_exit'   : float(s['rsi_exit']),
            'stop_loss'  : float(s['stop_loss']),
            'trail_start': float(s['trailing_start']),
            'trail_minus': float(s['trailing_drop']),
            'init_profit': float(s['init_profit']),
            'decay_start': float(s['decay_start']),
            'decay_rate' : float(s['decay_rate']),
            'min_trades' : 5,
            'macd_fast'  : 12,
            'macd_slow'  : 26,
            'macd_sig'   : 9,
        }
        r = tune_macd_for_strategy(
            strategy_id    = s['id'],
            symbol         = s['local_ticker'],
            direction      = s['direction'],
            candle_time    = s['candle_time'],
            current_params = params,
            broker_name    = s['broker_name']
        )
        if r:
            results.append(r)

    # ── PRINT COMPARISON TABLE ──
    log("")
    log("=" * 75)
    log("BEFORE/AFTER COMPARISON TABLE")
    log("=" * 75)
    log(f"{'Symbol':<12} {'Dir':<6} {'TF':<5} {'Old MACD':<10} {'Old PnL%':<10} {'New MACD':<10} {'New PnL%':<10} {'Gain':<8}")
    log("-" * 75)

    improved = 0
    no_change = 0
    worse = 0

    for r in results:
        gain = r['improvement']
        if gain > 0:
            flag = '✅'
            improved += 1
        elif gain == 0:
            flag = '➡️'
            no_change += 1
        else:
            flag = '⚠️'
            worse += 1

        log(f"{r['symbol']:<12} {r['direction']:<6} {r['timeframe']:<5} "
            f"{r['baseline_macd']:<10} {r['baseline_pnl']:<10} "
            f"{r['best_macd']:<10} {r['best_pnl']:<10} "
            f"{gain:+.2f}% {flag}")

    log("-" * 75)
    log(f"Improved: {improved} | No change: {no_change} | Worse: {worse}")
    log("=" * 75)


if __name__ == "__main__":
    run_macd_tuning_all()
