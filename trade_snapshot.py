<<<<<<< HEAD
# trade_snapshot.py
"""
Auto-snapshot plotter for trades
"""
import matplotlib.pyplot as plt
import pandas as pd
import os

def save_trade_snapshot(df: pd.DataFrame, symbol: str, entry_time, exit_time, entry_price, exit_price, filename, stop_loss=None, rsi=None, exit_reason=None):
    df = df.copy()
    df = df[(df.index >= entry_time - pd.Timedelta(minutes=1)) & (df.index <= exit_time + pd.Timedelta(minutes=1))]
    if df.empty: return

    plt.figure(figsize=(12, 6))
    plt.plot(df['close'], label='Close Price', color='blue', linewidth=1.5)
    plt.axhline(entry_price, color='green', linestyle='--', linewidth=1.2, label='Entry Price')
    plt.axhline(exit_price, color='red', linestyle='--', linewidth=1.2, label=f"Exit @ {exit_price:.2f}")
    plt.axvline(entry_time, color='green', linestyle=':', linewidth=1.0, label='Entry Time')
    plt.axvline(exit_time, color='red', linestyle=':', linewidth=1.0, label='Exit Time')

    if stop_loss:
        plt.axhline(stop_loss, color='orange', linestyle=':', label='Stop Loss')
    if rsi is not None:
        plt.text(df.index[-1], df['close'].max(), f"RSI: {rsi:.1f}", ha='right', color='purple')
    if exit_reason:
        plt.text(df.index[-1], df['close'].min(), f"Exit Reason: {exit_reason}", ha='right', color='black')

    plt.title(f"{symbol} Trade Snapshot ({entry_time.strftime('%H:%M')} - {exit_time.strftime('%H:%M')})")
    plt.legend()
    plt.tight_layout()
    os.makedirs("trade_snapshots", exist_ok=True)
    plt.savefig(f"trade_snapshots/{filename}.png")
=======
# trade_snapshot.py
"""
Auto-snapshot plotter for trades
"""
import matplotlib.pyplot as plt
import pandas as pd
import os

def save_trade_snapshot(df: pd.DataFrame, symbol: str, entry_time, exit_time, entry_price, exit_price, filename, stop_loss=None, rsi=None, exit_reason=None):
    df = df.copy()
    df = df[(df.index >= entry_time - pd.Timedelta(minutes=1)) & (df.index <= exit_time + pd.Timedelta(minutes=1))]
    if df.empty: return

    plt.figure(figsize=(12, 6))
    plt.plot(df['close'], label='Close Price', color='blue', linewidth=1.5)
    plt.axhline(entry_price, color='green', linestyle='--', linewidth=1.2, label='Entry Price')
    plt.axhline(exit_price, color='red', linestyle='--', linewidth=1.2, label=f"Exit @ {exit_price:.2f}")
    plt.axvline(entry_time, color='green', linestyle=':', linewidth=1.0, label='Entry Time')
    plt.axvline(exit_time, color='red', linestyle=':', linewidth=1.0, label='Exit Time')

    if stop_loss:
        plt.axhline(stop_loss, color='orange', linestyle=':', label='Stop Loss')
    if rsi is not None:
        plt.text(df.index[-1], df['close'].max(), f"RSI: {rsi:.1f}", ha='right', color='purple')
    if exit_reason:
        plt.text(df.index[-1], df['close'].min(), f"Exit Reason: {exit_reason}", ha='right', color='black')

    plt.title(f"{symbol} Trade Snapshot ({entry_time.strftime('%H:%M')} - {exit_time.strftime('%H:%M')})")
    plt.legend()
    plt.tight_layout()
    os.makedirs("trade_snapshots", exist_ok=True)
    plt.savefig(f"trade_snapshots/{filename}.png")
>>>>>>> 0c0df91 (Initial push)
    plt.close()