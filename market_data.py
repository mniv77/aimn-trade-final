# market_data.py
"""
AIMn Trading System - Market Data Loader
Pulls 1-minute historical OHLCV data for crypto symbols from Alpaca
"""

from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
import pandas as pd
from config import ALPACA_KEY, ALPACA_SECRET
from config import SYMBOLS, TIMEFRAME

# Create Alpaca client
client = CryptoHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)

def fetch_crypto_bars(symbol: str, limit: int = 200) -> pd.DataFrame:
    """
    Fetch 1-minute historical bars for a single crypto symbol
    """
    now = datetime.utcnow()
    start = now - timedelta(minutes=limit + 10)  # Buffer
    request = CryptoBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        start=start,
        end=now
    )
    bars = client.get_crypto_bars(request).df

    # Clean and structure DataFrame
    if symbol not in bars.index.get_level_values(0):
        return pd.DataFrame()

    df = bars.loc[symbol].copy()
    df = df.reset_index()
    df = df.rename(columns={
        'timestamp': 'datetime',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume'
    })
    df.set_index('datetime', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']]
    return df

def load_all_market_data(limit: int = 200) -> dict:
    """
    Load historical bars for all configured crypto symbols
    Returns a dict: { symbol: DataFrame }
    """
    market_data = {}
    for symbol in SYMBOLS:
        df = fetch_crypto_bars(symbol, limit=limit)
        if not df.empty:
            market_data[symbol] = df
    return market_data

if __name__ == "__main__":
    test_data = load_all_market_data()
    for sym, df in test_data.items():
        print(f"{sym}: {len(df)} bars loaded")