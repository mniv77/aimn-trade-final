# alpaca_client.py
import os
import requests

ALPACA_KEY       = os.environ.get("ALPACA_KEY", "YOUR_ALPACA_KEY_HERE")
ALPACA_SECRET    = os.environ.get("ALPACA_SECRET", "YOUR_ALPACA_SECRET_HERE")
ALPACA_BASE_URL  = os.environ.get(
    "ALPACA_BASE_URL",
    "https://paper-api.alpaca.markets"
)

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
    "Content-Type": "application/json",
}

def place_market_order(symbol: str, side: str, qty: float):
    """
    Place a market order at Alpaca (paper).
    Returns JSON with order info or raises Exception.
    """
    import json

    url = f"{ALPACA_BASE_URL}/v2/orders"
    payload = {
        "symbol": symbol,
        "qty": str(qty),
        "side": side.lower(),          # "buy" or "sell"
        "type": "market",
        "time_in_force": "day"
    }

    resp = requests.post(url, headers=HEADERS, json=payload, timeout=10)
    if resp.status_code >= 300:
        raise Exception(f"Alpaca order error: {resp.status_code} {resp.text}")
    return resp.json()


def get_latest_price(symbol: str) -> float:
    """
    Fetch latest trade price for a symbol from Alpaca.
    Very simple version, using /v2/stocks/{symbol}/trades/latest
    """
    url = f"{ALPACA_BASE_URL}/v2/stocks/{symbol}/trades/latest"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code >= 300:
        raise Exception(f"Alpaca price error: {resp.status_code} {resp.text}")
    data = resp.json()
    # Data shape: {"symbol": "...", "trade": {"p": price, "t": "...", ...}}
    return float(data["trade"]["p"])
