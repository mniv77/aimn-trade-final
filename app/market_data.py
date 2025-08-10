# /app/market_data.py
# NOTE: For demo, this fetches Alpaca Crypto bars via data API v2. Replace with your existing module if needed.
import os, requests, pandas as pd
from datetime import datetime, timedelta, timezone

ALPACA_DATA_URL = "https://data.alpaca.markets/v1beta3/crypto/us/bars"

def fetch_bars(symbol: str, timeframe: str = "1Min", limit: int = 300, paper: bool = True) -> pd.DataFrame:
    key = os.environ.get("ALPACA_KEY_ID")  # fallback headers if not using DB auth for data
    sec = os.environ.get("ALPACA_SECRET_KEY")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec} if key and sec else {}
    sym = symbol.replace("/", "")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=3)
    params = {"symbols": sym, "timeframe": timeframe, "start": start.isoformat(), "end": end.isoformat(), "limit": limit}
    r = requests.get(ALPACA_DATA_URL, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    raw = r.json()["bars"].get(sym, [])
    if not raw: 
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df["t"] = pd.to_datetime(df["t"])
    df = df.rename(columns={"o":"open","h":"high","l":"low","c":"close","v":"volume"})[["t","open","high","low","close","volume"]]
    return df