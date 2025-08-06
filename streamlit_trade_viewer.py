# demo_generator.py
"""
Generates demo trades + charts for Streamlit dashboard preview
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from trade_snapshot import save_trade_snapshot
from trade_exporter import export_trades_to_csv

# Generate fake OHLCV data
def generate_fake_ohlcv(start_time: datetime, periods=60) -> pd.DataFrame:
    np.random.seed(42)
    times = [start_time + timedelta(minutes=i) for i in range(periods)]
    close = np.cumsum(np.random.randn(periods)) + 100
    open_ = close + np.random.randn(periods) * 0.5
    high = np.maximum(open_, close) + np.random.rand(periods)
    low = np.minimum(open_, close) - np.random.rand(periods)
    volume = np.random.randint(100, 1000, size=periods)

    return pd.DataFrame({
        'open': open_, 'high': high, 'low': low,
        'close': close, 'volume': volume
    }, index=pd.to_datetime(times))

# Create fake trades
def generate_demo_trades():
    symbols = ['BTC/USD', 'ETH/USD']
    trades = []
    now = datetime.now()
    os.makedirs('trade_snapshots', exist_ok=True)

    for i in range(5):
        symbol = symbols[i % 2]
        direction = 'BUY' if i % 2 == 0 else 'SELL'
        start = now - timedelta(minutes=(10 * (i+1)))
        df = generate_fake_ohlcv(start)

        entry_time = df.index[10]
        exit_time = df.index[50]
        entry_price = df['close'].iloc[10]
        exit_price = df['close'].iloc[50]
        stop_loss = entry_price * (0.98 if direction == 'BUY' else 1.02)
        rsi = 65.0 + np.random.rand() * 5
        exit_reason = ['S', 'E', 'P', 'R'][i % 4]

        filename = f"{symbol.replace('/', '')}_{exit_reason}_{entry_time.strftime('%H%M%S')}"

        save_trade_snapshot(df, symbol, entry_time, exit_time, entry_price,
                            exit_price, filename, stop_loss, rsi, exit_reason)

        trades.append({
            'symbol': symbol,
            'direction': direction,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'shares': 1,
            'pnl': (exit_price - entry_price) * (1 if direction == 'BUY' else -1),
            'pnl_pct': ((exit_price - entry_price) / entry_price) * 100,
            'exit_code': exit_reason,
            'highest_price': df['high'].max(),
            'lowest_price': df['low'].min()
        })

    export_trades_to_csv(trades, filename='demo_trades.csv')

if __name__ == "__main__":
    generate_demo_trades()
    print("✅ Demo trades and snapshots generated!")
