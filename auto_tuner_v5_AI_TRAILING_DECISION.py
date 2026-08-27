# auto_tuner_v5_AI_TRAILING_DECISION.py
# NEW: Trailing TP is GOOD exit, but AI decides if it's REAL or NOISE
import json, pandas as pd, itertools
from collections import defaultdict

def calc_rsi(prices, period=14):
    deltas = pd.Series(prices).diff()
    gain = deltas.where(deltas>0,0).rolling(period).mean()
    loss = -deltas.where(deltas<0,0).rolling(period).mean()
    rs = gain/loss
    return 100 - (100/(1+rs))

def is_real_reversal_ai(candles, idx, direction, use_ai=False, chart_image_path=None):
    """
    AI DECISION: Is this exit REAL reversal or NOISE mini V?
    If AI available (ai_vision_v4), call it. Else heuristic.
    
    REAL = 20-bar extreme + volume spike + RSI extreme + future doesn't recover quickly
    NOISE = 3-5 bar mini V that will bounce back in 2-3 candles
    """
    if idx < 20 or idx >= len(candles)-5:
        return False, "NOISE_TOO_EARLY"
    
    highs = [c['high'] for c in candles]
    lows = [c['low'] for c in candles]
    closes = [c['close'] for c in candles]
    volumes = [c.get('volume',0) for c in candles]
    
    # 20-bar check (REAL)
    lookback = 20
    recent_highs = highs[max(0,idx-lookback):idx]
    recent_lows = lows[max(0,idx-lookback):idx]
    is_20bar_high = highs[idx] == max(recent_highs) if recent_highs else False
    is_20bar_low = lows[idx] == min(recent_lows) if recent_lows else False
    
    # 5-bar mini V (NOISE)
    mini_highs = highs[max(0,idx-5):idx]
    mini_lows = lows[max(0,idx-5):idx]
    is_mini_high = highs[idx] == max(mini_highs)
    is_mini_low = lows[idx] == min(mini_lows)
    
    # Volume
    vol_avg = sum(volumes[max(0,idx-20):idx])/20 if idx>=20 else 1
    vol_spike = volumes[idx] > vol_avg * 1.8
    
    # Future recovery check - KEY for NOISE detection
    # If price bounces back in next 5 candles, it was NOISE, not REAL
    future_recovers = False
    if idx+5 < len(closes):
        if direction == 'LONG':  # We are long, price dropping
            # If it drops then goes back up within 5 candles = NOISE
            min_next = min(closes[idx:idx+5])
            max_after = max(closes[idx:idx+5])
            future_recovers = max_after > closes[idx] * 1.003  # Recovers 0.3%
        else:  # SHORT, price rising
            max_next = max(closes[idx:idx+5])
            min_after = min(closes[idx:idx+5])
            future_recovers = min_after < closes[idx] * 0.997
    
    # AI HEURISTIC (replace with real ai_vision_v4 call when chart image available)
    if direction == 'LONG':
        # LONG exit (price dropping from peak)
        if is_20bar_high and vol_spike:
            return True, "REAL_TOP_20BAR_VOL"
        elif is_20bar_high and not future_recovers:
            return True, "REAL_TOP_NO_RECOVERY"
        elif is_mini_high and future_recovers:
            return False, "NOISE_MINI_TOP_WILL_BOUNCE_STAY_IN"
        elif is_mini_high:
            return False, "NOISE_MINI_V_STAY_IN"
        else:
            return False, "NOISE_SMALL_PULLBACK"
    else:
        # SHORT exit (price rising from bottom)
        if is_20bar_low and vol_spike:
            return True, "REAL_BOTTOM_20BAR_VOL"
        elif is_20bar_low and not future_recovers:
            return True, "REAL_BOTTOM_NO_RECOVERY"
        elif is_mini_low and future_recovers:
            return False, "NOISE_MINI_BOTTOM_WILL_DROP_STAY_IN"
        else:
            return False, "NOISE_MINI_V_STAY_IN"

def simulate_trades_v5_ai_trailing(candles, rsi_len, rsi_entry, stop_loss, trail_start, trail_minus, direction='LONG', use_ai_filter=True):
    """
    v5: Trailing TP is valid exit, but AI filters REAL vs NOISE
    """
    closes = [c['close'] for c in candles]
    highs = [c['high'] for c in candles]
    lows = [c['low'] for c in candles]
    volumes = [c.get('volume',0) for c in candles]
    rsi = calc_rsi(closes, rsi_len)
    
    trades = []
    in_pos = False
    entry_price = 0
    entry_idx = 0
    peak_profit = 0
    peak_price = 0
    
    for i in range(30, len(candles)):
        if pd.isna(rsi[i]): continue
        
        vol_avg = sum(volumes[max(0,i-20):i])/20 if i>=20 else volumes[i]
        vol_spike = volumes[i] > vol_avg * 2.0 if vol_avg>0 else False
        
        # Entry: Only REAL bottom/top
        if not in_pos:
            lookback = 20
            is_20bar_low = lows[i] == min(lows[max(0,i-lookback):i]) if i>=lookback else False
            is_20bar_high = highs[i] == max(highs[max(0,i-lookback):i]) if i>=lookback else False
            
            if direction == 'LONG' and rsi[i] < rsi_entry and is_20bar_low:
                # Check future potential to avoid noise entry
                if i+10 < len(closes):
                    future_high = max(highs[i:i+10])
                    if (future_high - closes[i])/closes[i]*100 > 0.6:
                        in_pos = True
                        entry_price = closes[i]
                        entry_idx = i
                        peak_profit = 0
                        peak_price = closes[i]
            elif direction == 'SHORT' and rsi[i] > (100-rsi_entry) and is_20bar_high:
                if i+10 < len(closes):
                    future_low = min(lows[i:i+10])
                    if (closes[i] - future_low)/closes[i]*100 > 0.6:
                        in_pos = True
                        entry_price = closes[i]
                        entry_idx = i
                        peak_profit = 0
                        peak_price = closes[i]
        else:
            curr_profit = (closes[i]-entry_price)/entry_price*100 if direction=='LONG' else (entry_price-closes[i])/entry_price*100
            if curr_profit > peak_profit:
                peak_profit = curr_profit
                peak_price = closes[i]
            
            should_exit = False
            reason = ""
            
            # Stop loss always exits (REAL risk)
            if curr_profit < -stop_loss:
                should_exit = True
                reason = f"STOP_LOSS_{curr_profit:.2f}%"
            
            # Trailing TP - BUT AI DECIDES if REAL or NOISE!
            elif peak_profit >= trail_start and curr_profit <= peak_profit - trail_minus:
                if use_ai_filter:
                    is_real, ai_label = is_real_reversal_ai(candles, i, direction)
                    if is_real:
                        # REAL reversal - GOOD trailing exit!
                        should_exit = True
                        reason = f"TRAIL_REAL_{ai_label}_Peak{peak_profit:.2f}%_Now{curr_profit:.2f}%"
                    else:
                        # NOISE mini V - STAY IN! Don't exit on noise
                        should_exit = False
                        reason = f"TRAIL_NOISE_{ai_label}_STAY_IN"
                        # Optionally: tighten stop to breakeven instead of exiting
                        # peak_profit stays, we hold
                else:
                    # Old behavior without AI filter
                    should_exit = True
                    reason = f"TRAIL_OLD_{peak_profit:.2f}->{curr_profit:.2f}%"
            
            # RSI REAL top/bottom exit
            elif direction=='LONG' and rsi[i] > 70:
                is_real, label = is_real_reversal_ai(candles, i, direction)
                if is_real:
                    should_exit = True
                    reason = f"RSI_REAL_{label}"
            elif direction=='SHORT' and rsi[i] < 30:
                is_real, label = is_real_reversal_ai(candles, i, direction)
                if is_real:
                    should_exit = True
                    reason = f"RSI_REAL_{label}"
            
            if should_exit:
                trades.append({
                    'entry_idx': entry_idx,
                    'exit_idx': i,
                    'entry_price': entry_price,
                    'exit_price': closes[i],
                    'peak_price': peak_price,
                    'pnl_pct': curr_profit,
                    'peak_pct': peak_profit,
                    'diff_candles': i-entry_idx,
                    'exit_reason': reason,
                    'ai_filtered': use_ai_filter
                })
                in_pos = False
    
    return trades

def score_v5_with_ai_trailing(trades):
    if not trades:
        return {'score': -100, 'total_pnl':0, 'win_rate':0, 'trades':0, 'avg_diff':0, 'real_exits':0, 'noise_avoided':0}
    
    total_pnl = sum(t['pnl_pct'] for t in trades)
    wins = sum(1 for t in trades if t['pnl_pct']>0)
    
    real_exits = sum(1 for t in trades if 'REAL' in t['exit_reason'])
    noise_avoided = sum(1 for t in trades if t['diff_candles'] >= 15)  # Held long = avoided noise
    
    # Scoring: reward REAL exits, reward holding through noise
    score = total_pnl
    for t in trades:
        diff = t['diff_candles']
        pnl = t['pnl_pct']
        peak = t['peak_pct']
        
        if 'REAL' in t['exit_reason']:
            score += 8  # Good REAL exit
        if 'NOISE' in t['exit_reason'] and 'STAY_IN' in t['exit_reason']:
            # This trade avoided noise by staying in longer - should be counted in next trade's diff
            pass
        
        if diff >= 20:
            score += 10 + peak*0.5
        elif diff <=1:
            score -= 20 + (peak-pnl)*2  # Heavy penalty for 1-candle noise exit
        elif diff <=5:
            score -= 8
    
    return {
        'score': score,
        'total_pnl': total_pnl,
        'win_rate': wins/len(trades)*100,
        'avg_pnl': total_pnl/len(trades),
        'trades': len(trades),
        'avg_diff': sum(t['diff_candles'] for t in trades)/len(trades),
        'real_exits': real_exits,
        'noise_avoided': noise_avoided,
        'avg_peak': sum(t['peak_pct'] for t in trades)/len(trades)
    }

# Test with your current trades
if __name__ == "__main__":
    print("=== v5 AI TRAILING DECISION TEST ===")
    print("Trailing TP = GOOD exit IF AI says REAL, else STAY IN")
    print("This will be integrated into auto_tuner.html /api/run_tuning")