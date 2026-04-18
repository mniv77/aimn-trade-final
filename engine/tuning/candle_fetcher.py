# /home/MeirNiv/aimn-trade-final/engine/tuning/candle_fetcher.py
import requests
from datetime import datetime, timedelta
import sys

# ── Gemini candle fetcher (crypto) ────────────────────────────
def fetch_gemini_candles(symbol, timeframe="1hr", limit=100):
    url = f"https://api.gemini.com/v2/candles/{symbol}/{timeframe}?limit={limit}"
    resp = requests.get(url, timeout=10)
    data = resp.json()
    if not isinstance(data, list):
        print(f"[candle_fetcher] ❌ Unexpected response for {symbol}/{timeframe}: {data}")
        return []
    candles = []
    for c in data:
        ts = datetime.fromtimestamp(c[0] / 1000)
        candles.append({
            "symbol"   : symbol,
            "timeframe": timeframe,
            "timestamp": ts,
            "open"     : c[1],
            "high"     : c[2],
            "low"      : c[3],
            "close"    : c[4],
            "volume"   : c[5]
        })
    return candles


# ── Yahoo Finance candle fetcher (stocks, ETFs, any broker) ──
def fetch_yahoo_candles(symbol, timeframe="1hr", limit=100):
    """Fetch candles from Alpaca historical data API for stocks/ETFs"""
    sys.path.insert(0, '/home/MeirNiv/aimn-trade-final')
    from db import get_db_connection

    # Get Alpaca credentials from DB
    try:
        conn, cursor = get_db_connection()
        cursor.execute("SELECT api_key, api_secret FROM brokers WHERE name='Alpaca' LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if not row:
            print(f"[candle_fetcher] ❌ Alpaca credentials not found")
            return []
        api_key    = row['api_key']
        api_secret = row['api_secret']
    except Exception as e:
        print(f"[candle_fetcher] ❌ DB error: {e}")
        return []

    # Map AiMN timeframes to Alpaca timeframes
    tf_map = {
        '1m' : '1Min',
        '5m' : '5Min',
        '15m': '15Min',
        '30m': '30Min',
        '1hr': '1Hour',
        '1h' : '1Hour',
        '2h' : '2Hour',
        '6hr': '1Day',
        '1d' : '1Day',
    }
    alpaca_tf = tf_map.get(timeframe, '1Hour')

    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    headers = {
        'APCA-API-KEY-ID'    : api_key,
        'APCA-API-SECRET-KEY': api_secret,
    }
    params = {
        'timeframe': alpaca_tf,
        'limit'    : 10000,
        'feed'     : 'sip',
        'start'    : '2020-01-01',
        'sort'     : 'asc',
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code != 200:
            print(f"[candle_fetcher] ❌ Alpaca HTTP {r.status_code} for {symbol}: {r.text}")
            return []

        data = r.json()
        bars = data.get('bars', [])
        if not bars:
            print(f"[candle_fetcher] ❌ No bars from Alpaca for {symbol}")
            return []

        candles = []
        for b in bars:
            candles.append({
                'symbol'   : symbol,
                'timeframe': timeframe,
                'timestamp': b['t'],
                'open'     : float(b['o']),
                'high'     : float(b['h']),
                'low'      : float(b['l']),
                'close'    : float(b['c']),
                'volume'   : float(b['v']),
            })

        print(f"[candle_fetcher] ✅ Alpaca: {len(candles)} candles for {symbol}/{timeframe}")
        return candles

    except Exception as e:
        print(f"[candle_fetcher] ❌ Alpaca error for {symbol}: {e}")
        return []


# ── Yahoo Finance Forex fetcher (currency pairs) ─────────────
def fetch_yahoo_forex(symbol, timeframe="1hr", limit=100):
    """Fetch Forex candles using yfinance (e.g. EUR/USD -> EURUSD=X)"""
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        print("[candle_fetcher] ❌ yfinance not installed. Run: pip install yfinance")
        return []

    # Convert EUR/USD to EURUSD=X
    ticker = symbol.replace("/", "") + "=X"

    # Map timeframes
    tf_map = {
        '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
        '1hr': '1h', '1h': '1h', '2h': '2h',
        '1d': '1d', '1w': '1wk', '1mo': '1mo'
    }
    interval = tf_map.get(timeframe, '1h')

    # Fetch last 60 days for enough bars
    try:
        df = yf.download(ticker, period="60d", interval=interval, progress=False)
        if df.empty:
            print(f"[candle_fetcher] ❌ No data from yfinance for {ticker}")
            return []

        candles = []
        for idx, row in df.iterrows():
            candles.append({
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': idx.to_pydatetime(),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': float(row['Volume']) if 'Volume' in row else 0
            })

        print(f"[candle_fetcher] ✅ yfinance Forex: {len(candles)} candles for {symbol}/{timeframe}")
        return candles[-limit:] if limit else candles

    except Exception as e:
        print(f"[candle_fetcher] ❌ yfinance error for {symbol}: {e}")
        return []


# ── Smart fetcher — auto detects broker/symbol type ──────────
def fetch_candles(symbol, timeframe="1hr", limit=100, broker="Gemini"):
    """
    Universal candle fetcher.
    Automatically routes to correct data source based on broker.
    """
    broker = broker.upper()

    if broker == "GEMINI":
        # Convert symbol format: BTC/USD -> btcusd
        clean = symbol.replace("/", "").lower()
        return fetch_gemini_candles(clean, timeframe, limit)

    elif broker == "FOREX":
        return fetch_yahoo_forex(symbol, timeframe, limit)

    elif broker in ("ALPACA", "ALPACA-ETF", "WEBULL", "COINBASE", "YAHOO"):
        return fetch_yahoo_candles(symbol, timeframe, limit)

    else:
        print(f"[candle_fetcher] ⚠️ Unknown broker '{broker}' — trying Yahoo Finance")
        return fetch_yahoo_candles(symbol, timeframe, limit)
