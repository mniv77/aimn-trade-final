import os
import sys
import json
import traceback
from datetime import datetime
from sqlalchemy import text
import pandas as pd
from collections import defaultdict

# Import your AI Vision Modules
try:
    from ai_vision_check import check_reversal
    AI_VISION_AVAILABLE = True
except ImportError:
    AI_VISION_AVAILABLE = False

try:
    from ai_vision_tuner_validator import validate_strategy, generate_entry_chart, find_entry_points
    AI_VALIDATOR_AVAILABLE = True
except ImportError:
    AI_VALIDATOR_AVAILABLE = False


def calc_rsi_real(highs, lows, closes, i, period=14):
    """
    RSI Real specification: Looks back in history (14) for max price = 100 units
    and min price = 0 units, and evaluates like regular RSI on real scaled prices.
    """
    start_idx = max(0, i - period)
    window_highs = highs[start_idx:i+1]
    window_lows = lows[start_idx:i+1]
    window_closes = closes[start_idx:i+1]

    if len(window_closes) < 2:
        return 50.0

    max_price = max(window_highs) if window_highs else 100.0
    min_price = min(window_lows) if window_lows else 0.0

    if max_price == min_price:
        return 50.0

    scaled_closes = [(c - min_price) / (max_price - min_price) * 100.0 for c in window_closes]

    deltas = [scaled_closes[idx] - scaled_closes[idx-1] for idx in range(1, len(scaled_closes))]
    if not deltas:
        return 50.0

    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_macd_series(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow:
        return [0]*len(closes), [0]*len(closes)

    def ema(data, period):
        multiplier = 2 / (period + 1)
        ema_list = [data[0]]
        for val in data[1:]:
            ema_list.append((val - ema_list[-1]) * multiplier + ema_list[-1])
        return ema_list

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line


def evaluate_auto_tuner(
    symbol,
    highs,
    lows,
    closes,
    timestamps,
    strategy_id=None,
    direction="LONG",
    params=None,
    use_ai_validation=True
):
    if params is None:
        params = {
            'rsi_len': 14,
            'rsi_entry': 25,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_sig': 9
        }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Running Auto-Tuner for {symbol} ({direction})")

    if AI_VALIDATOR_AVAILABLE and use_ai_validation and strategy_id:
        score, validated = validate_strategy(
            strategy_id=strategy_id,
            symbol=symbol,
            direction=direction,
            highs=highs,
            lows=lows,
            closes=closes,
            timestamps=timestamps,
            params=params
        )
        return {
            "status": "success",
            "symbol": symbol,
            "direction": direction,
            "ai_validated": validated,
            "ai_score": score
        }
    else:
        entries = []
        rsi_len = params.get('rsi_len', 14)
        rsi_entry = params.get('rsi_entry', 25)

        for i in range(rsi_len + 5, len(closes) - 1):
            rsi_val = calc_rsi_real(highs, lows, closes, i, rsi_len)

            ai_override = False
            if AI_VISION_AVAILABLE:
                temp_chart = generate_entry_chart(symbol, highs, lows, closes, timestamps, i, n_candles=60)
                if temp_chart and os.path.exists(temp_chart):
                    res = check_reversal(temp_chart, symbol, direction)
                    if res.get("verdict") == "CONFIRMED":
                        ai_override = True
                    try:
                        os.remove(temp_chart)
                    except:
                        pass

            if ai_override:
                entries.append({"bar": i, "trigger": "AI_REVERSAL_OVERRIDE"})
            elif direction == "LONG" and rsi_val <= rsi_entry:
                entries.append({"bar": i, "trigger": "NUMERIC_RSI_FALLBACK"})
            elif direction == "SHORT" and rsi_val >= (100 - rsi_entry):
                entries.append({"bar": i, "trigger": "NUMERIC_RSI_FALLBACK"})

        return {
            "status": "success",
            "symbol": symbol,
            "direction": direction,
            "total_entries": len(entries),
            "entries": entries
        }


def print_best_results(symbol, direction, timeframe, closes, best_params, win_rate_val, avg_pnl_val, trades_val, total_pnl_val, breakdown, best_stats):
    # If variables are None or string "undefined", fallback safely
    symbol = str(symbol) if symbol and symbol != "undefined" else "N/A"
    direction = str(direction) if direction and direction != "undefined" else "LONG"
    timeframe = str(timeframe) if timeframe and timeframe != "undefined" else "1h"
    
    if not best_params:
        best_params = {}
    if not breakdown:
        breakdown = {"STOP": 0, "TRAIL": 0, "DECAY": 0, "RSI": 0}
        
    trades_val = trades_val if trades_val is not None and trades_val != "undefined" else 0
    win_rate_val = win_rate_val if win_rate_val is not None and win_rate_val != "undefined" else 0.0
    avg_pnl_val = avg_pnl_val if avg_pnl_val is not None and avg_pnl_val != "undefined" else 0.0
    total_pnl_val = total_pnl_val if total_pnl_val is not None and total_pnl_val != "undefined" else 0.0

    def get_pct(count):
        try:
            return f"{(float(count) / float(trades_val) * 100):.1f}" if float(trades_val) > 0 else "0.0"
        except:
            return "0.0"

    current_candle_count = len(closes) if closes is not None else 0

    print("🏆  BEST PARAMETERS FOUND")
    print("────────────────────────────────────────────────────")
    print(f"Symbol     : {symbol}")
    print(f"Direction  : {direction}")
    print(f"Timeframe  : {timeframe}")
    print(f"Candle Count: {current_candle_count}")
    print("────────────────────────────────────────────────────")
    print(f"RSI Lookbk : {best_params.get('rsi_len', 14)} bars")
    print(f"RSI Entry  : {best_params.get('rsi_entry', 20)}")
    print(f"Stop Loss  : {best_params.get('stop_loss', 1.5)}%")
    print(f"Trail Start: {best_params.get('trail_start', 0)}%")
    print(f"Trail Drop : {best_params.get('trail_drop', 0)}%")
    print(f"Init Profit: {best_params.get('init_profit', 0)}%")
    print(f"Decay Start: {best_params.get('decay_start', 0)}h")
    print("────────────────────────────────────────────────────")
    try:
        print(f"Win Rate   : {float(win_rate_val):.1f}%")
        print(f"Avg PnL    : {float(avg_pnl_val):.2f}%")
        print(f"Trades     : {int(trades_val)}")
        print(f"Total PnL  : {float(total_pnl_val):.2f}%")
    except:
        print(f"Win Rate   : {win_rate_val}%")
        print(f"Avg PnL    : {avg_pnl_val}%")
        print(f"Trades     : {trades_val}")
        print(f"Total PnL  : {total_pnl_val}%")
    print("────────────────────────────────────────────────────")
    print("📊 EXIT BREAKDOWN")
    print(f"STOP Loss  : {breakdown.get('STOP', 0)} trades ({get_pct(breakdown.get('STOP', 0))}%)")
    print(f"TRAIL Exit : {breakdown.get('TRAIL', 0)} trades ({get_pct(breakdown.get('TRAIL', 0))}%)")
    print(f"DECAY Exit : {breakdown.get('DECAY', 0)} trades ({get_pct(breakdown.get('DECAY', 0))}%)")
    print(f"RSI Exit   : {breakdown.get('RSI', 0)} trades ({get_pct(breakdown.get('RSI', 0))}%)")
    print("────────────────────────────────────────────────────")
    print("✅ Saved to strategy_params")

    return {
        "symbol": symbol,
        "direction": direction,
        "timeframe": timeframe,
        "candle_count": current_candle_count,
        "params": best_params,
        "result": best_stats
    }


def tune_strategy_original(symbol, direction, timeframe, closes, highs, lows):
    try:
        if hasattr(closes, "tolist"): closes = closes.tolist()
        if hasattr(highs, "tolist"): highs = highs.tolist()
        if hasattr(lows, "tolist"): lows = lows.tolist()

        best_score = float('-inf')
        best_params = {
            "rsi_len": 14,
            "rsi_entry": 30,
            "stop_loss": 1.5,
            "trail_start": 1.0,     # Give it at least 1% room before trailing starts
            "trail_drop": "0.5%",
            "init_profit": 0.5,     # Require at least 1.5% initial profit target
            "decay_start": 0
        }
        best_stats = {
            "winrate": "0.0",
            "avg_pnl": "0.00",
            "trades": 0,
            "total_pnl": "0.00",
            "exit_breakdown": {"STOP": 0, "TRAIL": 0, "DECAY": 0, "RSI": 0}
        }

        if not closes or not highs or not lows or len(closes) < 10:
            return best_params, best_stats

        max_len = len(closes)
        trades_count = 0
        wins = 0
        total_pnl = 0.0
        exit_breakdown = {"STOP": 0, "TRAIL": 0, "DECAY": 0, "RSI": 0}

        i = 2
        while i < max_len - 1:
            if i + 1 >= max_len:
                break

            is_pivot_entry = False
            if direction == "LONG":
                if lows[i] < lows[i-1] and lows[i] <= lows[i+1]:
                    is_pivot_entry = True
            else:
                if highs[i] > highs[i-1] and highs[i] >= highs[i+1]:
                    is_pivot_entry = True

            if is_pivot_entry:
                trades_count += 1
                entry_p = closes[i]
                exited = False
                next_bar_idx = min(i + 30, max_len)

                for j in range(i + 1, next_bar_idx):
                    if j >= max_len:
                        break

                    curr_p = closes[j]
                    if direction == "LONG":
                        pnl_pct = ((curr_p - entry_p) / entry_p) * 100
                        if pnl_pct <= -3.0:
                            total_pnl += pnl_pct
                            exit_breakdown["STOP"] += 1
                            exited = True
                            break

                        if j > i + 2 and (j + 1) < max_len and highs[j] > highs[j-1] and highs[j] >= highs[j+1]:
                            total_pnl += pnl_pct
                            if pnl_pct > 0:
                                wins += 1
                                exit_breakdown["TRAIL"] += 1
                            else:
                                exit_breakdown["STOP"] += 1
                            exited = True
                            break
                    else:
                        pnl_pct = ((entry_p - curr_p) / entry_p) * 100
                        if pnl_pct <= -3.0:
                            total_pnl += pnl_pct
                            exit_breakdown["STOP"] += 1
                            exited = True
                            break

                        if j > i + 2 and (j + 1) < max_len and lows[j] < lows[j-1] and lows[j] <= lows[j+1]:
                            total_pnl += pnl_pct
                            if pnl_pct > 0:
                                wins += 1
                                exit_breakdown["TRAIL"] += 1
                            else:
                                exit_breakdown["STOP"] += 1
                            exited = True
                            break

                if not exited:
                    final_p = closes[min(i + 29, max_len - 1)]
                    pnl_pct = ((final_p - entry_p) / entry_p) * 100 if direction == "LONG" else ((entry_p - final_p) / entry_p) * 100
                    total_pnl += pnl_pct
                    if pnl_pct > 0:
                        wins += 1
                        exit_breakdown["TRAIL"] += 1
                    else:
                        exit_breakdown["STOP"] += 1

                i = next_bar_idx
            else:
                i += 1

        winrate = (wins / trades_count * 100) if trades_count > 0 else 0

        if trades_count > 0:
            best_stats = {
                "winrate": f"{winrate:.1f}",
                "avg_pnl": f"{(total_pnl / trades_count):.2f}",
                "trades": trades_count,
                "total_pnl": f"{total_pnl:.2f}",
                "exit_breakdown": exit_breakdown
            }

        return best_params, best_stats

    except Exception as e:
        print(f"Tune Strategy Exception: {str(e)}")
        return {
            "rsi_len": 14, "rsi_entry": 40, "stop_loss": 3.0,
            "trail_start": 0.5, "trail_drop": "0.5%", "init_profit": 0, "decay_start": 0
        }, {
            "winrate": "0.0", "avg_pnl": "0.00", "trades": 0,
            "total_pnl": "0.00", "exit_breakdown": {"STOP": 0, "TRAIL": 0, "DECAY": 0, "RSI": 0}
        }


# ==========================================
# 1. RUN ANALYSIS
# ==========================================
def run_analysis():
    """Analyze trade history and return recommendations and stats"""
    try:
        if not os.path.exists('aimn_trades.json'):
            return {"error": "aimn_trades.json not found.", "total_trades": 0, "win_rate": 0, "trades": []}

        with open('aimn_trades.json', 'r') as f:
            content = f.read().strip()
            if not content:
                return {"error": "aimn_trades.json is empty.", "total_trades": 0, "win_rate": 0, "trades": []}

            if content.startswith('['):
                trades = json.loads(content)
            else:
                trades = []
                for line in content.splitlines():
                    line = line.strip()
                    if line:
                        try:
                            trades.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
    except FileNotFoundError:
        return {"error": "aimn_trades.json not found.", "total_trades": 0, "win_rate": 0, "trades": []}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON format in aimn_trades.json: {str(e)}", "total_trades": 0, "win_rate": 0, "trades": []}

    if not trades:
        return {"error": "No trades recorded yet.", "total_trades": 0, "win_rate": 0, "trades": []}

    total_trades = len(trades)
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "trades": trades
    }



# ==========================================
#  CALCULATE WILDER RSI
# ==========================================

def calc_wilder_rsi(closes, period=14):
    """Standard Wilder's RSI calculation."""
    if len(closes) < period + 1:
        return 50.0

    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    # Initial averages
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder smoothing for the rest
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ==========================================
# STRUCTURAL PIVOT ENTRY TUNE STRATEGY
# ==========================================


def tune_strategy(strategy_id_or_symbol, symbol_or_direction=None, direction_or_timeframe=None, cfg=None, broker_name=None, closes=None, highs=None, lows=None, timeframe=None):
    try:
        if cfg is not None:
            strategy_id = strategy_id_or_symbol
            symbol = symbol_or_direction
            direction = direction_or_timeframe
        else:
            symbol = strategy_id_or_symbol
            direction = symbol_or_direction
            timeframe = direction_or_timeframe

        best_params = {
            "rsi_len": 14,
            "rsi_entry": 30,
            "stop_loss": 3.0,
            "trail_start": 0.5,
            "trail_drop": "0.5%",
            "init_profit": 0,
            "decay_start": 0
        }

        best_stats = {
            "winrate": "0.0",
            "avg_pnl": "0.00",
            "trades": 0,
            "total_pnl": "0.00",
            "exit_breakdown": {"STOP": 0, "TRAIL": 0, "DECAY": 0, "RSI": 0}
        }

        if closes is not None:
            if hasattr(closes, "tolist"): closes = closes.tolist()
            if hasattr(highs, "tolist"): highs = highs.tolist()
            if hasattr(lows, "tolist"): lows = lows.tolist()

            # --- NO MORE GUESSING: Print exact candle counts directly to logs ---
            c_len = len(closes) if closes else 0
            h_len = len(highs) if highs else 0
            l_len = len(lows) if lows else 0
            print(f"[TUNE_STRATEGY DEBUG] Symbol: {symbol} | Direction: {direction} | Candles Received -> Closes: {c_len}, Highs: {h_len}, Lows: {l_len}")

            if not closes or not highs or not lows or len(closes) < 20:
                print(f"[TUNE_STRATEGY WARNING] Aborting backtest: Insufficient or empty candle arrays.")
                return best_params, best_stats

            max_len = len(closes)
            trades_count = 0
            wins = 0
            total_pnl = 0.0
            exit_breakdown = {"STOP": 0, "TRAIL": 0, "DECAY": 0, "RSI": 0}

            rsi_len = best_params.get("rsi_len", 14)
            rsi_entry = best_params.get("rsi_entry", 30)

            i = rsi_len + 1
            while i < max_len - 1:
                sub_closes = closes[:i+1]
                rsi_val = calc_rsi_real(highs, lows, closes, i, rsi_len)

                is_entry = False
                if direction == "LONG":
                    if rsi_val <= rsi_entry:
                        is_entry = True
                else:  # SHORT
                    if rsi_val >= (100 - rsi_entry):
                        is_entry = True

                if is_entry:
                    trades_count += 1
                    entry_p = closes[i]
                    exited = False
                    next_bar_idx = min(i + 30, max_len)

                    for j in range(i + 1, next_bar_idx):
                        if j >= max_len:
                            break

                        curr_p = closes[j]
                        if direction == "LONG":
                            pnl_pct = ((curr_p - entry_p) / entry_p) * 100
                            if pnl_pct <= -3.0:
                                total_pnl += pnl_pct
                                exit_breakdown["STOP"] += 1
                                exited = True
                                break

                            if j > i + 2 and (j + 1) < max_len and highs[j] > highs[j-1] and highs[j] >= highs[j+1]:
                                total_pnl += pnl_pct
                                if pnl_pct > 0:
                                    wins += 1
                                    exit_breakdown["TRAIL"] += 1
                                else:
                                    exit_breakdown["STOP"] += 1
                                exited = True
                                break
                        else:
                            pnl_pct = ((entry_p - curr_p) / entry_p) * 100
                            if pnl_pct <= -3.0:
                                total_pnl += pnl_pct
                                exit_breakdown["STOP"] += 1
                                exited = True
                                break

                            if j > i + 2 and (j + 1) < max_len and lows[j] < lows[j-1] and lows[j] <= lows[j+1]:
                                total_pnl += pnl_pct
                                if pnl_pct > 0:
                                    wins += 1
                                    exit_breakdown["TRAIL"] += 1
                                else:
                                    exit_breakdown["STOP"] += 1
                                exited = True
                                break

                    if not exited:
                        final_p = closes[min(i + 29, max_len - 1)]
                        pnl_pct = ((final_p - entry_p) / entry_p) * 100 if direction == "LONG" else ((entry_p - final_p) / entry_p) * 100
                        total_pnl += pnl_pct
                        if pnl_pct > 0:
                            wins += 1
                            exit_breakdown["TRAIL"] += 1
                        else:
                            exit_breakdown["STOP"] += 1

                    i = next_bar_idx
                else:
                    i += 1

            # Fallback if 0 trades: if threshold was too strict, flag it in logs
            if trades_count == 0:
                print(f"[TUNE_STRATEGY WARNING] 0 trades found using RSI entry threshold {rsi_entry}. Price action never crossed the threshold.")

            winrate = (wins / trades_count * 100) if trades_count > 0 else 0

            if trades_count > 0:
                best_stats = {
                    "winrate": f"{winrate:.1f}",
                    "avg_pnl": f"{(total_pnl / trades_count):.2f}",
                    "trades": trades_count,
                    "total_pnl": f"{total_pnl:.2f}",
                    "exit_breakdown": exit_breakdown
                }

        return best_params, best_stats

    except Exception as e:
        print(f"tune_strategy exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "rsi_len": 14, "rsi_entry": 30, "stop_loss": 3.0,
            "trail_start": 0.5, "trail_drop": "0.5%", "init_profit": 0, "decay_start": 0
        }, {
            "winrate": "0.0", "avg_pnl": "0.00", "trades": 0,
            "total_pnl": "0.00", "exit_breakdown": {"STOP": 0, "TRAIL": 0, "DECAY": 0, "RSI": 0}
        }

if __name__ == "__main__":
    print("Auto-Tuner with Integrated AI Reversal Priority ready.")