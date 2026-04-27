# path: server/params_api_table.py
# run:  uvicorn --app-dir server params_api_table:app --host 127.0.0.1 --port 9000 --reload

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict
import os, pymysql

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "")
DB_NAME = os.environ.get("DB_NAME", "MeirNiv$default")

def conn():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset="utf8mb4", autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )

def q(sql, args=()):
    with conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, args)
            return cur

app = FastAPI(title="AIMn Params API (existing table)", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class Key(BaseModel):
    user_id: int = 1
    broker: str = "Alpaca"
    symbol: str
    timeframe: str = "1h"
    trade_mode: str = Field(pattern="^(BUY|SELL)$")

class EntryParams(BaseModel):
    rsi_window: int
    oversold_level: float
    overbought_level: float
    macd_fast: int
    macd_slow: int
    macd_signal: int
    vol_ma_length: int
    vol_threshold: float
    use_volume_filter: bool
    atr_length: int
    atr_ma_length: int
    atr_threshold: float
    use_atr_filter: bool

class ExitParams(BaseModel):
    stop_loss_pct: float
    early_trail_start: float
    early_trail_minus: float
    peak_trail_start: float
    peak_trail_minus: float
    rsi_exit_buy: float
    rsi_exit_sell: float
    rsi_exit_min_profit: float

class ParamsIn(BaseModel):
    key: Key
    entry: EntryParams
    exit: ExitParams
    flags: Optional[Dict[str, bool]] = None

class ParamsOut(BaseModel):
    key: Key
    entry: EntryParams
    exit: ExitParams
    flags: Dict[str, bool]
    updated_at: Optional[str] = None

def _to_bool(x): return 1 if bool(x) else 0
def _from_bool(x): return bool(x)

def ensure_unique():
    try:
        q("""ALTER TABLE strategy_params
             ADD UNIQUE KEY uniq_params (user_id, broker, symbol, timeframe, trade_mode)""")
    except Exception:
        pass

@app.on_event("startup")
def _startup():
    ensure_unique()

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/params2", response_model=ParamsOut)
def get_params2(user_id: int, broker: str, symbol: str, timeframe: str, trade_mode: str):
    cur = q("""
      SELECT * FROM strategy_params
      WHERE user_id=%s AND broker=%s AND symbol=%s AND timeframe=%s AND trade_mode=%s
      ORDER BY id DESC LIMIT 1
    """, (user_id, broker, symbol, timeframe, trade_mode))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="params not found")

    entry = EntryParams(
        rsi_window=row["rsi_window"],
        oversold_level=row["oversold_level"],
        overbought_level=row["overbought_level"],
        macd_fast=row["macd_fast"],
        macd_slow=row["macd_slow"],
        macd_signal=row["macd_signal"],
        vol_ma_length=row["vol_ma_length"],
        vol_threshold=row["vol_threshold"],
        use_volume_filter=_from_bool(row["use_volume_filter"]),
        atr_length=row["atr_length"],
        atr_ma_length=row["atr_ma_length"],
        atr_threshold=row["atr_threshold"],
        use_atr_filter=_from_bool(row["use_atr_filter"]),
    )
    exitp = ExitParams(
        stop_loss_pct=row["stop_loss_pct"],
        early_trail_start=row["early_trail_start"],
        early_trail_minus=row["early_trail_minus"],
        peak_trail_start=row["peak_trail_start"],
        peak_trail_minus=row["peak_trail_minus"],
        rsi_exit_buy=row["rsi_exit_buy"],
        rsi_exit_sell=row["rsi_exit_sell"],
        rsi_exit_min_profit=row["rsi_exit_min_profit"],
    )
    flags = dict(
        enable_alerts=_from_bool(row["enable_alerts"]),
        show_lines=_from_bool(row["show_lines"]),
        show_signals=_from_bool(row["show_signals"]),
    )
    return ParamsOut(
        key=Key(user_id=user_id, broker=broker, symbol=symbol, timeframe=timeframe, trade_mode=trade_mode),
        entry=entry, exit=exitp, flags=flags, updated_at=str(row.get("updated_at"))
    )

@app.post("/api/params2", response_model=ParamsOut)
def set_params2(data: ParamsIn):
    k = data.key
    E, X = data.entry, data.exit
    flags = data.flags or {}

    sql = """
    INSERT INTO strategy_params
    (user_id, broker, symbol, timeframe, trade_mode,
     rsi_window, oversold_level, overbought_level, rsi_exit_buy, rsi_exit_sell,
     macd_fast, macd_slow, macd_signal,
     vol_ma_length, vol_threshold, use_volume_filter,
     atr_length, atr_ma_length, atr_threshold, use_atr_filter,
     stop_loss_pct, early_trail_start, early_trail_minus,
     peak_trail_start, peak_trail_minus, rsi_exit_min_profit,
     enable_alerts, show_lines, show_signals, updated_at, created_at)
    VALUES
    (%s,%s,%s,%s,%s,
     %s,%s,%s,%s,%s,
     %s,%s,%s,
     %s,%s,%s,
     %s,%s,%s,%s,
     %s,%s,%s,
     %s,%s,%s,
     %s,%s,%s, NOW(), NOW())
    ON DUPLICATE KEY UPDATE
      rsi_window=VALUES(rsi_window),
      oversold_level=VALUES(oversold_level),
      overbought_level=VALUES(overbought_level),
      rsi_exit_buy=VALUES(rsi_exit_buy),
      rsi_exit_sell=VALUES(rsi_exit_sell),
      macd_fast=VALUES(macd_fast),
      macd_slow=VALUES(macd_slow),
      macd_signal=VALUES(macd_signal),
      vol_ma_length=VALUES(vol_ma_length),
      vol_threshold=VALUES(vol_threshold),
      use_volume_filter=VALUES(use_volume_filter),
      atr_length=VALUES(atr_length),
      atr_ma_length=VALUES(atr_ma_length),
      atr_threshold=VALUES(atr_threshold),
      use_atr_filter=VALUES(use_atr_filter),
      stop_loss_pct=VALUES(stop_loss_pct),
      early_trail_start=VALUES(early_trail_start),
      early_trail_minus=VALUES(early_trail_minus),
      peak_trail_start=VALUES(peak_trail_start),
      peak_trail_minus=VALUES(peak_trail_minus),
      rsi_exit_min_profit=VALUES(rsi_exit_min_profit),
      enable_alerts=VALUES(enable_alerts),
      show_lines=VALUES(show_lines),
      show_signals=VALUES(show_signals),
      updated_at=NOW()
    """
    args = (
        k.user_id, k.broker, k.symbol, k.timeframe, k.trade_mode,
        E.rsi_window, E.oversold_level, E.overbought_level, X.rsi_exit_buy, X.rsi_exit_sell,
        E.macd_fast, E.macd_slow, E.macd_signal,
        E.vol_ma_length, E.vol_threshold, _to_bool(E.use_volume_filter),
        E.atr_length, E.atr_ma_length, E.atr_threshold, _to_bool(E.use_atr_filter),
        X.stop_loss_pct, X.early_trail_start, X.early_trail_minus,
        X.peak_trail_start, X.peak_trail_minus, X.rsi_exit_min_profit,
        _to_bool(flags.get("enable_alerts", True)),
        _to_bool(flags.get("show_lines", True)),
        _to_bool(flags.get("show_signals", True)),
    )
    q(sql, args)
    return get_params2(k.user_id, k.broker, k.symbol, k.timeframe, k.trade_mode)
