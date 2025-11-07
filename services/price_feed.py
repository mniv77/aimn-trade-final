# FILE: services/price_feed.py
from __future__ import annotations
import os, time, json, math, random, logging
from typing import Optional, Tuple, Dict
import requests

log = logging.getLogger(__name__)
_TIMEOUT = 4
_ALPACA_KEY = os.getenv("ALPACA_KEY_ID")
_ALPACA_SEC = os.getenv("ALPACA_SECRET_KEY")
# in-memory cache to reduce provider load
_CACHE: Dict[str, Tuple[float, dict]] = {}
_CACHE_TTL = 1.5  # seconds

def _norm_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if s.startswith("$"):
        s = s[1:]
    return s

def _is_crypto(symbol: str, exchange: Optional[str]) -> bool:
    if exchange and exchange.upper() in {"CRYPTO", "BINANCE", "COINBASE"}:
        return True
    return "/" in symbol  # e.g., BTC/USD

def _cache_get(key: str) -> Optional[dict]:
    now = time.time()
    ent = _CACHE.get(key)
    if not ent:
        return None
    ts, data = ent
    if now - ts <= _CACHE_TTL:
        return data
    return None

def _cache_put(key: str, data: dict) -> None:
    _CACHE[key] = (time.time(), data)

def _alpaca_headers() -> dict:
    return {"APCA-API-KEY-ID": _ALPACA_KEY, "APCA-API-SECRET-KEY": _ALPACA_SEC}

def _alpaca_stock_latest(symbol: str) -> Optional[float]:
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest"
    r = requests.get(url, headers=_alpaca_headers(), timeout=_TIMEOUT)
    if r.status_code != 200:
        log.warning("Alpaca stocks %s -> %s %s", symbol, r.status_code, r.text[:120])
        return None
    data = r.json()
    # format: {"symbol":"MSFT","trade":{"p":price,...}}
    trade = data.get("trade") or {}
    p = trade.get("p")
    return float(p) if p is not None else None

def _alpaca_crypto_latest(symbol: str) -> Optional[float]:
    # normalize like BTC/USD -> BTC/USD; Alpaca wants "symbols=BTC/USD"
    params = {"symbols": symbol}
    url = "https://data.alpaca.markets/v1beta3/crypto/us/latest/trades"
    r = requests.get(url, headers=_alpaca_headers(), params=params, timeout=_TIMEOUT)
    if r.status_code != 200:
        log.warning("Alpaca crypto %s -> %s %s", symbol, r.status_code, r.text[:120])
        return None
    data = r.json()
    # format: {"trades":{"BTC/USD":{"p":price,...}}}
    trades = data.get("trades") or {}
    row = trades.get(symbol) or {}
    p = row.get("p")
    return float(p) if p is not None else None

def _yfinance_latest(symbol: str) -> Optional[float]:
    # lightweight fast-info endpoint used by yfinance internally
    # WARNING: may be blocked on PythonAnywhere free tier, so handle HTML/non-JSON
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    params = {"modules":"price"}
    r = requests.get(url, params=params, timeout=_TIMEOUT, headers={"User-Agent":"Mozilla/5.0"})
    if r.status_code != 200:
        return None
    try:
        j = r.json()
    except Exception:
        return None
    res = (((j.get("quoteSummary") or {}).get("result") or []) or [{}])[0]
    price = (((res.get("price") or {}).get("regularMarketPrice") or {}) or {}).get("raw")
    return float(price) if price is not None else None

def _simulate_tick(sym: str, last_price: Optional[float]) -> float:
    # only used as a last resort; flagged with "simulated": true
    base = last_price or {
        "SPY": 450.0, "QQQ": 380.0, "NVDA": 120.0, "AAPL": 170.0, "MSFT": 400.0,
        "BTC/USD": 68000.0, "ETH/USD": 3600.0
    }.get(sym, 100.0)
    drift = random.uniform(-0.15, 0.15) / 100.0  # ±0.15%
    return round(base * (1 + drift), 2)

def get_quote(symbol: str, exchange: Optional[str]=None) -> dict:
    sym = _norm_symbol(symbol)
    key = f"{exchange}|{sym}"
    cached = _cache_get(key)
    if cached:
        return cached

    # choose provider
    price = None
    source = None
    simulated = False
    errors = []

    try:
        if _ALPACA_KEY and _ALPACA_SEC:
            if _is_crypto(sym, exchange):
                price = _alpaca_crypto_latest(sym)
                source = "alpaca-crypto"
            else:
                price = _alpaca_stock_latest(sym)
                source = "alpaca-stocks"
    except Exception as e:
        errors.append(f"alpaca:{type(e).__name__}")

    if price is None:
        try:
            price = _yfinance_latest(sym)
            if price is not None:
                source = "yahoo"
        except Exception as e:
            errors.append(f"yahoo:{type(e).__name__}")

    if price is None:
        # final fallback to keep UI flowing (clearly marked)
        price = _simulate_tick(sym, None)
        source = "sim"
        simulated = True

    out = {
        "symbol": sym,
        "exchange": exchange,
        "price": price,
        "source": source,
        "simulated": simulated,
        "errors": errors,
        "ts": time.time(),
    }
    _cache_put(key, out)
    return out
