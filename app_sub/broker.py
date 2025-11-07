# /app/broker.py
import os, time, json, requests
from typing import Literal
from .security import get_alpaca_keys
from .services.settings import SettingsService

AlpacaURL = "https://paper-api.alpaca.markets"  # switch by mode if needed

def _headers(key_id, secret):
    return {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret}

def place_order(symbol:str, side:Literal["buy","sell"], qty:float, mode:str="paper") -> dict:
    key, sec = get_alpaca_keys(paper=(mode=="paper"))
    url = f"{AlpacaURL}/v2/orders"
    data = dict(symbol=symbol.replace("/",""), qty=str(qty), side=side, type="market", time_in_force="gtc")
    r = requests.post(url, headers=_headers(key, sec), json=data, timeout=10)
    if r.status_code >= 400:
        raise RuntimeError(f"Order error {r.status_code}: {r.text}")
    return r.json()