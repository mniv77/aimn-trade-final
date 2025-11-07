# /home/MeirNiv/aimn-trade-final/services/quote_provider.py
from __future__ import annotations
import os, time, random, threading
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import requests

@dataclass
class Quote:
    symbol: str
    exchange: str
    price: float
    ts_ms: int
    feed: str  # "REAL" | "PUBLIC" | "SIM"

class QuoteProvider:
    def get_price(self, symbol: str, exchange: str) -> Optional[Quote]:
        raise NotImplementedError

# ---- REAL (Alpaca) ----
class AlpacaQuoteProvider(QuoteProvider):
    def __init__(self) -> None:
        self._ok = False
        key = os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID")
        sec = os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY")
        base = os.getenv("ALPACA_BASE_URL", "https://data.alpaca.markets")
        if key and sec:
            try:
                from alpaca_trade_api.rest import REST
                self._rest = REST(key, sec, base_url=base)
                self._ok = True
            except Exception:
                self._ok = False

    def get_price(self, symbol: str, exchange: str) -> Optional[Quote]:
        if not self._ok:
            return None
        try:
            t = self._rest.get_latest_trade(symbol)
            px = float(getattr(t, "p", 0.0) or getattr(t, "price", 0.0))
            if px > 0:
                return Quote(symbol, exchange, px, int(time.time()*1000), "REAL")
        except Exception:
            return None
        return None

# ---- PUBLIC (Yahoo via yfinance; Binance for crypto) ----
class PublicQuoteProvider(QuoteProvider):
    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "aimn-quote/1.0"})
        try:
            import yfinance as yf  # noqa: F401
            self._has_yf = True
        except Exception:
            self._has_yf = False

    @staticmethod
    def _is_crypto(symbol: str, exchange: str) -> bool:
        s = symbol.upper()
        ex = (exchange or "").upper()
        return "CRYPTO" in ex or "/" in s or s.endswith("USDT")

    @staticmethod
    def _to_binance_symbol(symbol: str) -> str:
        s = symbol.upper().replace("/", "")
        if s.endswith("USD"):  # map USD -> USDT
            return s.replace("USD", "USDT")
        return s

    def _binance_price(self, symbol: str) -> Optional[float]:
        sym = self._to_binance_symbol(symbol)
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={sym}"
        try:
            r = self._session.get(url, timeout=3)
            if r.ok:
                j = r.json()
                px = float(j["price"])
                if px > 0: return px
        except Exception:
            return None
        return None

    def _yahoo_price(self, symbol: str) -> Optional[float]:
        if not self._has_yf:
            return None
        try:
            import yfinance as yf
            t = yf.Ticker(symbol)
            fast = getattr(t, "fast_info", None)
            if fast:
                px = float(getattr(fast, "last_price", 0.0) or 0.0)
                if px > 0: return px
            info = getattr(t, "info", {}) or {}
            px = float(info.get("regularMarketPrice") or info.get("currentPrice") or 0.0)
            if px > 0: return px
            df = t.history(period="1d", interval="1m")
            if not df.empty:
                px = float(df["Close"].iloc[-1])
                if px > 0: return px
        except Exception:
            return None
        return None

    def get_price(self, symbol: str, exchange: str) -> Optional[Quote]:
        now = int(time.time()*1000)
        if self._is_crypto(symbol, exchange):
            px = self._binance_price(symbol)
            if px and px > 0:
                return Quote(symbol, exchange, px, now, "PUBLIC")
            return None
        px = self._yahoo_price(symbol)
        if px and px > 0:
            return Quote(symbol, exchange, px, now, "PUBLIC")
        return None

# ---- SIM (bounded random walk) ----
class SimQuoteProvider(QuoteProvider):
    def __init__(self) -> None:
        self._state: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    def _seed(self, symbol: str) -> float:
        s = symbol.upper()
        seeds = {"AAPL": 175.6, "TSLA": 250.0, "NVDA": 190.0, "SPY": 520.0, "QQQ": 450.0,
                 "BTC/USD": 68000.0, "ETH/USD": 3500.0, "AMZN": 180.0, "MSFT": 430.0}
        if s not in seeds and s.endswith("/USD"):
            return 100.0
        return seeds.get(s, 100.0)

    def get_price(self, symbol: str, exchange: str) -> Optional[Quote]:
        key = f"{exchange}:{symbol}"
        now = time.time()
        with self._lock:
            if key not in self._state:
                self._state[key] = (self._seed(symbol), now)
            p, last = self._state[key]
            dt = max(0.2, now - last)
            is_crypto = "CRYPTO" in exchange.upper() or "/USD" in symbol.upper()
            vol = 0.004 if is_crypto else 0.0015
            drift = p * vol * (random.random() - 0.5) * (dt / 1.0)
            p = max(0.01, p + drift)
            self._state[key] = (p, now)
            return Quote(symbol, exchange, float(f"{p:.6f}"), int(now*1000), "SIM")

# ---- choose provider (REAL -> PUBLIC -> SIM) ----
def get_provider() -> QuoteProvider:
    alpaca = AlpacaQuoteProvider()
    if getattr(alpaca, "_ok", False):
        return alpaca
    try:
        pub = PublicQuoteProvider()
        return pub
    except Exception:
        return SimQuoteProvider()
