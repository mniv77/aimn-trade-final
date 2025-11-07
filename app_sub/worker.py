# ======================
# 4) /app/worker.py (FULL)
# ======================
# Replace the whole file with this version (keeps your logic, adds loop reading).
import time, traceback
from datetime import datetime
from .db import db_session
from .models import LogEvent, Trade, RuntimeState, UiEvent, Position
from .services.settings import SettingsService
from .market_data import fetch_bars
from .scanner import should_enter
from .indicators import rsi
from .broker import place_order
from .position_manager import enter_position, evaluate_exit, close_position

def log(level, msg, meta=None):
    db_session.add(LogEvent(level=level, message=msg, meta=meta)); db_session.commit()

def heartbeat():
    svc = SettingsService()
    rt = svc.get_runtime()
    rt.last_heartbeat = datetime.utcnow()
    db_session.commit()

def run_once(symbol="BTC/USD", timeframe="1m", mode="paper"):
    svc = SettingsService()
    params = svc.get_params(symbol, timeframe)
    df = fetch_bars(symbol, timeframe="1Min", limit=400)
    if df.empty:
        log("WARN", "no bars", {"symbol":symbol, "tf":timeframe}); return
    close = df["close"]
    last_price = float(close.iloc[-1])
    r = float(rsi(close, params.rsi_period).iloc[-1])

    # Exit first
    ev = evaluate_exit(symbol, last_price, r, params)
    if ev.exit_now:
        try:
            tr = close_position(symbol, last_price, ev.reason, timeframe=timeframe)
            if tr:
                place_order(symbol, "sell", tr.qty, mode=mode)
                log("INFO", f"exit {symbol}", {"reason":ev.reason, "price":last_price})
        except Exception as e:
            log("ERROR", "exit order failed", {"err":str(e)})

    # Entry if no position
    has_pos = db_session.query(Position).filter_by(symbol=symbol).one_or_none() is not None
    if not has_pos and should_enter(close, params):
        qty = max(0.000001, round(params.position_size_usd / last_price, 6))
        try:
            place_order(symbol, "buy", qty, mode=mode)
            enter_position(symbol, qty, last_price)
            tr = Trade(symbol=symbol, side="buy", qty=qty, price=last_price,
                       meta={"entry":"signal","timeframe":timeframe})
            db_session.add(tr); db_session.commit()
            db_session.add(UiEvent(kind="trade_entry", ref_id=tr.id)); db_session.commit()
            log("INFO", "entered long", {"symbol":symbol,"qty":qty,"price":last_price})
        except Exception as e:
            log("ERROR", "entry failed", {"err":str(e)})

def run_forever(poll_sec=60, timeframe="1m"):
    svc = SettingsService()
    while True:
        heartbeat()
        try:
            rt = svc.get_runtime()
            if not rt.bot_enabled:
                time.sleep(poll_sec); heartbeat(); continue

            # Read loop selection from DB each cycle
            pairs = svc.get_loop_symbols()  # list[(symbol, timeframe)]
            if not pairs:
                pairs = [("BTC/USD", timeframe)]

            for sym, tf in pairs:
                run_once(sym, timeframe=tf, mode=rt.mode)

            heartbeat()
        except Exception as e:
            log("ERROR", "loop error", {"err":str(e), "tb":traceback.format_exc()})
        time.sleep(poll_sec)