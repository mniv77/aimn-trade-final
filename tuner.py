import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
import time

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
SYMBOL = 'BTC/USDT'
TIMEFRAME = '15m'
LIMIT = 1000  # Number of candles to test (Backtest depth)
TRADE_MODE = 'SELL'  # 'BUY' or 'SELL'

# ==========================================
# 📥 1. FETCH DATA
# ==========================================
def get_data():
    print(f"📥 Fetching {LIMIT} candles for {SYMBOL}...")
    exchange = ccxt.binance()
    bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=LIMIT)
    df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    return df

# ==========================================
# 🧠 2. STRATEGY ENGINE (Replicates V7.9)
# ==========================================
def run_strategy(df, rsi_len, macd_fast, macd_slow, macd_sig, 
                 entry_rsi_level, stop_loss_pct, trail_start_pct, 
                 decay_start_hr, decay_rate, init_profit):
    
    # --- Indicators ---
    # We use .copy() to avoid SettingWithCopy warnings during loops
    d = df.copy()
    
    # RSI
    d['rsi'] = ta.rsi(d['close'], length=rsi_len)
    
    # MACD
    macd = ta.macd(d['close'], fast=macd_fast, slow=macd_slow, signal=macd_sig)
    d['macd'] = macd[f'MACD_{macd_fast}_{macd_slow}_{macd_sig}']
    d['signal'] = macd[f'MACDs_{macd_fast}_{macd_slow}_{macd_sig}']

    # --- Backtest Loop ---
    balance = 1000.0
    in_position = False
    entry_price = 0.0
    entry_time = None
    trades = 0
    wins = 0
    
    # Pre-calculate crossovers to speed up loop
    d['macd_cross_up'] = (d['macd'] > d['signal']) & (d['macd'].shift(1) < d['signal'].shift(1))
    d['macd_cross_down'] = (d['macd'] < d['signal']) & (d['macd'].shift(1) > d['signal'].shift(1))

    for i in range(1, len(d)):
        row = d.iloc[i]
        
        # --- ENTRY LOGIC ---
        if not in_position:
            if TRADE_MODE == 'BUY':
                if row['rsi'] < entry_rsi_level and row['macd_cross_up']:
                    in_position = True
                    entry_price = row['close']
                    entry_time = row['time']
            
            elif TRADE_MODE == 'SELL':
                if row['rsi'] > entry_rsi_level and row['macd_cross_down']:
                    in_position = True
                    entry_price = row['close']
                    entry_time = row['time']

        # --- EXIT LOGIC ---
        elif in_position:
            # 1. Calculate Duration (Hours) for Decay
            duration_hr = (row['time'] - entry_time).total_seconds() / 3600
            
            # 2. Calculate Required Profit (Decay Logic)
            elapsed_decay = max(0, duration_hr - decay_start_hr)
            current_req = max(0.0, init_profit - (elapsed_decay * decay_rate))
            
            # 3. Calculate P&L %
            if TRADE_MODE == 'BUY':
                pnl_pct = ((row['close'] - entry_price) / entry_price) * 100
            else:
                pnl_pct = ((entry_price - row['close']) / entry_price) * 100
            
            profit_met = pnl_pct >= current_req

            # 4. Triggers (Stop Loss OR Target Met)
            # (Simplified: If we hit profit target OR stop loss, we exit)
            
            # Check Stop Loss
            if pnl_pct <= -stop_loss_pct:
                in_position = False
                balance -= (balance * (stop_loss_pct/100))
                trades += 1
            
            # Check Profit (with Trailing assumption: if we hit target, we take it)
            elif profit_met:
                in_position = False
                # Assume we capture the required profit (conservative)
                balance += (balance * (current_req/100))
                trades += 1
                wins += 1

    win_rate = (wins / trades * 100) if trades > 0 else 0
    return balance, trades, win_rate

# ==========================================
# 🚀 3. THE OPTIMIZER (Grid Search)
# ==========================================
def optimize():
    df = get_data()
    
    print(f"\n🚀 STARTING OPTIMIZATION FOR {TRADE_MODE} MODE...")
    print("Testing combinations... (This might take a moment)\n")
    
    best_score = -9999
    best_params = {}
    
    # --- 🎛️ TUNING RANGES ---
    # These are the knobs the script will twist for you
    
    rsi_levels = [25, 30, 35, 70, 75] if TRADE_MODE == 'BUY' else [65, 70, 75, 80]
    stop_losses = [1.5, 2.0, 2.5, 3.0]
    decay_starts = [1.0, 2.0, 4.0]
    
    # We loop through every combination
    for rsi_lvl in rsi_levels:
        for sl in stop_losses:
            for decay in decay_starts:
                
                # Run the strategy with these specific numbers
                final_bal, trades, win_rate = run_strategy(
                    df, 
                    rsi_len=100, 
                    macd_fast=12, macd_slow=26, macd_sig=9,
                    entry_rsi_level=rsi_lvl, 
                    stop_loss_pct=sl, 
                    trail_start_pct=5.0, # Fixed for simplicity
                    decay_start_hr=decay, 
                    decay_rate=0.5, 
                    init_profit=3.0
                )
                
                # Scoring: We want high profit AND decent activity (> 5 trades)
                score = final_bal if trades > 5 else 0
                
                print(f"Testing: RSI {rsi_lvl} | SL {sl}% | Decay {decay}h -> P&L: ${final_bal:.2f} ({trades} trades)")
                
                if score > best_score:
                    best_score = score
                    best_params = {
                        'RSI Level': rsi_lvl,
                        'Stop Loss': sl,
                        'Decay Start': decay,
                        'Final Balance': final_bal,
                        'Win Rate': win_rate,
                        'Trades': trades
                    }

    # ==========================================
    # 🏆 4. FINAL REPORT
    # ==========================================
    print("\n" + "="*40)
    print(f"🏆 BEST {TRADE_MODE} SETTINGS FOUND")
    print("="*40)
    print(f"💰 Final Balance: ${best_params['Final Balance']:.2f} (from $1000)")
    print(f"📈 Win Rate:      {best_params['Win Rate']:.1f}%")
    print(f"🔢 Total Trades:  {best_params['Trades']}")
    print("-" * 40)
    print(f"✅ RSI Trigger:   {best_params['RSI Level']}")
    print(f"✅ Stop Loss:     {best_params['Stop Loss']}%")
    print(f"✅ Decay Start:   {best_params['Decay Start']} hours")
    print("="*40)

if __name__ == "__main__":
    optimize()