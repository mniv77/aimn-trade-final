# =========================================
# path: brokers/alpaca_client.py
# =========================================
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import alpaca_trade_api as tradeapi
except Exception:
    tradeapi = None

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
    def open_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        return OrderResult(ok=True, order_id="dry-open", side=side, symbol=symbol, qty=qty, raw={"mode":"dry"})
    def close_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        close_side = "sell" if side.upper()=="BUY" else "buy"
        return OrderResult(ok=True, order_id="dry-close", side=close_side, symbol=symbol, qty=qty, raw={"mode":"dry"})

class AlpacaBroker(BaseBroker):
    def __init__(self, key_id: str, secret_key: str, base_url: Optional[str] = None):
        if not tradeapi:
            raise RuntimeError("alpaca-trade-api not installed")
        self.api = tradeapi.REST(
            key_id=key_id,
            secret_key=secret_key,
            base_url=base_url or "https://paper-api.alpaca.markets",
            api_version="v2",
        )
        # fail fast if creds bad
        self.api.get_account()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(0.5), retry=retry_if_exception_type(Exception))
    def _submit(self, **kw):
        return self.api.submit_order(**kw)

    def open_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        try:
            o = self._submit(symbol=symbol, qty=str(qty), side=side.lower(), type="market", time_in_force="day")
            return OrderResult(ok=True, order_id=getattr(o, "id", ""), side=side, symbol=symbol, qty=qty, raw=getattr(o, "_raw", None))
        except Exception as e:
            return OrderResult(ok=False, order_id="", side=side, symbol=symbol, qty=qty, error=str(e))

    def close_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        close_side = "sell" if side.upper()=="BUY" else "buy"
        try:
            o = self._submit(symbol=symbol, qty=str(qty), side=close_side, type="market", time_in_force="day")
            return OrderResult(ok=True, order_id=getattr(o, "id", ""), side=close_side, symbol=symbol, qty=qty, raw=getattr(o, "_raw", None))
        except Exception as e:
            return OrderResult(ok=False, order_id="", side=close_side, symbol=symbol, qty=qty, error=str(e))
