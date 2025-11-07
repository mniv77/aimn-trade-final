#!/usr/bin/env python3
# File: template/aimn_strategy.py
# Description: Manual tuning framework for AImn auto trade strategy

import pandas as pd
import ta
import sys

# === USER CONFIG AREA ===

# File path to your OHLCV data (CSV)
DATA_FILE = 'data.csv'  # Replace with the path to your file

# Test buy or sell only
TRADE_DIRECTION = 'buy'  # 'buy' or 'sell'

# Strategy parameters (example defaults)
PARAMS = {
    'rsi_type': 'wilder',   # 'wilder' or 'RSIReal'
    'rsi_period': 14,
    'rsi_entry_threshold': 30 if TRADE_DIRECTION == 'buy' else 70,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'volume_enabled': True,
    'volume_threshold': 1000,
    'atr_enabled': True,
    'atr_period': 14,
    # Trailing exit
    'early_start_trailing': 0.01,
    'early_trailing_minus': 0.005,
    'peak_trigger_profit': 0.03,
    'peak_trailing_minus': 0.01,
    # Stop loss
    'stop_loss': 0.02,
    # RSI exit
    'rsi_exit': 70 if TRADE_DIRECTION == 'buy' else 30,
    # Min profit to exit
    'min_exit_profit': 0.005
}

# === END USER CONFIG ===

def load_data(filepath):
    try:
        df = pd.read_csv(filepath, parse_dates=['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        return df
    except Exception as e:
        print("ERROR: Could not load data file:", filepath)
        print(e)
        sys.exit(1)

def calc_indicators(df):
    # RSI
    if PARAMS['rsi_type'] == 'wilder':
        df['rsi'] = ta.momentum.RSIIndicator(df['Close'], window=PARAMS['rsi_period']).rsi()
    else:
        # RSIReal: 0 at min, 100 at max, else linearly scaled
        minp, maxp = df['Close'].min(), df['Close'].max()
        df['rsi'] = (df['Close'] - minp) / (maxp - minp) * 100

    # MACD
    macd = ta.trend.MACD(
        close=df['Close'],
        window_slow=PARAMS['macd_slow'],
        window_fast=PARAMS['macd_fast'],
        window_sign=PARAMS['macd_signal']
    )
    df['macd'] = macd.macd() if TRADE_DIRECTION == 'buy' else -macd.macd()
    df['macd_signal'] = macd.macd_signal()

    # Volume
    df['volume_ok'] = True
    if PARAMS['volume_enabled']:
        df['volume_ok'] = df['Volume'] > PARAMS['volume_threshold']

    # ATR
    df['atr_ok'] = True
    if PARAMS['atr_enabled']:
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            window=PARAMS['atr_period']
        ).average_true_range()
        df['atr_ok'] = df['atr'] > 0

    return df

def strategy(df):
    trades = []
    in_trade = False
    entry_idx = None
    entry_price = 0.0
    peak_price = 0.0
    for i, row in df.iterrows():
        # ENTRY LOGIC
        if not in_trade:
            entry_signal = (
                (row['rsi'] < PARAMS['rsi_entry_threshold'] if TRADE_DIRECTION == 'buy'
                 else row['rsi'] > PARAMS['rsi_entry_threshold'])
                and ((row['macd'] > row['macd_signal']) if TRADE_DIRECTION == 'buy' else (row['macd'] < row['macd_signal']))
                and row['volume_ok']
                and row['atr_ok']
            )
            if entry_signal:
                in_trade = True
                entry_idx = i
                entry_price = row['Close']
                peak_price = entry_price
        else:
            # Update peak price
            if TRADE_DIRECTION == 'buy':
                peak_price = max(peak_price, row['Close'])
                profit = (row['Close'] - entry_price) / entry_price
            else:
                peak_price = min(peak_price, row['Close'])
                profit = (entry_price - row['Close']) / entry_price

            # EXIT LOGIC
            can_exit = profit >= PARAMS['min_exit_profit']

            # Trailing logic (early/peak)
            if profit >= PARAMS['early_start_trailing']:
                if profit < PARAMS['peak_trigger_profit']:
                    # Early trailing
                    trailing_stop = peak_price * (1 - PARAMS['early_trailing_minus'] if TRADE_DIRECTION == 'buy'
                                                 else 1 + PARAMS['early_trailing_minus'])
                else:
                    # Peak trailing
                    trailing_stop = peak_price * (1 - PARAMS['peak_trailing_minus'] if TRADE_DIRECTION == 'buy'
                                                 else 1 + PARAMS['peak_trailing_minus'])
                trailing_exit = (row['Close'] < trailing_stop) if TRADE_DIRECTION == 'buy' else (row['Close'] > trailing_stop)
            else:
                trailing_exit = False

            # Stop loss
            stop_exit = profit <= -PARAMS['stop_loss']

            # RSI exit
            rsi_exit = (row['rsi'] > PARAMS['rsi_exit']) if TRADE_DIRECTION == 'buy' else (row['rsi'] < PARAMS['rsi_exit'])

            exit_reason = None
            if can_exit and (trailing_exit or stop_exit or rsi_exit):
                if trailing_exit:
                    exit_reason = 'trailing'
                elif stop_exit:
                    exit_reason = 'stop'
                elif rsi_exit:
                    exit_reason = 'rsi'
            if exit_reason:
                trades.append({
                    'entry_idx': entry_idx,
                    'entry_price': entry_price,
                    'exit_idx': i,
                    'exit_price': row['Close'],
                    'profit': profit,
                    'reason': exit_reason
                })
                in_trade = False
    return trades

def report(trades):
    if not trades:
        print("No trades executed.")
        return
    n = len(trades)
    wins = [t for t in trades if t['profit'] > 0]
    losses = [t for t in trades if t['profit'] <= 0]
    total_pnl = sum(t['profit'] for t in trades) * 100
    avg_trade = total_pnl / n
    max_dd = min([t['profit'] for t in trades]) * 100 if losses else 0
    print(f"Total Trades: {n}")
    print(f"Wins: {len(wins)} ({100*len(wins)/n:.1f}%)")
    print(f"Losses: {len(losses)} ({100*len(losses)/n:.1f}%)")
    print(f"Total P&L: {total_pnl:.2f}%")
    print(f"Average Trade: {avg_trade:.2f}%")
    print(f"Max Drawdown (single trade): {max_dd:.2f}%")
    print("\nParameters Used:")
    for k, v in PARAMS.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    df = load_data(DATA_FILE)
    df = calc_indicators(df)
    trades = strategy(df)
    report(trades)
