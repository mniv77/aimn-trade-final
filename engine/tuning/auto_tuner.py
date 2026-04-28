# /home/MeirNiv/aimn-trade-final/engine/tuning/auto_tuner.py
# AiMN V3.1 - Auto Tuner - FIXED backtest logic
# Phase 1 (dur < decay_start): Trail + RSI exits active, Stop always active
# Phase 2 (dur >= decay_start): Decay gate active, Trail + RSI still work

import sys
sys.path.insert(0, '/home/MeirNiv/aimn-trade-final')

from engine.tuning.candle_fetcher import fetch_candles
from db import get_db_connection
from datetime import datetime
from itertools import product

DEFAULT = {
    'rsi_len_options'    : [50, 100, 168],
    'rsi_entry_options'  : [25, 35, 40],
    'macd_fast'          : 12,
    'macd_slow'          : 26,
    'macd_sig'           : 9,
    'stop_loss_options'  : [0.3, 1.0, 2.0],
    'trail_start_options': [0.2, 0.5, 1.0],
    'trail_minus_options': [0.1, 0.2, 0.3],
    'rsi_exit_options'   : [65.0, 70.0, 75.0],
    'init_profit_options': [0.1, 0.5, 1.5],
    'decay_start_options': [0.5, 1.0, 2.0],
    'decay_rate'         : 0.5,
    'timeframe'          : '5m',
    'bars'               : 2000,
    'min_trades'         : 3,
    'score_metric'       : 'total_pnl',
}

BAR_MINUTES_MAP = {
    '1m'  : 1,
    '5m'  : 5,
    '15m' : 15,
    '30m' : 30,
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
    ema_fast_arr = [ema_f]
    for i in range(1, n):
        ema_f = closes[i] * k_fast + ema_f * (1 - k_fast)
        ema_fast_arr.append(ema_f)

    k_slow = 2 / (slow + 1)
    ema_s  = closes[0]
    ema_slow_arr = [ema_s]
    for i in range(1, n):
        ema_s = closes[i] * k_slow + ema_s * (1 - k_slow)
        ema_slow_arr.append(ema_s)

    macd_line = [ema_fast_arr[i] - ema_slow_arr[i] for i in range(n)]

    k_sig  = 2 / (sig + 1)
    ema_sg = macd_line[0]
    sig_arr = [ema_sg]
    for i in range(1, n):
        ema_sg = macd_line[i] * k_sig + ema_sg * (1 - k_sig)
        sig_arr.append(ema_sg)

    return macd_line, sig_arr


def backtest(highs, lows, closes, direction, params, bar_minutes):
    rsi_len     = params['rsi_len']
    rsi_entry   = params['rsi_entry']
    stop_loss   = params['stop_loss']
    trail_start = params['trail_start']
    trail_minus = params['trail_minus']
    rsi_exit    = params['rsi_exit']
    init_profit = params['init_profit']
    decay_start = params['decay_start']
    decay_rate  = params['decay_rate']
    min_trades  = params['min_trades']
    macd_fast   = params['macd_fast']
    macd_slow   = params['macd_slow']
    macd_sig    = params['macd_sig']

    n = len(closes)
    macd_line, _ = calc_macd_series(closes, macd_fast, macd_slow, macd_sig)

    trades      = 0
    wins        = 0
    total_pnl   = 0.0
    in_trade    = False
    entry_price = 0.0
    peak_profit = -999.0
    entry_bar   = 0

    exit_reasons = {'STOP': 0, 'TRAIL': 0, 'DECAY': 0, 'RSI': 0}
    start_bar = max(rsi_len, macd_slow + macd_sig) + 1

    for i in range(start_bar, n - 1):
        if not in_trade:
            # ── ENTRY ────────────────────────────────────
            rsi = calc_rsi_real(highs, lows, closes, i, rsi_len)
            if rsi is None:
                continue
            macd_curr = macd_line[i]
            if direction == 'LONG':
                entry_cond = (rsi <= rsi_entry) and (macd_curr > 0)
            else:
                entry_cond = (rsi >= (100 - rsi_entry)) and (macd_curr < 0)
            if entry_cond:
                in_trade    = True
                entry_price = closes[i]
                peak_profit = -999.0
                entry_bar   = i
        else:
            # ── EXIT ─────────────────────────────────────
            if direction == 'LONG':
                current_pnl = (closes[i] - entry_price) / entry_price * 100
            else:
                current_pnl = (entry_price - closes[i]) / entry_price * 100

            peak_profit = max(peak_profit, current_pnl)
            dur_hours   = (i - entry_bar) * bar_minutes / 60.0

            # Current gate — decays after decay_start hours
            if dur_hours >= decay_start:
                current_gate = max(0.0, init_profit - (dur_hours - decay_start) * decay_rate)
            else:
                current_gate = init_profit

            exit_reason = None
            exit_hit    = False

            # ── RULE 1: STOP LOSS — always active ────────
            if current_pnl <= -stop_loss:
                exit_reason = 'STOP'
                exit_hit    = True

            # ── RULE 2: TRAIL EXIT ────────────────────────
            # Trail exits whenever peak drops by trail_minus — NO gate check!
            # The trail IS the exit signal — gate should not block it
            elif peak_profit >= trail_start:
                trail_level = peak_profit - trail_minus
                if current_pnl <= trail_level:
                    exit_reason = 'TRAIL'
                    exit_hit    = True

            # ── RULE 3: RSI EXIT ──────────────────────────
            if not exit_hit:
                rsi = calc_rsi_real(highs, lows, closes, i, rsi_len)
                if rsi is not None:
                    if direction == 'LONG' and rsi >= rsi_exit and current_pnl >= current_gate:
                        exit_reason = 'RSI'
                        exit_hit    = True
                    elif direction == 'SHORT' and rsi <= (100 - rsi_exit) and current_pnl >= current_gate:
                        exit_reason = 'RSI'
                        exit_hit    = True

            # ── RULE 4: DECAY EXIT ────────────────────────
            # Only after decay_start hours, when gate reaches 0
            if not exit_hit and dur_hours >= decay_start:
                if current_pnl >= current_gate:
                    exit_reason = 'DECAY'
                    exit_hit    = True

            if exit_hit:
                exit_reasons[exit_reason] += 1
                total_pnl += current_pnl
                trades    += 1
                if current_pnl > 0:
                    wins += 1
                in_trade    = False
                peak_profit = -999.0

    if trades < min_trades:
        return None

    return {
       'trades'        : trades,
        'wins'          : wins,
        'winrate'       : round(wins / trades * 100, 2),
        'avg_pnl'       : round(total_pnl / trades, 4),
        'total_pnl'     : round(total_pnl, 4),
        'exit_breakdown': exit_reasons,
    }

def score(result, metric='total_pnl'):
    if not result:
        return -999
    decay_pct = result['exit_breakdown']['DECAY'] / result['trades']
    decay_penalty = decay_pct * 15
    if metric == 'winrate':
        return result['winrate'] + (result['total_pnl'] * 0.01) - decay_penalty
    if metric == 'avg_pnl':
        return result['avg_pnl'] + (result['winrate'] * 0.001) - decay_penalty
    return result['total_pnl'] + (result['winrate'] * 0.01) - decay_penalty


def save_best_params(strategy_id, params, result):
    conn, cursor = get_db_connection()
    if not conn:
        log("❌ DB connection failed")
        return
    try:
        is_active = 1 if result['total_pnl'] > 0 else 0
        cursor.execute("""
            UPDATE strategy_params
            SET rsi_len        = %s,
                rsi_entry      = %s,
                stop_loss      = %s,
                trailing_start = %s,
                trailing_drop  = %s,
                rsi_exit       = %s,
                init_profit    = %s,
                decay_start    = %s,
                decay_rate     = %s,
                last_tuned     = NOW(),
                pl_pct         = %s,
                active         = %s
            WHERE id = %s
        """, (
            params['rsi_len'], params['rsi_entry'], params['stop_loss'],
            params['trail_start'], params['trail_minus'], params['rsi_exit'],
            params['init_profit'], params['decay_start'], params['decay_rate'],
            result['total_pnl'], is_active, strategy_id
        ))
        cursor.execute("""
            INSERT INTO tuning_history
                (strategy_id, rsi_len, rsi_entry, stop_loss,
                 trailing_start, trailing_drop, winrate, avg_pnl,
                 pl_pct, trades_tested, tuned_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            strategy_id, params['rsi_len'], params['rsi_entry'], params['stop_loss'],
            params['trail_start'], params['trail_minus'],
            result['winrate'], result['avg_pnl'], result['total_pnl'], result['trades'],
        ))
        log(f"  ✅ Saved id={strategy_id}")
    except Exception as e:
        log(f"  ❌ Save error: {e}")
    finally:
        conn.close()



def walk_forward(highs, lows, closes, direction, params, bar_minutes, train_pct=0.7):
    n = len(closes)
    split = int(n * train_pct)
    train = backtest(highs[:split], lows[:split], closes[:split], direction, params, bar_minutes)
    test  = backtest(highs[split:], lows[split:], closes[split:], direction, params, bar_minutes)
    return train, test


def tune_strategy_wf(strategy_id, symbol, direction, candle_time=None, cfg=None, broker_name="Gemini", train_pct=0.7):
    if cfg is None:
        cfg = DEFAULT.copy()
    timeframe    = cfg.get('timeframe', DEFAULT['timeframe'])
    bars         = cfg.get('bars', DEFAULT['bars'])
    bar_minutes  = BAR_MINUTES_MAP.get(timeframe, 60)
    score_metric = cfg.get('score_metric', DEFAULT['score_metric'])
    rsi_len_options     = cfg.get('rsi_len_options',     DEFAULT['rsi_len_options'])
    rsi_entry_options   = cfg.get('rsi_entry_options',   DEFAULT['rsi_entry_options'])
    stop_loss_options   = cfg.get('stop_loss_options',   DEFAULT['stop_loss_options'])
    trail_start_options = cfg.get('trail_start_options', DEFAULT['trail_start_options'])
    trail_minus_options = cfg.get('trail_minus_options', DEFAULT['trail_minus_options'])
    init_profit_options = cfg.get('init_profit_options') or [cfg.get('init_profit', 1.0)]
    rsi_exit_options    = cfg.get('rsi_exit_options')    or [cfg.get('rsi_exit', 70.0)]
    decay_start_options = cfg.get('decay_start_options') or [cfg.get('decay_start', 0.5)]
    fixed = {
        'decay_rate': cfg.get('decay_rate', DEFAULT['decay_rate']),
        'min_trades': cfg.get('min_trades', DEFAULT['min_trades']),
        'macd_fast' : cfg.get('macd_fast',  DEFAULT['macd_fast']),
        'macd_slow' : cfg.get('macd_slow',  DEFAULT['macd_slow']),
        'macd_sig'  : cfg.get('macd_sig',   DEFAULT['macd_sig']),
    }
    log("=" * 55)
    log("Walk-Forward: " + symbol + " " + direction + " [" + timeframe + "] train=" + str(int(train_pct*100)) + "%")
    candles = fetch_candles(symbol, timeframe, bars, broker=broker_name)
    if not candles or len(candles) < 50:
        log("Insufficient candles")
        return None
    candles.sort(key=lambda x: x['timestamp'])
    highs  = [float(c['high'])  for c in candles]
    lows   = [float(c['low'])   for c in candles]
    closes = [float(c['close']) for c in candles]
    split  = int(len(closes) * train_pct)
    log("Total: " + str(len(closes)) + " | Train: " + str(split) + " | Test: " + str(len(closes)-split))
    best_train  = None
    best_params = None
    best_score  = -999
    for init_profit, rsi_exit, decay_start, rsi_len, rsi_entry, stop_loss, trail_start, trail_minus in product(
        init_profit_options, rsi_exit_options, decay_start_options, rsi_len_options,
        rsi_entry_options, stop_loss_options, trail_start_options, trail_minus_options
    ):
        if trail_minus >= trail_start:
            continue
        params = {
            'init_profit': init_profit, 'rsi_exit': rsi_exit,
            'decay_start': decay_start, 'rsi_len': rsi_len,
            'rsi_entry': rsi_entry, 'stop_loss': stop_loss,
            'trail_start': trail_start, 'trail_minus': trail_minus,
            **fixed
        }
        train_result = backtest(highs[:split], lows[:split], closes[:split], direction, params, bar_minutes)
        if not train_result:
            continue
        s = score(train_result, score_metric)
        if s > best_score:
            best_score  = s
            best_train  = train_result
            best_params = params.copy()
    if not best_params:
        log("No valid combinations in train window")
        return None
    best_test = backtest(highs[split:], lows[split:], closes[split:], direction, best_params, bar_minutes)
    log("TRAIN: PnL=" + str(best_train['total_pnl']) + "% WR=" + str(best_train['winrate']) + "% trades=" + str(best_train['trades']))
    if best_test:
        log("TEST:  PnL=" + str(best_test['total_pnl']) + "% WR=" + str(best_test['winrate']) + "% trades=" + str(best_test['trades']))
        ratio = round(best_test['total_pnl'] / best_train['total_pnl'], 2) if best_train['total_pnl'] != 0 else 0
        log("Overfit ratio: " + str(ratio) + " (1.0=perfect, <0.5=overfit)")
    else:
        log("TEST: Not enough trades")
        ratio = None
    if best_test and best_test['total_pnl'] > 0:
        save_best_params(strategy_id, best_params, best_test)
        log("SAVED — test window positive!")
    else:
        log("NOT SAVED — test window negative or insufficient")
    return {
        'symbol'       : symbol,
        'direction'    : direction,
        'timeframe'    : timeframe,
        'params'       : best_params,
        'train_result' : best_train,
        'test_result'  : best_test,
        'overfit_ratio': ratio,
    }


def tune_strategy(strategy_id, symbol, direction, candle_time=None, cfg=None, broker_name="Gemini"):
    if cfg is None:
        cfg = DEFAULT.copy()

    timeframe    = cfg.get('timeframe',    DEFAULT['timeframe'])
    bars         = cfg.get('bars',         DEFAULT['bars'])
    bar_minutes  = BAR_MINUTES_MAP.get(timeframe, 60)
    score_metric = cfg.get('score_metric', DEFAULT['score_metric'])

    rsi_len_options     = cfg.get('rsi_len_options',     DEFAULT['rsi_len_options'])
    rsi_entry_options   = cfg.get('rsi_entry_options',   DEFAULT['rsi_entry_options'])
    stop_loss_options   = cfg.get('stop_loss_options',   DEFAULT['stop_loss_options'])
    trail_start_options = cfg.get('trail_start_options', DEFAULT['trail_start_options'])
    trail_minus_options = cfg.get('trail_minus_options', DEFAULT['trail_minus_options'])
    init_profit_options = cfg.get('init_profit_options') or [cfg.get('init_profit', 1.0)]
    rsi_exit_options    = cfg.get('rsi_exit_options')    or [cfg.get('rsi_exit', 70.0)]
    decay_start_options = cfg.get('decay_start_options') or [cfg.get('decay_start', 0.5)]
    fixed = {
        'decay_rate' : cfg.get('decay_rate',  DEFAULT['decay_rate']),
        'min_trades' : cfg.get('min_trades',  DEFAULT['min_trades']),
        'macd_fast'  : cfg.get('macd_fast',   DEFAULT['macd_fast']),
        'macd_slow'  : cfg.get('macd_slow',   DEFAULT['macd_slow']),
        'macd_sig'   : cfg.get('macd_sig',    DEFAULT['macd_sig']),
    }

    log(f"\n{'='*55}")
    log(f"Tuning: {symbol} {direction} [{timeframe}]")

    candles = fetch_candles(symbol, timeframe, bars, broker=broker_name)
    if not candles or len(candles) < 50:
        log(f"❌ Insufficient candles: {len(candles) if candles else 0}")
        return None

    candles.sort(key=lambda x: x['timestamp'])
    highs  = [float(c['high'])  for c in candles]
    lows   = [float(c['low'])   for c in candles]
    closes = [float(c['close']) for c in candles]
    log(f"  Fetched {len(closes)} candles ({timeframe})")

    best_result = None
    best_params = None
    best_score  = -999

    for init_profit, rsi_exit, decay_start, rsi_len, rsi_entry, stop_loss, trail_start, trail_minus in product(
        init_profit_options, rsi_exit_options, decay_start_options, rsi_len_options,
        rsi_entry_options, stop_loss_options, trail_start_options, trail_minus_options
    ):
        # Skip invalid combinations where trail_minus >= trail_start
        if trail_minus >= trail_start:
            continue

        params = {
            'init_profit': init_profit, 'rsi_exit': rsi_exit,
            'decay_start': decay_start,
            'rsi_len': rsi_len, 'rsi_entry': rsi_entry,
            'stop_loss': stop_loss, 'trail_start': trail_start,
            'trail_minus': trail_minus, **fixed
        }
        result = backtest(highs, lows, closes, direction, params, bar_minutes)
        if not result:
            continue
        s = score(result, score_metric)
        if s > best_score:
            best_score  = s
            best_result = result
            best_params = params.copy()

    if not best_params:
        log(f"❌ No valid combinations found")
        return None

    log(f"  🏆 TotalPnL={best_result['total_pnl']}% WR={best_result['winrate']}% trades={best_result['trades']}")
    save_best_params(strategy_id, best_params, best_result)

    return {
        'symbol'   : symbol,
        'direction': direction,
        'timeframe': timeframe,
        'params'   : best_params,
        'result'   : best_result,
    }


run_auto_tuning = tune_strategy