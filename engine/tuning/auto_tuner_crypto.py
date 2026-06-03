# /home/MeirNiv/aimn-trade-final/engine/tuning/auto_tuner_crypto.py
# AiMN V3.1 - CRYPTO-SPECIFIC Auto Tuner
# Designed for trending crypto markets (BTC, ETH, SOL, LINK)
# Different from ETF tuner: wider stops, tighter trail, shorter time-stop, lower gates

import sys
sys.path.insert(0, '/home/MeirNiv/aimn-trade-final')
from engine.tuning.candle_fetcher import fetch_candles
from db import get_db_connection
from datetime import datetime
from itertools import product

# Crypto-specific defaults - different from ETF tuner
CRYPTO_DEFAULT = {
    'rsi_len_options'    : [20, 50, 100],
    'rsi_entry_options'  : [15, 20, 25],        # Stricter - only extreme oversold
    'macd_fast'          : 12,
    'macd_slow'          : 26,
    'macd_sig'           : 7,                   # Signal=7 (vs 9 for ETF)
    'stop_loss_options'  : [1.0, 1.5, 2.0],    # Wider stops for crypto volatility
    'trail_start_options': [0.3, 0.5, 0.8],    # Lower trail start
    'trail_minus_options': [0.05, 0.08, 0.10], # Tighter trail drop (8% of peak)
    'rsi_exit_options'   : [60.0, 65.0, 70.0],
    'init_profit_options': [0.3, 0.5, 1.0],    # Lower gates - realistic for crypto
    'decay_start_options': [1.0, 1.5, 2.0],    # Shorter decay window
    'decay_rate'         : 0.5,
    'timeframe'          : '1hr',
    'bars'               : 8000,
    'min_trades'         : 5,
    'score_metric'       : 'profit_per_day',
    'time_stop_hours'    : 2.0,                 # 2h TIME-STOP (vs 3h for ETF)
}

BAR_MINUTES_MAP = {
    '1m'  : 1,
    '5m'  : 5,
    '15m' : 15,
    '30m' : 30,
    '1h'  : 60,
    '1hr' : 60,
    '6hr' : 360,
    '1day': 1440,
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def calc_rsi_real(highs, lows, closes, i, lookback):
    start = max(0, i - lookback)
    hi = max(highs[start:i+1])
    lo = min(lows[start:i+1])
    if hi == lo:
        return None
    return max(0.0, min(100.0, ((closes[i] - lo) / (hi - lo)) * 100))

def calc_macd_series(closes, fast, slow, sig):
    n = len(closes)
    k_fast = 2 / (fast + 1)
    ema_f  = closes[0]
    k_slow = 2 / (slow + 1)
    ema_s  = closes[0]
    k_sig  = 2 / (sig + 1)
    macd_line   = [0.0] * n
    signal_line = [0.0] * n
    for i in range(1, n):
        ema_f = closes[i] * k_fast + ema_f * (1 - k_fast)
        ema_s = closes[i] * k_slow + ema_s * (1 - k_slow)
        macd_line[i] = ema_f - ema_s
    sig_val = macd_line[slow]
    for i in range(slow, n):
        sig_val = macd_line[i] * k_sig + sig_val * (1 - k_sig)
        signal_line[i] = sig_val
    return macd_line, signal_line

def backtest_crypto(highs, lows, closes, direction, params, bar_minutes, volumes=None):
    """Crypto-specific backtest with trending market logic"""
    rsi_len     = params['rsi_len']
    rsi_entry   = params['rsi_entry']
    stop_loss   = params['stop_loss']
    trail_start = params['trail_start']
    trail_minus = params['trail_minus']
    rsi_exit    = params['rsi_exit']
    init_profit = params['init_profit']
    decay_start = params['decay_start']
    decay_rate  = params.get('decay_rate', 0.5)
    min_trades  = params['min_trades']
    macd_fast   = params['macd_fast']
    macd_slow   = params['macd_slow']
    macd_sig    = params['macd_sig']
    time_stop   = params.get('time_stop_hours', 2.0)

    n = len(closes)
    macd_line, _ = calc_macd_series(closes, macd_fast, macd_slow, macd_sig)

    trades = 0
    wins = 0
    total_pnl = 0.0
    in_trade = False
    entry_price = 0.0
    peak_profit = -999.0
    entry_bar = 0
    exit_reasons = {'STOP': 0, 'TRAIL': 0, 'DECAY': 0, 'RSI': 0, 'TIME-STOP': 0}
    total_duration_hours = 0.0

    start_bar = max(rsi_len, macd_slow + macd_sig) + 3

    for i in range(start_bar, n - 1):
        if not in_trade:
            rsi = calc_rsi_real(highs, lows, closes, i, rsi_len)
            if rsi is None:
                continue

            macd_curr = macd_line[i]

            if direction == 'LONG':
                macd_rising = (i > 0) and (macd_line[i] > macd_line[i-1])
                rsi_prev = calc_rsi_real(highs, lows, closes, i-1, rsi_len) or rsi
                rsi_bouncing = rsi > rsi_prev
                # HTF filter: current close > previous close (bullish candle)
                htf_ok = (i >= 1) and (closes[i] > closes[i-1])
                # Volume confirmation
                vol_ok = True
                if volumes and i >= 20:
                    avg_vol = sum(volumes[i-20:i]) / 20
                    vol_ok = volumes[i] >= avg_vol * 0.8  # at least 80% of average
                entry_cond = (rsi <= rsi_entry) and macd_rising and (rsi_bouncing or rsi <= 8) and htf_ok and vol_ok
                if entry_cond and i >= 3:
                    recent_high = max(closes[i-3:i+1])
                    entry_cond = closes[i] <= recent_high * 0.998
            else:
                macd_falling = (i > 0) and (macd_line[i] < macd_line[i-1])
                rsi_prev = calc_rsi_real(highs, lows, closes, i-1, rsi_len) or rsi
                rsi_bouncing = rsi < rsi_prev
                htf_ok = (i >= 1) and (closes[i] < closes[i-1])
                vol_ok = True
                if volumes and i >= 20:
                    avg_vol = sum(volumes[i-20:i]) / 20
                    vol_ok = volumes[i] >= avg_vol * 0.8
                entry_cond = (rsi >= (100 - rsi_entry)) and macd_falling and (rsi_bouncing or rsi >= 92) and htf_ok and vol_ok
                if entry_cond and i >= 3:
                    recent_low = min(closes[i-3:i+1])
                    entry_cond = closes[i] >= recent_low * 1.002

            if entry_cond:
                in_trade = True
                entry_price = closes[i]
                peak_profit = -999.0
                entry_bar = i
                active_stop = stop_loss
                active_trail_start = trail_start
                active_trail_minus = trail_minus
                active_decay_start = decay_start

        else:
            if direction == 'LONG':
                current_pnl = (closes[i] - entry_price) / entry_price * 100
            else:
                current_pnl = (entry_price - closes[i]) / entry_price * 100

            peak_profit = max(peak_profit, current_pnl)
            dur_hours = (i - entry_bar) * bar_minutes / 60.0

            if dur_hours >= active_decay_start:
                current_gate = max(0.0, init_profit - (dur_hours - active_decay_start) * decay_rate)
            else:
                current_gate = init_profit

            exit_reason = None
            exit_hit = False

            # RULE 1: STOP LOSS
            if current_pnl <= -active_stop:
                exit_reason = 'STOP'
                exit_hit = True

            # RULE 2: TRAIL (proportional - 8% of peak for crypto)
            if not exit_hit and peak_profit >= active_trail_start:
                trail_level = peak_profit * 0.92  # 8% of peak (tighter for crypto)
                if current_pnl <= trail_level and trail_level > 0:
                    exit_reason = 'TRAIL'
                    exit_hit = True

            # RULE 3: RSI EXIT
            if not exit_hit and current_pnl >= current_gate:
                rsi = calc_rsi_real(highs, lows, closes, i, rsi_len)
                if rsi is not None:
                    if direction == 'LONG' and rsi >= rsi_exit and current_pnl >= current_gate:
                        exit_reason = 'RSI'
                        exit_hit = True
                    elif direction == 'SHORT' and rsi <= (100 - rsi_exit) and current_pnl >= current_gate:
                        exit_reason = 'RSI'
                        exit_hit = True

            # RULE 4: DECAY GATE
            if not exit_hit and dur_hours > active_decay_start and current_pnl > 0 and current_pnl >= current_gate:
                exit_reason = 'DECAY'
                exit_hit = True

            # RULE 5: TIME-STOP (2h for crypto, not 3h)
            if not exit_hit and dur_hours >= time_stop and current_pnl < 0:
                exit_reason = 'TIME-STOP'
                exit_hit = True

            if exit_hit:
                trades += 1
                total_pnl += current_pnl
                total_duration_hours += dur_hours
                if current_pnl > 0:
                    wins += 1
                exit_reasons[exit_reason] = exit_reasons.get(exit_reason, 0) + 1
                in_trade = False
                entry_price = 0.0
                peak_profit = -999.0

    if trades < min_trades:
        return None

    win_rate = wins / trades if trades > 0 else 0
    avg_dur = total_duration_hours / trades if trades > 0 else 0
    total_days = (n * bar_minutes) / (60 * 24)
    profit_per_day = total_pnl / total_days if total_days > 0 else 0

    return {
        'trades'         : trades,
        'wins'           : wins,
        'win_rate'       : round(win_rate * 100, 1),
        'total_pnl'      : round(total_pnl, 4),
        'avg_duration_h' : round(avg_dur, 2),
        'profit_per_day' : round(profit_per_day, 4),
        'exit_reasons'   : exit_reasons,
    }

def tune_crypto_strategy(symbol, direction, timeframe, cfg=None):
    """Tune a single crypto symbol/direction/timeframe with crypto-specific params"""
    cfg = cfg or {}
    params = {**CRYPTO_DEFAULT, **cfg}

    bar_minutes = BAR_MINUTES_MAP.get(timeframe, 60)
    bars = params.get('bars', 8000)

    log(f"\n{'='*55}")
    log(f"CRYPTO TUNE: {symbol} {direction} [{timeframe}]")

    candles = fetch_candles(symbol, timeframe, bars, broker='Gemini')
    if not candles or len(candles) < 200:
        log(f"NOT ENOUGH CANDLES: {len(candles) if candles else 0}")
        return

    highs   = [c['high'] for c in candles]
    lows    = [c['low'] for c in candles]
    closes  = [c['close'] for c in candles]
    volumes = [c.get('volume', 0) for c in candles]

    n = len(closes)
    split = n // 2
    train_highs, train_lows, train_closes, train_vols = highs[:split], lows[:split], closes[:split], volumes[:split]
    test_highs, test_lows, test_closes, test_vols = highs[split:], lows[split:], closes[split:], volumes[split:]

    log(f"Total: {n} | Train: {split} | Test: {n-split}")

    best_score = -999
    best_params = None
    best_train = None
    best_test = None

    param_grid = list(product(
        params['rsi_len_options'],
        params['rsi_entry_options'],
        params['stop_loss_options'],
        params['trail_start_options'],
        params['trail_minus_options'],
        params['rsi_exit_options'],
        params['init_profit_options'],
        params['decay_start_options'],
    ))

    log(f"Grid size: {len(param_grid)} combinations")

    for combo in param_grid:
        rsi_len, rsi_entry, stop_loss, trail_start, trail_minus, rsi_exit, init_profit, decay_start = combo

        p = {
            'rsi_len': rsi_len, 'rsi_entry': rsi_entry,
            'stop_loss': stop_loss, 'trail_start': trail_start,
            'trail_minus': trail_minus, 'rsi_exit': rsi_exit,
            'init_profit': init_profit, 'decay_start': decay_start,
            'decay_rate': params['decay_rate'],
            'macd_fast': params['macd_fast'],
            'macd_slow': params['macd_slow'],
            'macd_sig': params['macd_sig'],
            'min_trades': params['min_trades'],
            'time_stop_hours': params.get('time_stop_hours', 2.0),
        }

        train_result = backtest_crypto(train_highs, train_lows, train_closes, direction, p, bar_minutes, train_vols)
        if not train_result:
            continue

        score = train_result[params['score_metric']]
        if score > best_score:
            best_score = score
            best_params = p
            best_train = train_result

    if not best_params:
        log("NO VALID PARAMS FOUND")
        return

    log(f"TRAIN: PnL={best_train['total_pnl']}% WR={best_train['win_rate']}% trades={best_train['trades']}")

    test_result = backtest_crypto(test_highs, test_lows, test_closes, direction, best_params, bar_minutes, test_vols)

    if not test_result or test_result['total_pnl'] <= 0:
        log("TEST: Not enough trades or negative")
        log("NOT SAVED - test window negative or insufficient")
        return

    log(f"TEST:  PnL={test_result['total_pnl']}% WR={test_result['win_rate']}% trades={test_result['trades']}")

    ratio = test_result['profit_per_day'] / best_train['profit_per_day'] if best_train['profit_per_day'] > 0 else 0
    log(f"Overfit ratio: {ratio:.2f} (1.0=perfect, <0.5=overfit)")

    # Save to DB
    conn, cursor = get_db_connection()
    try:
        cursor.execute("""
            SELECT bp.id FROM broker_products bp
            JOIN brokers b ON bp.broker_id = b.id
            WHERE bp.local_ticker = %s AND b.name = 'Gemini'
            LIMIT 1
        """, (symbol,))
        row = cursor.fetchone()
        if not row:
            log(f"Symbol {symbol} not found in DB")
            return

        bp_id = row['id'] if isinstance(row, dict) else row[0]

        cursor.execute("""
            SELECT id FROM strategy_params
            WHERE broker_product_id = %s AND direction = %s AND candle_time = %s
            LIMIT 1
        """, (bp_id, direction, timeframe))
        existing = cursor.fetchone()

        pl_pct = test_result['total_pnl']

        if existing:
            sp_id = existing['id'] if isinstance(existing, dict) else existing[0]
            cursor.execute("""
                UPDATE strategy_params SET
                    rsi_len=%s, rsi_entry=%s, stop_loss=%s,
                    trailing_start=%s, trailing_drop=%s, rsi_exit=%s,
                    init_profit=%s, decay_start=%s, decay_rate=%s,
                    pl_pct=%s, last_tuned=NOW(), active=0
                WHERE id=%s
            """, (best_params['rsi_len'], best_params['rsi_entry'], best_params['stop_loss'],
                  best_params['trail_start'], best_params['trail_minus'], best_params['rsi_exit'],
                  best_params['init_profit'], best_params['decay_start'], best_params['decay_rate'],
                  pl_pct, sp_id))
            log(f"  Updated id={sp_id}")
        else:
            cursor.execute("""
                INSERT INTO strategy_params
                    (broker_product_id, direction, candle_time, rsi_len, rsi_entry,
                     stop_loss, trailing_start, trailing_drop, rsi_exit,
                     init_profit, decay_start, decay_rate, pl_pct, last_tuned, active)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),0)
            """, (bp_id, direction, timeframe,
                  best_params['rsi_len'], best_params['rsi_entry'], best_params['stop_loss'],
                  best_params['trail_start'], best_params['trail_minus'], best_params['rsi_exit'],
                  best_params['init_profit'], best_params['decay_start'], best_params['decay_rate'],
                  pl_pct))
            log(f"  Created new strategy id={cursor.lastrowid}")

        conn.commit()
        log(f"SAVED - {symbol} {direction} [{timeframe}] Test={pl_pct}%")

    except Exception as e:
        log(f"DB ERROR: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Quick test
    tune_crypto_strategy('BTC/USD', 'LONG', '1hr')