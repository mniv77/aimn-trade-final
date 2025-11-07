# ======================================================================
# FILE: brokers/alpaca_client.py
# deps: alpaca-trade-api, tenacity
# ======================================================================
from __future__ import annotations
import os, uuid, time
from dataclasses import dataclass
from typing import Optional, Dict, Any

try:
    import alpaca_trade_api as tradeapi
except Exception:
    tradeapi = None  # optional; we fallback if missing

from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type


@dataclass
class OrderResult:
    ok: bool
    order_id: str
    side: str
    symbol: str
    qty: float
    raw: Dict[str, Any] | None = None
    error: str | None = None


class BaseBroker:
    def open_market(self, symbol: str, side: str, qty: float) -> OrderResult: ...
    def close_market(self, symbol: str, side: str, qty: float) -> OrderResult: ...


class DryRunBroker(BaseBroker):
    """Fallback: records intent only. Safe on servers without creds."""
    def open_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        oid = f"dry-{uuid.uuid4().hex[:10]}"
        return OrderResult(ok=True, order_id=oid, side=side, symbol=symbol, qty=qty, raw={"mode":"dryrun"})

    def close_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        oid = f"dry-close-{uuid.uuid4().hex[:10]}"
        return OrderResult(ok=True, order_id=oid, side=side, symbol=symbol, qty=qty, raw={"mode":"dryrun"})


class AlpacaBroker(BaseBroker):
    """Minimal wrapper around alpaca-trade-api for paper/live trading."""
    def __init__(self, api: tradeapi.REST):
        self.api = api

    @classmethod
    def from_env_or_dummy(cls) -> BaseBroker:
        key = os.getenv("APCA_API_KEY_ID")
        secret = os.getenv("APCA_API_SECRET_KEY")
        base = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
        if tradeapi and key and secret:
            api = tradeapi.REST(key_id=key, secret_key=secret, base_url=base, api_version="v2")
            try:
                api.get_account()  # sanity
                return cls(api)
            except Exception:
                pass
        return DryRunBroker()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(0.6), retry=retry_if_exception_type(Exception))
    def _submit(self, **kwargs):
        return self.api.submit_order(**kwargs)

    def open_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        try:
            o = self._submit(symbol=symbol, qty=str(qty), side=side.lower(),
                             type="market", time_in_force="day")
            return OrderResult(ok=True, order_id=o.id, side=side, symbol=symbol, qty=qty, raw=o._raw)
        except Exception as e:
            return OrderResult(ok=False, order_id="", side=side, symbol=symbol, qty=qty, error=str(e))

    def close_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        """Place reverse market order to close."""
        close_side = "sell" if side.upper() == "BUY" else "buy"
        try:
            o = self._submit(symbol=symbol, qty=str(qty), side=close_side,
                             type="market", time_in_force="day")
            return OrderResult(ok=True, order_id=o.id, side=close_side, symbol=symbol, qty=qty, raw=o._raw)
        except Exception as e:
            return OrderResult(ok=False, order_id="", side=close_side, symbol=symbol, qty=qty, error=str(e))
