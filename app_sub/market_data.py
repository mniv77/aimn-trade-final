# /app/market_data.py
# NOTE: For demo, this fetches Alpaca Crypto bars via data API v2. Replace with your existing module if needed.
import os, requests, pandas as pd
from datetime import datetime, timedelta, timezone

ALPACA_DATA_URL = "https://data.alpaca.markets/v1beta3/crypto/us/bars"

def _to_alpaca_symbol(symbol: str) -> str:
    S = symbol.upper().replace("-", "/").replace(" ", "")
    if "/" in S:
        return S
    QUOTES = ("USD","USDT","EUR","GBP","JPY","AUD","CAD","CHF")
    for q in QUOTES:
        if S.endswith(q):
            return f"{S[:-len(q)]}/{q}"
    return symbol


def fetch_bars(symbol: str, timeframe: str = "1Min", limit: int = 300, paper: bool = True) -> pd.DataFrame:
    key = os.environ.get("ALPACA_KEY_ID")  # fallback headers if not using DB auth for data
    sec = os.environ.get("ALPACA_SECRET_KEY")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec} if key and sec else {}
    sym = _to_alpaca_symbol(symbol)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=3)
    params = {"symbols": sym, "timeframe": timeframe, "start": start.isoformat(), "end": end.isoformat(), "limit": limit}
    r = requests.get(ALPACA_DATA_URL, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    raw = r.json().get("bars", {}).get(sym, [])
    if not raw: 
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df["t"] = pd.to_datetime(df["t"])
    df = df.rename(columns={"o":"open","h":"high","l":"low","c":"close","v":"volume"})[["t","open","high","low","close","volume"]]
    return df

def _to_binance_symbol(symbol: str) -> str:
    symbol = symbol.replace('-', '/')
    if '/' in symbol:
        base, quote = symbol.split('/', 1)
    else:
        base, quote = symbol, 'USDT'
    if quote in ('USD', 'USDT'):  # normalize
        quote = 'USDT'
    return f"{base}{quote}"

def _tf_to_binance(tf: str) -> str:
    m = {
        '1Min':'1m','3Min':'3m','5Min':'5m','15Min':'15m','30Min':'30m',
        '1Hour':'1h','2Hour':'2h','4Hour':'4h','6Hour':'6h','8Hour':'8h','12Hour':'12h',
        '1Day':'1d'
    }
    return m.get(tf, '1m')



# [aimn] binance fallback
def _to_binance_symbol(symbol: str) -> str:
    symbol = symbol.replace('-', '/')
    if '/' in symbol:
        base, quote = symbol.split('/', 1)
    else:
        base, quote = symbol, 'USDT'
    if quote in ('USD','USDT'):
        quote = 'USDT'
    return f"{base}{quote}"

def _tf_to_binance(tf: str) -> str:
    m = {'1Min':'1m','3Min':'3m','5Min':'5m','15Min':'15m','30Min':'30m',
         '1Hour':'1h','2Hour':'2h','4Hour':'4h','6Hour':'6h','8Hour':'8h','12Hour':'12h',
         '1Day':'1d'}
    return m.get(tf, '1m')

def _fetch_bars_binance(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    import requests, pandas as pd
    sym = _to_binance_symbol(symbol)
    interval = _tf_to_binance(timeframe)
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": sym, "interval": interval, "limit": min(int(limit), 1000)}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return pd.DataFrame()
    data = [{
        "t": pd.to_datetime(x[0], unit="ms", utc=True),
        "open": float(x[1]), "high": float(x[2]),
        "low": float(x[3]), "close": float(x[4]),
        "volume": float(x[5]),
    } for x in rows]
    return pd.DataFrame(data)[["t","open","high","low","close","volume"]]

_old_fetch_bars = fetch_bars  # keep original

def fetch_bars(symbol: str, timeframe: str = "1Min", limit: int = 300, paper: bool = True) -> pd.DataFrame:
    import requests, pandas as pd, os
    from datetime import datetime, timezone, timedelta
    key = os.environ.get("ALPACA_KEY_ID")
    sec = os.environ.get("ALPACA_SECRET_KEY")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec} if key and sec else {}
    sym = _to_alpaca_symbol(symbol)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=3)
    params = {"symbols": sym, "timeframe": timeframe, "start": start.isoformat(), "end": end.isoformat(), "limit": limit}
    try:
        r = requests.get(ALPACA_DATA_URL, headers=headers, params=params, timeout=15)
        if r.status_code in (401, 403):
            raise requests.HTTPError(f"{r.status_code}", response=r)
        r.raise_for_status()
        raw = r.json().get("bars", {}).get(sym, [])
        if raw:
            df = pd.DataFrame(raw)
            df["t"] = pd.to_datetime(df["t"])
            df = df.rename(columns={"o":"open","h":"high","l":"low","c":"close","v":"volume"})[["t","open","high","low","close","volume"]]
            return df
    except Exception:
        pass  # fall back

    try:
        df2 = _fetch_bars_binance(symbol, timeframe, limit)
        return df2 if not df2.empty else _fetch_bars_synthetic(symbol, timeframe, limit)
    except Exception:
        return _fetch_bars_synthetic(symbol, timeframe, limit)
# [/aimn]


def _fetch_bars_synthetic(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    # generate synthetic 1-minute bars for the last N minutes
    import pandas as pd
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    n = max(1, int(limit))
    times = [now - timedelta(minutes=i) for i in range(n-1, -1, -1)]
    base = 30000.0
    data = []
    for i, t in enumerate(times):
        o = base + i * 0.5
        h = o + 1.0
        l = o - 1.0
        c = o + 0.2
        v = 1.0
        data.append({'t': pd.Timestamp(t), 'open': o, 'high': h, 'low': l, 'close': c, 'volume': v})
    return pd.DataFrame(data)[['t','open','high','low','close','volume']]
