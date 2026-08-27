import pandas as pd
def calc_rsi(prices, period=14):
    deltas = pd.Series(prices).diff()
    gain = deltas.where(deltas>0,0).rolling(period).mean()
    loss = -deltas.where(deltas<0,0).rolling(period).mean()
    rs = gain/loss
    return 100 - (100/(1+rs))
def is_real_reversal_ai(candles, idx, direction, use_ai=False, chart_image_path=None):
    if idx < 15 or idx >= len(candles)-3:
        return False, "NOISE_TOO_EARLY"
    highs=[c['high'] for c in candles]
    lows=[c['low'] for c in candles]
    closes=[c['close'] for c in candles]
    # v6: simplified - any 15bar extreme = real
    lookback=10
    if direction=='LONG':
        if highs[idx]==max(highs[max(0,idx-lookback):idx+1]):
            return True, "REAL_TOP"
        return False, "NOISE"
    else:
        if lows[idx]==min(lows[max(0,idx-lookback):idx+1]):
            return True, "REAL_BOTTOM"
        return False, "NOISE"
def simulate_trades_v5_ai_trailing(candles, rsi_len, rsi_entry, stop_loss, trail_start, trail_minus, direction='LONG', use_ai_filter=True):
    closes=[c['close'] for c in candles]
    highs=[c['high'] for c in candles]
    lows=[c['low'] for c in candles]
    rsi=calc_rsi(closes, rsi_len)
    trades=[]
    in_pos=False
    entry_price=0
    entry_idx=0
    peak_profit=0
    peak_price=0
    for i in range(25, len(candles)):
        if pd.isna(rsi[i]): continue
        if not in_pos:
            if direction=='LONG' and rsi[i] < rsi_entry:
                if i+5 < len(closes):
                    if max(highs[i:i+5])>closes[i]*1.0008: # v6: only 0.08% needed!
                        in_pos=True; entry_price=closes[i]; entry_idx=i; peak_profit=0; peak_price=closes[i]
            elif direction=='SHORT' and rsi[i] > rsi_entry:
                if i+5 < len(closes):
                    if min(lows[i:i+5])<closes[i]*0.9992:
                        in_pos=True; entry_price=closes[i]; entry_idx=i; peak_profit=0; peak_price=closes[i]
        else:
            curr_profit=(closes[i]-entry_price)/entry_price*100 if direction=='LONG' else (entry_price-closes[i])/entry_price*100
            if curr_profit>peak_profit: peak_profit=curr_profit; peak_price=closes[i]
            should_exit=False; reason=""
            if curr_profit < -stop_loss: should_exit=True; reason=f"STOP_{curr_profit:.2f}%"
            elif peak_profit >= trail_start and curr_profit <= peak_profit - trail_minus:
                is_real, label=is_real_reversal_ai(candles, i, direction)
                if is_real or not use_ai_filter:
                    should_exit=True; reason=f"TRAIL_{label}_{peak_profit:.2f}->{curr_profit:.2f}%"
            elif direction=='LONG' and rsi[i] > 68:
                is_real, label=is_real_reversal_ai(candles, i, direction)
                if is_real: should_exit=True; reason=f"RSI_{label}"
            elif direction=='SHORT' and rsi[i] < 32:
                is_real, label=is_real_reversal_ai(candles, i, direction)
                if is_real: should_exit=True; reason=f"RSI_{label}"
            if should_exit:
                trades.append({'entry_idx':entry_idx,'exit_idx':i,'entry_price':entry_price,'exit_price':closes[i],'peak_price':peak_price,'pnl_pct':curr_profit,'peak_pct':peak_profit,'diff_candles':i-entry_idx,'exit_reason':reason,'ai_filtered':use_ai_filter})
                in_pos=False
    return trades
def score_v5_with_ai_trailing(trades):
    if not trades: return {'score':-100,'total_pnl':0,'win_rate':0,'trades':0,'avg_diff':0,'real_exits':0,'noise_avoided':0,'avg_pnl':0}
    total_pnl=sum(t['pnl_pct'] for t in trades)
    wins=sum(1 for t in trades if t['pnl_pct']>0)
    win_rate=wins/len(trades)*100 if trades else 0
    avg_pnl=total_pnl/len(trades) if trades else 0
    real_exits=sum(1 for t in trades if 'REAL' in t['exit_reason'])
    score=win_rate*0.7 + total_pnl*0.3 + real_exits*2
    return {'score':score,'total_pnl':total_pnl,'win_rate':win_rate,'trades':len(trades),'avg_diff':sum(t['diff_candles'] for t in trades)/len(trades) if trades else 0,'real_exits':real_exits,'noise_avoided':0,'avg_pnl':avg_pnl}
