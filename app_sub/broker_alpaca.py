<<<<<<< HEAD
# filename: app/broker_alpaca.py
"""
AIMn Trading System — Alpaca Broker Adapter

Implements the BrokerBase interface for Alpaca (paper or live).
Requires either `alpaca-trade-api` OR falls back to `requests`.

Usage:
    from app.broker_alpaca import AlpacaBroker
    broker = AlpacaBroker(api_key, api_secret, base_url="https://paper-api.alpaca.markets")
    broker.connect()
    acct = broker.get_account()

Notes:
- For crypto on Alpaca, use the data URLs for crypto bars if you later add OHLCV.
- This adapter focuses on account/positions/orders wiring.
"""

from __future__ import annotations

import json
from typing import List, Dict, Any, Optional

try:
    from alpaca_trade_api.rest import REST, TimeFrame  # type: ignore
    _HAS_ALPACA_LIB = True
except Exception:
    import requests  # type: ignore
    _HAS_ALPACA_LIB = False

from .broker_base import BrokerBase


class AlpacaBroker(BrokerBase):
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        super().__init__(api_key, api_secret, **kwargs)
        # Allow override via kwargs, else default to paper
        self.base_url: str = kwargs.get("base_url", "https://paper-api.alpaca.markets")
        # Optional: specify asset_class ("us_equity" or "crypto") for list_symbols()
        self.asset_class: Optional[str] = kwargs.get("asset_class")
        self._client = None
        self._connected = False

    # ------------------------------------------------------------------
    # Connection / account
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        if _HAS_ALPACA_LIB:
            self._client = REST(self.api_key, self.api_secret, base_url=self.base_url)
            # A simple ping: fetch account
            _ = self._client.get_account()
            self._connected = True
            return True
        else:
            # Minimal check via REST
            headers = {
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.api_secret,
            }
            r = requests.get(f"{self.base_url}/v2/account", headers=headers, timeout=15)
            if r.status_code == 200:
                self._connected = True
                self._client = headers  # store for later raw calls
                return True
            raise RuntimeError(f"Alpaca connect failed: {r.status_code} {r.text}")

    def get_account(self) -> Dict[str, Any]:
        if not self._connected:
            raise RuntimeError("Not connected")
        if _HAS_ALPACA_LIB:
            acc = self._client.get_account()
            return {
                "portfolio_value": float(getattr(acc, "portfolio_value", 0) or 0),
                "buying_power": float(getattr(acc, "buying_power", 0) or 0),
                "currency": getattr(acc, "currency", "USD"),
                "status": getattr(acc, "status", ""),
            }
        else:
            r = requests.get(f"{self.base_url}/v2/account", headers=self._client, timeout=15)
            r.raise_for_status()
            acc = r.json()
            return {
                "portfolio_value": float(acc.get("portfolio_value", 0) or 0),
                "buying_power": float(acc.get("buying_power", 0) or 0),
                "currency": acc.get("currency", "USD"),
                "status": acc.get("status", ""),
            }

    # ------------------------------------------------------------------
    # Market data / symbols / positions
    # ------------------------------------------------------------------
    def list_symbols(self) -> List[str]:
        """Return tradable symbols filtered by optional asset_class.
        If self.asset_class is None, we return a sane subset (common crypto + equities) that are tradable.
        """
        if not self._connected:
            raise RuntimeError("Not connected")

        symbols: List[str] = []
        if _HAS_ALPACA_LIB:
            # Fetch assets (equities + crypto). asset_class filter reduces volume.
            assets = self._client.list_assets(status="active")
            for a in assets:
                try:
                    if not getattr(a, "tradable", False):
                        continue
                    if self.asset_class and getattr(a, "asset_class", None) != self.asset_class:
                        continue
                    sym = getattr(a, "symbol", None)
                    if sym:
                        symbols.append(sym)
                except Exception:
                    continue
        else:
            params = {"status": "active"}
            r = requests.get(f"{self.base_url}/v2/assets", headers=self._client, params=params, timeout=30)
            r.raise_for_status()
            assets = r.json()
            for a in assets:
                try:
                    if not a.get("tradable"):
                        continue
                    if self.asset_class and a.get("class") != self.asset_class:
                        continue
                    sym = a.get("symbol")
                    if sym:
                        symbols.append(sym)
                except Exception:
                    continue

        # Heuristic: prefer USD or USDT quoted crypto + common equities
        # (You can refine this or expose a filter in UI.)
        symbols = sorted(set(symbols))
        return symbols

    def get_positions(self) -> List[Dict[str, Any]]:
        if not self._connected:
            raise RuntimeError("Not connected")
        if _HAS_ALPACA_LIB:
            pos = self._client.list_positions()
            out = []
            for p in pos:
                out.append({
                    "symbol": getattr(p, "symbol", ""),
                    "qty": float(getattr(p, "qty", 0) or 0),
                    "market_value": float(getattr(p, "market_value", 0) or 0),
                    "unrealized_pl": float(getattr(p, "unrealized_pl", 0) or 0),
                })
            return out
        else:
            r = requests.get(f"{self.base_url}/v2/positions", headers=self._client, timeout=15)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            pos = r.json()
            out = []
            for p in pos:
                out.append({
                    "symbol": p.get("symbol", ""),
                    "qty": float(p.get("qty", 0) or 0),
                    "market_value": float(p.get("market_value", 0) or 0),
                    "unrealized_pl": float(p.get("unrealized_pl", 0) or 0),
                })
            return out

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------
    def place_order(self, symbol: str, qty: float, side: str, order_type: str = "market") -> Any:
        if not self._connected:
            raise RuntimeError("Not connected")
        side = side.lower()
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")

        if _HAS_ALPACA_LIB:
            order = self._client.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force="gtc",
            )
            return getattr(order, "_raw", str(order))
        else:
            payload = {
                "symbol": symbol,
                "qty": str(qty),
                "side": side,
                "type": order_type,
                "time_in_force": "gtc",
            }
            r = requests.post(f"{self.base_url}/v2/orders", headers=self._client, json=payload, timeout=15)
            r.raise_for_status()
            return r.json()

    def close_position(self, symbol: str) -> Any:
        if not self._connected:
            raise RuntimeError("Not connected")
        if _HAS_ALPACA_LIB:
            r = self._client.close_position(symbol)
            return getattr(r, "_raw", str(r))
        else:
            r = requests.delete(f"{self.base_url}/v2/positions/{symbol}", headers=self._client, timeout=15)
            if r.status_code in (200, 204):
                return {"status": "ok"}
            r.raise_for_status()
            return r.json()

    def close_all_positions(self) -> Any:
        if not self._connected:
            raise RuntimeError("Not connected")
        if _HAS_ALPACA_LIB:
            r = self._client.close_all_positions()
            return getattr(r, "_raw", str(r))
        else:
            r = requests.delete(f"{self.base_url}/v2/positions", headers=self._client, timeout=30)
            if r.status_code in (200, 204):
                return {"status": "ok"}
            r.raise_for_status()
            return r.json()
=======
# filename: app/broker_alpaca.py
"""
AIMn Trading System — Alpaca Broker Adapter

Implements the BrokerBase interface for Alpaca (paper or live).
Requires either `alpaca-trade-api` OR falls back to `requests`.

Usage:
    from app.broker_alpaca import AlpacaBroker
    broker = AlpacaBroker(api_key, api_secret, base_url="https://paper-api.alpaca.markets")
    broker.connect()
    acct = broker.get_account()

Notes:
- For crypto on Alpaca, use the data URLs for crypto bars if you later add OHLCV.
- This adapter focuses on account/positions/orders wiring.
"""

from __future__ import annotations

import json
from typing import List, Dict, Any, Optional

try:
    from alpaca_trade_api.rest import REST, TimeFrame  # type: ignore
    _HAS_ALPACA_LIB = True
except Exception:
    import requests  # type: ignore
    _HAS_ALPACA_LIB = False

from .broker_base import BrokerBase


class AlpacaBroker(BrokerBase):
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        super().__init__(api_key, api_secret, **kwargs)
        # Allow override via kwargs, else default to paper
        self.base_url: str = kwargs.get("base_url", "https://paper-api.alpaca.markets")
        # Optional: specify asset_class ("us_equity" or "crypto") for list_symbols()
        self.asset_class: Optional[str] = kwargs.get("asset_class")
        self._client = None
        self._connected = False

    # ------------------------------------------------------------------
    # Connection / account
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        if _HAS_ALPACA_LIB:
            self._client = REST(self.api_key, self.api_secret, base_url=self.base_url)
            # A simple ping: fetch account
            _ = self._client.get_account()
            self._connected = True
            return True
        else:
            # Minimal check via REST
            headers = {
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.api_secret,
            }
            r = requests.get(f"{self.base_url}/v2/account", headers=headers, timeout=15)
            if r.status_code == 200:
                self._connected = True
                self._client = headers  # store for later raw calls
                return True
            raise RuntimeError(f"Alpaca connect failed: {r.status_code} {r.text}")

    def get_account(self) -> Dict[str, Any]:
        if not self._connected:
            raise RuntimeError("Not connected")
        if _HAS_ALPACA_LIB:
            acc = self._client.get_account()
            return {
                "portfolio_value": float(getattr(acc, "portfolio_value", 0) or 0),
                "buying_power": float(getattr(acc, "buying_power", 0) or 0),
                "currency": getattr(acc, "currency", "USD"),
                "status": getattr(acc, "status", ""),
            }
        else:
            r = requests.get(f"{self.base_url}/v2/account", headers=self._client, timeout=15)
            r.raise_for_status()
            acc = r.json()
            return {
                "portfolio_value": float(acc.get("portfolio_value", 0) or 0),
                "buying_power": float(acc.get("buying_power", 0) or 0),
                "currency": acc.get("currency", "USD"),
                "status": acc.get("status", ""),
            }

    # ------------------------------------------------------------------
    # Market data / symbols / positions
    # ------------------------------------------------------------------
    def list_symbols(self) -> List[str]:
        """Return tradable symbols filtered by optional asset_class.
        If self.asset_class is None, we return a sane subset (common crypto + equities) that are tradable.
        """
        if not self._connected:
            raise RuntimeError("Not connected")

        symbols: List[str] = []
        if _HAS_ALPACA_LIB:
            # Fetch assets (equities + crypto). asset_class filter reduces volume.
            assets = self._client.list_assets(status="active")
            for a in assets:
                try:
                    if not getattr(a, "tradable", False):
                        continue
                    if self.asset_class and getattr(a, "asset_class", None) != self.asset_class:
                        continue
                    sym = getattr(a, "symbol", None)
                    if sym:
                        symbols.append(sym)
                except Exception:
                    continue
        else:
            params = {"status": "active"}
            r = requests.get(f"{self.base_url}/v2/assets", headers=self._client, params=params, timeout=30)
            r.raise_for_status()
            assets = r.json()
            for a in assets:
                try:
                    if not a.get("tradable"):
                        continue
                    if self.asset_class and a.get("class") != self.asset_class:
                        continue
                    sym = a.get("symbol")
                    if sym:
                        symbols.append(sym)
                except Exception:
                    continue

        # Heuristic: prefer USD or USDT quoted crypto + common equities
        # (You can refine this or expose a filter in UI.)
        symbols = sorted(set(symbols))
        return symbols

    def get_positions(self) -> List[Dict[str, Any]]:
        if not self._connected:
            raise RuntimeError("Not connected")
        if _HAS_ALPACA_LIB:
            pos = self._client.list_positions()
            out = []
            for p in pos:
                out.append({
                    "symbol": getattr(p, "symbol", ""),
                    "qty": float(getattr(p, "qty", 0) or 0),
                    "market_value": float(getattr(p, "market_value", 0) or 0),
                    "unrealized_pl": float(getattr(p, "unrealized_pl", 0) or 0),
                })
            return out
        else:
            r = requests.get(f"{self.base_url}/v2/positions", headers=self._client, timeout=15)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            pos = r.json()
            out = []
            for p in pos:
                out.append({
                    "symbol": p.get("symbol", ""),
                    "qty": float(p.get("qty", 0) or 0),
                    "market_value": float(p.get("market_value", 0) or 0),
                    "unrealized_pl": float(p.get("unrealized_pl", 0) or 0),
                })
            return out

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------
    def place_order(self, symbol: str, qty: float, side: str, order_type: str = "market") -> Any:
        if not self._connected:
            raise RuntimeError("Not connected")
        side = side.lower()
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")

        if _HAS_ALPACA_LIB:
            order = self._client.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force="gtc",
            )
            return getattr(order, "_raw", str(order))
        else:
            payload = {
                "symbol": symbol,
                "qty": str(qty),
                "side": side,
                "type": order_type,
                "time_in_force": "gtc",
            }
            r = requests.post(f"{self.base_url}/v2/orders", headers=self._client, json=payload, timeout=15)
            r.raise_for_status()
            return r.json()

    def close_position(self, symbol: str) -> Any:
        if not self._connected:
            raise RuntimeError("Not connected")
        if _HAS_ALPACA_LIB:
            r = self._client.close_position(symbol)
            return getattr(r, "_raw", str(r))
        else:
            r = requests.delete(f"{self.base_url}/v2/positions/{symbol}", headers=self._client, timeout=15)
            if r.status_code in (200, 204):
                return {"status": "ok"}
            r.raise_for_status()
            return r.json()

    def close_all_positions(self) -> Any:
        if not self._connected:
            raise RuntimeError("Not connected")
        if _HAS_ALPACA_LIB:
            r = self._client.close_all_positions()
            return getattr(r, "_raw", str(r))
        else:
            r = requests.delete(f"{self.base_url}/v2/positions", headers=self._client, timeout=30)
            if r.status_code in (200, 204):
                return {"status": "ok"}
            r.raise_for_status()
            return r.json()
>>>>>>> 0c0df91 (Initial push)
