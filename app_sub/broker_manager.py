# filename: app/broker_manager.py
"""
AIMn Trading System — Broker Manager

Purpose
-------
Central place to:
  • store/load credentials (now persisted + encrypted via app/state.py)
  • construct the correct broker adapter (Alpaca or Gemini)
  • cache a single connected instance per broker name

Usage
-----
from app.broker_manager import set_credentials, get_broker
set_credentials("Alpaca", key, secret, base_url="https://paper-api.alpaca.markets")
broker = get_broker("Alpaca")
acct = broker.get_account()
"""

from __future__ import annotations

from typing import Dict, Any

from .broker_base import BrokerBase
from .broker_alpaca import AlpacaBroker
from .broker_gemini import GeminiBroker
from . import state  # encrypted persistence

# ---------------------------------------------------------------------------
# Persistent + in-memory cache
# ---------------------------------------------------------------------------

# In-memory shadow (fast lookup during a session)
_CREDENTIALS: Dict[str, Dict[str, Any]] = {}
_BROKERS: Dict[str, BrokerBase] = {}


def set_credentials(broker_name: str, api_key: str, api_secret: str, **extra) -> None:
    """Save credentials (persist encrypted) and reset cached instance."""
    # Persist encrypted
    state.save_credentials(broker_name, api_key, api_secret)
    # Mirror in-memory (include extras like base_url/filters)
    _CREDENTIALS[broker_name] = {"api_key": api_key, "api_secret": api_secret, **extra}
    # Invalidate cached connected instance
    if broker_name in _BROKERS:
        try:
            del _BROKERS[broker_name]
        except Exception:
            pass


def _load_credentials(broker_name: str) -> Dict[str, Any]:
    # Prefer in-memory for speed
    cfg = _CREDENTIALS.get(broker_name)
    if cfg:
        return cfg
    # Fallback to encrypted storage
    key, secret = state.load_credentials(broker_name)
    if key or secret:
        cfg = {"api_key": key or "", "api_secret": secret or ""}
        _CREDENTIALS[broker_name] = cfg
        return cfg
    # No creds stored yet; return empty
    return {"api_key": "", "api_secret": ""}


def get_broker(broker_name: str) -> BrokerBase:
    """Return a connected broker instance for the given name."""
    if broker_name in _BROKERS:
        return _BROKERS[broker_name]

    cfg = _load_credentials(broker_name)
    api_key = cfg.get("api_key", "")
    api_secret = cfg.get("api_secret", "")

    if broker_name.lower() == "alpaca":
        base_url = cfg.get("base_url", "https://paper-api.alpaca.markets")
        asset_class = cfg.get("asset_class")  # optional list_symbols filter
        broker = AlpacaBroker(api_key, api_secret, base_url=base_url, asset_class=asset_class)
    elif broker_name.lower() == "gemini":
        base_url = cfg.get("base_url", "https://api.sandbox.gemini.com")
        quote_filter = cfg.get("quote_filter", "USDT")
        broker = GeminiBroker(api_key, api_secret, base_url=base_url, quote_filter=quote_filter)
    else:
        raise ValueError(f"Unknown broker: {broker_name}")

    broker.connect()
    _BROKERS[broker_name] = broker
    return broker


# Convenience wrappers used by UI / orchestrator

def list_symbols(broker_name: str):
    return get_broker(broker_name).list_symbols()


def get_account(broker_name: str):
    return get_broker(broker_name).get_account()


def get_positions(broker_name: str):
    return get_broker(broker_name).get_positions()


def place_order(broker_name: str, symbol: str, qty: float, side: str, order_type: str = "market"):
    return get_broker(broker_name).place_order(symbol, qty, side, order_type)


def close_position(broker_name: str, symbol: str):
    return get_broker(broker_name).close_position(symbol)


def close_all_positions(broker_name: str):
    return get_broker(broker_name).close_all_positions()
