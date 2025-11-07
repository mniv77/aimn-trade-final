<<<<<<< HEAD
# filename: app/broker_gemini.py
"""
AIMn Trading System — Gemini Broker Adapter

Implements the BrokerBase interface for Gemini (production or sandbox).

Notes
-----
- Public endpoints require no auth (symbols, ticker).
- Private endpoints require HMAC-SHA384 signing with:
    X-GEMINI-APIKEY
    X-GEMINI-PAYLOAD (base64 of JSON)
    X-GEMINI-SIGNATURE (hex of HMAC-SHA384 over payload)
- Base URLs:
    Production REST: https://api.gemini.com
    Sandbox REST:    https://api.sandbox.gemini.com

Caveats
-------
- Gemini is account/balance-based (crypto), not "positions" like equities.
- For your rule: Buy BTC only with USDT and sell only if holding BTC —
  we enforce a simple guard in place_order().
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import List, Dict, Any, Optional

import requests  # type: ignore

from .broker_base import BrokerBase


class GeminiBroker(BrokerBase):
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        super().__init__(api_key, api_secret, **kwargs)
        # Default to SANDBOX unless explicitly set
        self.base_url: str = kwargs.get("base_url", "https://api.sandbox.gemini.com")
        # Optional: filter quote currency (e.g., "USD" or "USDT")
        self.quote_filter: Optional[str] = kwargs.get("quote_filter", "USDT")
        self._connected = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _signed_post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a signed POST to Gemini private endpoint.
        """
        url = f"{self.base_url}{path}"
        payload["request"] = path
        payload["nonce"] = str(int(time.time() * 1000))

        encoded = json.dumps(payload).encode()
        b64 = base64.b64encode(encoded)
        sig = hmac.new(
            self.api_secret.encode(), b64, hashlib.sha384
        ).hexdigest()

        headers = {
            "Content-Type": "text/plain",
            "Content-Length": "0",
            "X-GEMINI-APIKEY": self.api_key,
            "X-GEMINI-PAYLOAD": b64.decode(),
            "X-GEMINI-SIGNATURE": sig,
            "Cache-Control": "no-cache",
        }
        r = requests.post(url, headers=headers, timeout=20)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Connection / account
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        # Simple connectivity check via public endpoint
        r = requests.get(f"{self.base_url}/v1/symbols", timeout=15)
        r.raise_for_status()
        # Optional: try a private ping (balances) if keys were provided
        try:
            _ = self.get_account()
        except Exception:
            # If private fails, still consider connected for public ops
            pass
        self._connected = True
        return True

    def get_account(self) -> Dict[str, Any]:
        # Gemini doesn't have "account" like equities; use balances
        try:
            balances = self._signed_post("/v1/balances", {})
        except Exception:
            # If keys missing/invalid, return an empty account stub
            return {
                "portfolio_value": 0.0,
                "buying_power": 0.0,
                "currency": "USD",
                "status": "no-auth",
            }

        # Very rough: sum USD/USDT balances as "buying power"
        buying_power = 0.0
        for b in balances:
            cur = b.get("currency", "").upper()
            amt = float(b.get("amount", 0.0) or 0.0)
            if cur in ("USD", "USDT"):
                buying_power += amt

        return {
            "portfolio_value": buying_power,  # placeholder; true PV needs pricing
            "buying_power": buying_power,
            "currency": "USD",
            "status": "ok",
        }

    # ------------------------------------------------------------------
    # Market data / symbols / positions
    # ------------------------------------------------------------------
    def list_symbols(self) -> List[str]:
        if not self._connected:
            raise RuntimeError("Not connected")
        r = requests.get(f"{self.base_url}/v1/symbols", timeout=20)
        r.raise_for_status()
        # Gemini returns symbols like "btcusd", "ethusd"
        raw = r.json()
        symbols: List[str] = []
        for s in raw:
            s = s.upper()
            # normalize to BASE/QUOTE format
            if s.endswith("USD"):
                base = s[:-3]
                quote = "USD"
                norm = f"{base}/{quote}"
                symbols.append(norm)
            elif s.endswith("USDT"):
                base = s[:-4]
                quote = "USDT"
                norm = f"{base}/{quote}"
                symbols.append(norm)

        # Optional filter (default USDT per your rule)
        if self.quote_filter:
            symbols = [x for x in symbols if x.endswith("/" + self.quote_filter)]

        return sorted(set(symbols))

    def get_positions(self) -> List[Dict[str, Any]]:
        # Gemini is balance-based; positions concept is approximate.
        # We return non-zero crypto balances as "positions".
        try:
            balances = self._signed_post("/v1/balances", {})
        except Exception:
            return []

        out: List[Dict[str, Any]] = []
        for b in balances:
            cur = b.get("currency", "").upper()
            amt = float(b.get("amount", 0.0) or 0.0)
            if cur not in ("USD", "USDT") and amt > 0:
                out.append({"symbol": f"{cur}/USDT", "qty": amt})
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

        # Enforce your rule for BTC/USDT (and similar)
        base, quote = symbol.split("/")
        base = base.upper()
        quote = quote.upper()
        if quote != "USDT":
            raise ValueError("For safety, only *USDT-quoted* pairs are allowed here.")

        # Gemini "symbol" format is lowercase and without slash: e.g., "btcusdt"
        gem_symbol = f"{base}{quote}".lower()

        # For market orders, Gemini uses "type": "exchange market"
        order_type_map = {
            "market": "exchange market",
            "limit": "exchange limit",
        }
        gem_type = order_type_map.get(order_type.lower(), "exchange market")

        payload = {
            "symbol": gem_symbol,
            "amount": str(qty),
            "side": side,
            "type": gem_type,
        }
        # NOTE: For limit orders you must also include "price".
        # We keep this basic for now.

        return self._signed_post("/v1/order/new", payload)

    def close_position(self, symbol: str) -> Any:
        # For crypto, "closing" means placing a market order on the opposite side
        base, quote = symbol.split("/")
        base = base.upper()
        quote = quote.upper()
        # You'd look up the current balance of BASE and sell it (or buy to cover)
        # Simplified: attempt to sell entire base balance
        try:
            balances = self._signed_post("/v1/balances", {})
        except Exception:
            return {"status": "no-auth"}

        base_amt = 0.0
        for b in balances:
            if b.get("currency", "").upper() == base:
                base_amt = float(b.get("available", b.get("amount", 0)) or 0.0)
                break
        if base_amt <= 0:
            return {"status": "no-position"}

        return self.place_order(symbol, qty=base_amt, side="sell", order_type="market")

    def close_all_positions(self) -> Any:
        # Iterate balances and market-sell non-USD/USDT assets
        try:
            balances = self._signed_post("/v1/balances", {})
        except Exception:
            return {"status": "no-auth"}

        results = []
        for b in balances:
            cur = b.get("currency", "").upper()
            if cur in ("USD", "USDT"):
                continue
            amt = float(b.get("available", b.get("amount", 0)) or 0.0)
            if amt > 0:
                sym = f"{cur}/USDT"
                try:
                    res = self.place_order(sym, qty=amt, side="sell", order_type="market")
                    results.append({sym: res})
                except Exception as e:
                    results.append({sym: f"error: {e}"})
        return {"closed": results}

=======
# filename: app/broker_gemini.py
"""
AIMn Trading System — Gemini Broker Adapter

Implements the BrokerBase interface for Gemini (production or sandbox).

Notes
-----
- Public endpoints require no auth (symbols, ticker).
- Private endpoints require HMAC-SHA384 signing with:
    X-GEMINI-APIKEY
    X-GEMINI-PAYLOAD (base64 of JSON)
    X-GEMINI-SIGNATURE (hex of HMAC-SHA384 over payload)
- Base URLs:
    Production REST: https://api.gemini.com
    Sandbox REST:    https://api.sandbox.gemini.com

Caveats
-------
- Gemini is account/balance-based (crypto), not "positions" like equities.
- For your rule: Buy BTC only with USDT and sell only if holding BTC —
  we enforce a simple guard in place_order().
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import List, Dict, Any, Optional

import requests  # type: ignore

from .broker_base import BrokerBase


class GeminiBroker(BrokerBase):
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        super().__init__(api_key, api_secret, **kwargs)
        # Default to SANDBOX unless explicitly set
        self.base_url: str = kwargs.get("base_url", "https://api.sandbox.gemini.com")
        # Optional: filter quote currency (e.g., "USD" or "USDT")
        self.quote_filter: Optional[str] = kwargs.get("quote_filter", "USDT")
        self._connected = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _signed_post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a signed POST to Gemini private endpoint.
        """
        url = f"{self.base_url}{path}"
        payload["request"] = path
        payload["nonce"] = str(int(time.time() * 1000))

        encoded = json.dumps(payload).encode()
        b64 = base64.b64encode(encoded)
        sig = hmac.new(
            self.api_secret.encode(), b64, hashlib.sha384
        ).hexdigest()

        headers = {
            "Content-Type": "text/plain",
            "Content-Length": "0",
            "X-GEMINI-APIKEY": self.api_key,
            "X-GEMINI-PAYLOAD": b64.decode(),
            "X-GEMINI-SIGNATURE": sig,
            "Cache-Control": "no-cache",
        }
        r = requests.post(url, headers=headers, timeout=20)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Connection / account
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        # Simple connectivity check via public endpoint
        r = requests.get(f"{self.base_url}/v1/symbols", timeout=15)
        r.raise_for_status()
        # Optional: try a private ping (balances) if keys were provided
        try:
            _ = self.get_account()
        except Exception:
            # If private fails, still consider connected for public ops
            pass
        self._connected = True
        return True

    def get_account(self) -> Dict[str, Any]:
        # Gemini doesn't have "account" like equities; use balances
        try:
            balances = self._signed_post("/v1/balances", {})
        except Exception:
            # If keys missing/invalid, return an empty account stub
            return {
                "portfolio_value": 0.0,
                "buying_power": 0.0,
                "currency": "USD",
                "status": "no-auth",
            }

        # Very rough: sum USD/USDT balances as "buying power"
        buying_power = 0.0
        for b in balances:
            cur = b.get("currency", "").upper()
            amt = float(b.get("amount", 0.0) or 0.0)
            if cur in ("USD", "USDT"):
                buying_power += amt

        return {
            "portfolio_value": buying_power,  # placeholder; true PV needs pricing
            "buying_power": buying_power,
            "currency": "USD",
            "status": "ok",
        }

    # ------------------------------------------------------------------
    # Market data / symbols / positions
    # ------------------------------------------------------------------
    def list_symbols(self) -> List[str]:
        if not self._connected:
            raise RuntimeError("Not connected")
        r = requests.get(f"{self.base_url}/v1/symbols", timeout=20)
        r.raise_for_status()
        # Gemini returns symbols like "btcusd", "ethusd"
        raw = r.json()
        symbols: List[str] = []
        for s in raw:
            s = s.upper()
            # normalize to BASE/QUOTE format
            if s.endswith("USD"):
                base = s[:-3]
                quote = "USD"
                norm = f"{base}/{quote}"
                symbols.append(norm)
            elif s.endswith("USDT"):
                base = s[:-4]
                quote = "USDT"
                norm = f"{base}/{quote}"
                symbols.append(norm)

        # Optional filter (default USDT per your rule)
        if self.quote_filter:
            symbols = [x for x in symbols if x.endswith("/" + self.quote_filter)]

        return sorted(set(symbols))

    def get_positions(self) -> List[Dict[str, Any]]:
        # Gemini is balance-based; positions concept is approximate.
        # We return non-zero crypto balances as "positions".
        try:
            balances = self._signed_post("/v1/balances", {})
        except Exception:
            return []

        out: List[Dict[str, Any]] = []
        for b in balances:
            cur = b.get("currency", "").upper()
            amt = float(b.get("amount", 0.0) or 0.0)
            if cur not in ("USD", "USDT") and amt > 0:
                out.append({"symbol": f"{cur}/USDT", "qty": amt})
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

        # Enforce your rule for BTC/USDT (and similar)
        base, quote = symbol.split("/")
        base = base.upper()
        quote = quote.upper()
        if quote != "USDT":
            raise ValueError("For safety, only *USDT-quoted* pairs are allowed here.")

        # Gemini "symbol" format is lowercase and without slash: e.g., "btcusdt"
        gem_symbol = f"{base}{quote}".lower()

        # For market orders, Gemini uses "type": "exchange market"
        order_type_map = {
            "market": "exchange market",
            "limit": "exchange limit",
        }
        gem_type = order_type_map.get(order_type.lower(), "exchange market")

        payload = {
            "symbol": gem_symbol,
            "amount": str(qty),
            "side": side,
            "type": gem_type,
        }
        # NOTE: For limit orders you must also include "price".
        # We keep this basic for now.

        return self._signed_post("/v1/order/new", payload)

    def close_position(self, symbol: str) -> Any:
        # For crypto, "closing" means placing a market order on the opposite side
        base, quote = symbol.split("/")
        base = base.upper()
        quote = quote.upper()
        # You'd look up the current balance of BASE and sell it (or buy to cover)
        # Simplified: attempt to sell entire base balance
        try:
            balances = self._signed_post("/v1/balances", {})
        except Exception:
            return {"status": "no-auth"}

        base_amt = 0.0
        for b in balances:
            if b.get("currency", "").upper() == base:
                base_amt = float(b.get("available", b.get("amount", 0)) or 0.0)
                break
        if base_amt <= 0:
            return {"status": "no-position"}

        return self.place_order(symbol, qty=base_amt, side="sell", order_type="market")

    def close_all_positions(self) -> Any:
        # Iterate balances and market-sell non-USD/USDT assets
        try:
            balances = self._signed_post("/v1/balances", {})
        except Exception:
            return {"status": "no-auth"}

        results = []
        for b in balances:
            cur = b.get("currency", "").upper()
            if cur in ("USD", "USDT"):
                continue
            amt = float(b.get("available", b.get("amount", 0)) or 0.0)
            if amt > 0:
                sym = f"{cur}/USDT"
                try:
                    res = self.place_order(sym, qty=amt, side="sell", order_type="market")
                    results.append({sym: res})
                except Exception as e:
                    results.append({sym: f"error: {e}"})
        return {"closed": results}

>>>>>>> 0c0df91 (Initial push)
