# filename: AImnMLResearch/backtest_loop_skeleton.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

 
def run_backtest(df, params):
    trade_mode = params.get('trade_mode', 'BUY')
    is_buy_mode = trade_mode == 'BUY'
    is_sell_mode = trade_mode == 'SELL'
    # Indicator Calculation
    df['recent_high'] = df['high'].rolling(params['rsi_window']).max()
    df['recent_low'] = df['low'].rolling(params['rsi_window']).min()
    df['rsi_real'] = (df['close'] - df['recent_low']) / (df['recent_high'] - df['recent_low']) * 100
    df['rsi_real'] = df['rsi_real'].fillna(50)
    exp1 = df['close'].ewm(span=params['macd_fast_length'], adjust=False).mean()
    exp2 = df['close'].ewm(span=params['macd_slow_length'], adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=params['macd_signal_length'], adjust=False).mean()
    df['vol_ma_buy'] = df['volume'].rolling(params['vol_ma_length_buy']).mean()
    df['vol_ma_sell'] = df['volume'].rolling(params['vol_ma_length_sell']).mean()
    df['tr'] = np.maximum(df['high'] - df['low'],
                          np.abs(df['high'] - df['close'].shift(1)),
                          np.abs(df['low'] - df['close'].shift(1)))
    df['atr_buy'] = df['tr'].rolling(params['atr_length_buy']).mean()
    df['atr_ma_buy'] = df['atr_buy'].rolling(params['atr_ma_length_buy']).mean()
    df['atr_sell'] = df['tr'].rolling(params['atr_length_sell']).mean()
    df['atr_ma_sell'] = df['atr_sell'].rolling(params['atr_ma_length_sell']).mean()
    df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
    df['obv_ma'] = df['obv'].rolling(20).mean()

    trades = []
    balance = 1000
    equity_curve = [balance]
    in_position = False
    entry_price = None
    entry_index = None
    direction = None

    for i in range(2, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]

        buy_signal = (
            is_buy_mode and
            row['rsi_real'] <= params['oversold_level']
            and (prev_row['macd'] < prev_row['macd_signal']) and (row['macd'] > row['macd_signal'])
            and (row['volume'] > row['vol_ma_buy'] * params['vol_threshold_buy'])
        )
        sell_signal = (
            is_sell_mode and
            row['rsi_real'] >= params['overbought_level']
            and (prev_row['macd'] > prev_row['macd_signal']) and (row['macd'] < row['macd_signal'])
            and (row['volume'] > row['vol_ma_sell'] * params['vol_threshold_sell'])
        )

        if not in_position and (buy_signal or sell_signal):
            direction = 'BUY' if buy_signal else 'SELL'
            entry_price = row['close']
            entry_index = i
            in_position = True

        if in_position:
            if direction == 'BUY':
                profit_pct = (row['close'] - entry_price) / entry_price * 100
                exit_condition = (
                    ((row['rsi_real'] >= params['rsi_exit_buy']) or (i - entry_index > 10))
                    and profit_pct >= params['min_exit_profit_pct_buy']
                )
            else:
                profit_pct = (entry_price - row['close']) / entry_price * 100
                exit_condition = (
                    ((row['rsi_real'] <= params['rsi_exit_sell']) or (i - entry_index > 10))
                    and profit_pct >= params['min_exit_profit_pct_sell']
                )
            if exit_condition:
                exit_price = row['close']
                trades.append({
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(exit_price, 2),
                    'profit_pct': profit_pct,
                    'direction': direction,
                    'exit_reason': 'RSI/Timeout',
                    'entry_index': entry_index,
                    'exit_index': i,
                })
                balance *= (1 + profit_pct / 100)
                equity_curve.append(balance)
                in_position = False

    n_trades = len(trades)
    n_wins = sum(1 for t in trades if t['profit_pct'] > 0)
    n_losses = n_trades - n_wins
    win_rate = 100 * n_wins / n_trades if n_trades else 0
    n_buy_orders = sum(1 for t in trades if t['direction'] == 'BUY')
    n_sell_orders = sum(1 for t in trades if t['direction'] == 'SELL')
    avg_trade_pct = sum(t['profit_pct'] for t in trades) / n_trades if n_trades else 0
    compound_total_pct = (balance - 1000) / 1000 * 100 if n_trades else 0
    equity_series = pd.Series(equity_curve)
    roll_max = equity_series.cummax()
    drawdown = (equity_series - roll_max) / roll_max
    max_drawdown = drawdown.min() * 100 if not drawdown.empty else 0

    plot_path = "static/price_trades_equity.png"
    plt.figure(figsize=(10,6))
    ax1 = plt.gca()
    df['close'].plot(ax=ax1, color='gray', linewidth=1, label='Close Price')
    for trade in trades:
        entry, exit_, dir_ = trade['entry_index'], trade['exit_index'], trade['direction']
        color = 'green' if dir_ == 'BUY' else 'red'
        ax1.annotate('B' if dir_ == 'BUY' else 'S', xy=(entry, df.iloc[entry]['close']), color=color,
                     fontsize=10, ha='center', va='bottom', fontweight='bold')
        ax1.annotate('E', xy=(exit_, df.iloc[exit_]['close']), color='blue',
                     fontsize=10, ha='center', va='top', fontweight='bold')
    ax1.set_ylabel("Price")
    ax1.legend(loc='upper left')
    ax2 = ax1.twinx()
    ax2.plot(range(len(equity_curve)), equity_curve, color='blue', label='Equity Curve')
    ax2.set_ylabel("Account Value ($)")
    ax2.legend(loc='upper right')
    plt.title("Price, Trades, and Equity Curve")
    plt.tight_layout()
    os.makedirs(os.path.dirname(plot_path), exist_ok=True)
    plt.savefig(plot_path)
    plt.close()

    results = {
        'compound_total_pct': compound_total_pct,
        'n_trades': n_trades,
        'n_wins': n_wins,
        'n_losses': n_losses,
        'win_rate': win_rate,
        'n_buy_orders': n_buy_orders,
        'n_sell_orders': n_sell_orders,
        'avg_trade_pct': avg_trade_pct,
        'max_drawdown': abs(max_drawdown),
        'trades': trades,
        'equity_curve_path': plot_path
    }
    return results