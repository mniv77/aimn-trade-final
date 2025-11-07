# FILE: blueprints/trading_api.py
from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from typing import Dict, Optional

from flask import Blueprint, jsonify, request

trading_api = Blueprint("trading_api", __name__)

# ----------------------------------------------------------------------
# In-memory trade registry (simple and process-local)
# ----------------------------------------------------------------------
@dataclass
class TradeState:
    symbol: str
    exchange: str
    side: str                 # BUY or SELL
    qty: float
    entry_price: float
    entry_ts: float
    exit_price: Optional[float] = None
    exit_ts: Optional[float] = None
    reason: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.exit_ts is None

    def pnl_pct(self, last_price: Optional[float] = None) -> float:
        # When open, compute unrealized; when closed, realized.
        price = self.exit_price if not self.is_open else (last_price or self.entry_price)
        if self.side.upper() == "BUY":
            return (price - self.entry_price) / self.entry_price * 100.0
        else:
            return (self.entry_price - price) / self.entry_price * 100.0

# symbol -> TradeState
_TRADES: Dict[str, TradeState] = {}

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _require_json(keys: list[str]) -> dict:
    data = request.get_json(silent=True) or {}
    missing = [k for k in keys if k not in data]
    if missing:
        return None  # caller will handle
    return data

def _ok(payload, code=200):
    return jsonify(payload), code

def _err(message: str, code=400):
    return jsonify({"error": message}), code

# ----------------------------------------------------------------------
# Endpoints (note: NO /api/live_price here to avoid conflicts with app.py)
# ----------------------------------------------------------------------
@trading_api.post("/api/trade/open")
def trade_open():
    """
    Open or upsert a trade for a symbol. Idempotent by symbol.
    JSON: {symbol, exchange, side, qty, price}
    """
    must = ["symbol", "exchange", "side", "qty", "price"]
    data = _require_json(must)
    if data is None:
        return _err(f"Missing required keys: {must}", 400)

    symbol = str(data["symbol"]).strip().upper()
    exchange = str(data["exchange"]).strip().upper()
    side = str(data["side"]).strip().upper()
    try:
        qty = float(data["qty"])
        price = float(data["price"])
    except Exception:
        return _err("qty and price must be numeric", 400)

    if side not in ("BUY", "SELL"):
        return _err("side must be BUY or SELL", 400)
    if qty <= 0 or price <= 0:
        return _err("qty and price must be > 0", 400)

    ts = time.time()
    state = TradeState(
        symbol=symbol,
        exchange=exchange,
        side=side,
        qty=qty,
        entry_price=price,
        entry_ts=ts,
    )
    _TRADES[symbol] = state
    return _ok({"message": "opened", "trade": asdict(state)})

@trading_api.post("/api/trade/close")
def trade_close():
    """
    Close an existing trade by symbol.
    JSON: {symbol, price, reason?}
    """
    must = ["symbol", "price"]
    data = _require_json(must)
    if data is None:
        return _err(f"Missing required keys: {must}", 400)

    symbol = str(data["symbol"]).strip().upper()
    try:
        price = float(data["price"])
    except Exception:
        return _err("price must be numeric", 400)

    reason = str(data.get("reason") or "Manual/Strategy Exit")

    state = _TRADES.get(symbol)
    if not state:
        return _err("no open/known trade for symbol", 404)
    if not state.is_open:
        return _err("trade already closed", 409)

    state.exit_price = price
    state.exit_ts = time.time()
    state.reason = reason
    return _ok({
        "message": "closed",
        "trade": asdict(state),
        "pnl_pct": round(state.pnl_pct(), 4),
        "duration_sec": int(state.exit_ts - state.entry_ts),
    })

@trading_api.get("/api/trade/status")
def trade_status():
    """
    Get state for a symbol. Query args: ?symbol=XYZ
    """
    symbol = request.args.get("symbol", "").strip().upper()
    if not symbol:
        return _err("symbol required", 400)
    state = _TRADES.get(symbol)
    if not state:
        return _err("no trade", 404)
    # allow a real-time pnl calc if caller passes ?last=123.45
    last = request.args.get("last")
    last_f = None
    if last is not None:
        try:
            last_f = float(last)
        except Exception:
            pass
    return _ok({
        "trade": asdict(state),
        "is_open": state.is_open,
        "pnl_pct": round(state.pnl_pct(last_f), 4),
    })

# ----------------------------------------------------------------------
# Optional, namespaced price helper to avoid /api/live_price collision
# (your app.py already exposes /api/live_price)
# ----------------------------------------------------------------------
@trading_api.get("/api/price")
def bp_price():
    """
    Lightweight price helper under this blueprint (won't collide with app.py).
    Accepts: ?symbol= & exchange=
    """
    from random import uniform
    symbol = request.args.get("symbol", "AAPL")
    exchange = request.args.get("exchange", "ALPACA")
    if "CRYPTO" in (exchange or "").upper():
        # keep same shape as app.py for consistency
        price = round(uniform(10000, 120000), 2)
    else:
        price = round(uniform(50, 550), 2)
    return _ok({"symbol": symbol, "exchange": exchange, "price": price})
