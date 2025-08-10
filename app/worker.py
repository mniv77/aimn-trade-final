# /app/worker.py
import time, traceback
from datetime import datetime
from .db import db_session
from .models import LogEvent, Trade, RuntimeState
from .services.settings import SettingsService
from .market_data import fetch_bars
from .scanner import score_row, should_enter
from .broker import place_order

def log(level, msg, meta=None):
    db_session.add(LogEvent(level=level, message=msg, meta=meta)); db_session.commit()

def heartbeat():
    svc = SettingsService()
    rt = svc.get_runtime()
    rt.last_heartbeat = datetime.utcnow()
    db_session.commit()

def run_once(symbol="BTC/USD", timeframe="1Min"):
    svc = SettingsService()
    params = svc.get_params(symbol, "1m") if timeframe.lower()=="1min" else svc.get_params(symbol, timeframe)
    df = fetch_bars(symbol, timeframe="1Min", limit=300)
    if df.empty or len(df) < max(params.rsi_period, params.macd_slow) + 5:
        log("WARN", "insufficient bars", {"symbol":symbol}); return
    score = score_row(df["close"], params)
    if should_enter(score, params.entry_threshold):
        qty = round(params.position_size_usd / float(df["close"].iloc[-1]), 6)
        try:
            order = place_order(symbol, "buy", qty, mode="paper")  # adjust mode
            db_session.add(Trade(symbol=symbol, side="buy", qty=qty, price=float(df["close"].iloc[-1]), meta=order))
            db_session.commit()
            log("INFO", "entered long", {"symbol":symbol,"qty":qty,"score":score})
        except Exception as e:
            log("ERROR", "order failed", {"err":str(e)})
    else:
        log("INFO", "no entry", {"symbol":symbol,"score":score})

def run_forever(poll_sec=60):
    svc = SettingsService()
    while True:
        try:
            if not svc.get_runtime().bot_enabled:
                time.sleep(poll_sec); heartbeat(); continue
            run_once()
            heartbeat()
        except Exception as e:
            log("ERROR", "loop error", {"err":str(e), "tb":traceback.format_exc()})
        time.sleep(poll_sec)