from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from ..db import db_session
from ..models import RuntimeState
from shared_models import StrategyParam

def _num_from_parts(whole: int | None, dec: int | None) -> float:
    w = whole or 0
    d = dec or 0
    return float(w) + float(d) / 100.0


@dataclass
class ParamBundle:
    rsi_period: int
    rsi_buy: float
    rsi_sell: float
    macd_fast: int
    macd_slow: int
    macd_signal: int
    vol_window: int
    weight_rsi: float
    weight_macd: float
    weight_vol: float
    entry_threshold: float
    trailing_pct_primary: float
    trailing_pct_secondary: float
    trailing_start: float
    stop_loss: float
    rsi_exit: float
    position_size_usd: float
    mode: str


class SettingsService:
    _cache: Dict[Tuple[str, str], ParamBundle] = {}

    def refresh_cache(self) -> None:
        self._cache.clear()
        rows = db_session.query(StrategyParam).all()
        for p in rows:
            # --- handle old/new schema seamlessly ---
            # RSI buy/sell
            rsi_buy = getattr(p, "rsi_buy", None)
            if rsi_buy is None and hasattr(p, "rsi_buy_whole"):
                rsi_buy = _num_from_parts(
                    getattr(p, "rsi_buy_whole", 30),
                    getattr(p, "rsi_buy_decimal", 0),
                )

            rsi_sell = getattr(p, "rsi_sell", None)
            if rsi_sell is None and hasattr(p, "rsi_sell_whole"):
                rsi_sell = _num_from_parts(
                    getattr(p, "rsi_sell_whole", 70),
                    getattr(p, "rsi_sell_decimal", 0),
                )

            # Trailing primary/secondary
            tpri = getattr(p, "trailing_pct_primary", None)
            if tpri is None and hasattr(p, "trailing_pct_primary_whole"):
                tpri = _num_from_parts(
                    getattr(p, "trailing_pct_primary_whole", 1),
                    getattr(p, "trailing_pct_primary_decimal", 0),
                )

            tsec = getattr(p, "trailing_pct_secondary", None)
            if tsec is None and hasattr(p, "trailing_pct_secondary_whole"):
                tsec = _num_from_parts(
                    getattr(p, "trailing_pct_secondary_whole", 2),
                    getattr(p, "trailing_pct_secondary_decimal", 0),
                )

            # Trailing start, stop loss, RSI exit
            tstart = getattr(p, "trailing_start", None)
            if tstart is None and hasattr(p, "trailing_start_whole"):
                tstart = _num_from_parts(
                    getattr(p, "trailing_start_whole", 1),
                    getattr(p, "trailing_start_decimal", 0),
                )

            stop = getattr(p, "stop_loss", None)
            if stop is None and hasattr(p, "stop_loss_whole"):
                stop = _num_from_parts(
                    getattr(p, "stop_loss_whole", 1),
                    getattr(p, "stop_loss_decimal", 0),
                )

            rsi_exit = getattr(p, "rsi_exit", None)
            if rsi_exit is None and hasattr(p, "rsi_exit_whole"):
                rsi_exit = _num_from_parts(
                    getattr(p, "rsi_exit_whole", 50),
                    getattr(p, "rsi_exit_decimal", 0),
                )

            bundle = ParamBundle(
                rsi_period=getattr(p, "rsi_period", 14) or 14,
                rsi_buy=rsi_buy if rsi_buy is not None else 30.0,
                rsi_sell=rsi_sell if rsi_sell is not None else 70.0,
                macd_fast=getattr(p, "macd_fast", 12) or 12,
                macd_slow=getattr(p, "macd_slow", 26) or 26,
                macd_signal=getattr(p, "macd_signal", 9) or 9,
                vol_window=getattr(p, "vol_window", 20) or 20,
                weight_rsi=getattr(p, "weight_rsi", 0.5) or 0.5,
                weight_macd=getattr(p, "weight_macd", 0.3) or 0.3,
                weight_vol=getattr(p, "weight_vol", 0.2) or 0.2,
                entry_threshold=getattr(p, "entry_threshold", 0.0) or 0.0,
                trailing_pct_primary=tpri if tpri is not None else 1.0,
                trailing_pct_secondary=tsec if tsec is not None else 2.0,
                trailing_start=tstart if tstart is not None else 1.0,
                stop_loss=stop if stop is not None else 1.0,
                rsi_exit=rsi_exit if rsi_exit is not None else 50.0,
                position_size_usd=getattr(p, "position_size_usd", 100.0) or 100.0,
                mode=getattr(p, "mode", "BUY") or "BUY",
            )
            self._cache[(p.symbol, p.timeframe)] = bundle

    def get_params(self, symbol: str, timeframe: str) -> ParamBundle:
        key = (symbol, timeframe)
        if key not in self._cache:
            # lazy-load single row if missing
            p = (
                db_session.query(StrategyParam)
                .filter_by(symbol=symbol, timeframe=timeframe)
                .one_or_none()
            )
            if not p:
                raise KeyError(f"No params for {symbol} {timeframe}")
            self.refresh_cache()
        return self._cache[key]

    def get_runtime(self) -> RuntimeState:
        rt = db_session.get(RuntimeState, 1)
        if not rt:
            rt = RuntimeState(id=1)
            db_session.add(rt)
            db_session.commit()
        return rt

# --- injected: add set_runtime on SettingsService ---
try:
    _ = db_session.get
    _HAS_GET = True
except Exception:
    _HAS_GET = False

def _ss_set_runtime(self, *, enabled=None, mode=None):
    """Create/update the single RuntimeState row (id=1)."""
    if _HAS_GET:
        rt = db_session.get(RuntimeState, 1)
    else:
        rt = db_session.query(RuntimeState).get(1)
    if not rt:
        rt = RuntimeState(id=1)
        db_session.add(rt)
    if enabled is not None:
        rt.bot_enabled = bool(enabled)
    if mode is not None:
        rt.mode = str(mode)
    db_session.commit()
    return rt

if not hasattr(SettingsService, "set_runtime"):
    SettingsService.set_runtime = _ss_set_runtime
# --- end injected ---

    def get_loop_symbols(self):
        """
        Return list of (symbol, timeframe) tuples for the worker loop.
        Tries RuntimeState.{loop_selection|selected_pairs|loop_pairs},
        else falls back to distinct pairs in strategy_params, else BTC/USD|1m.
        """
        from sqlalchemy import text
        try:
            rt = db_session.get(RuntimeState, 1)
        except Exception:
            rt = db_session.query(RuntimeState).get(1)

        pairs = []
        if rt is not None:
            sel = None
            for attr in ("loop_selection", "selected_pairs", "loop_pairs"):
                if hasattr(rt, attr):
                    sel = getattr(rt, attr)
                    if sel:
                        break

            if isinstance(sel, str):
                for item in sel.split(','):
                    item = item.strip()
                    if not item:
                        continue
                    if '|' in item:
                        sym, tf = item.split('|', 1)
                    else:
                        sym, tf = item, "1m"
                    pairs.append((sym.strip(), tf.strip()))
            elif isinstance(sel, (list, tuple)):
                for item in sel:
                    if isinstance(item, str):
                        if '|' in item:
                            sym, tf = item.split('|', 1)
                        else:
                            sym, tf = item, "1m"
                        pairs.append((sym.strip(), tf.strip()))
                    elif isinstance(item, dict):
                        sym = item.get("symbol")
                        tf  = item.get("timeframe", "1m")
                        if sym:
                            pairs.append((sym, tf))

        if not pairs:
            rows = db_session.execute(
                text("SELECT DISTINCT symbol, timeframe FROM strategy_params LIMIT 5")
            ).fetchall()
            pairs = [(r[0], r[1]) for r in rows] or [("BTC/USD", "1m")]

        return pairs


# --- injected: ensure SettingsService.get_loop_symbols exists ---
try:
    SettingsService
except NameError:
    pass
else:
    if not hasattr(SettingsService, "get_loop_symbols"):
        from sqlalchemy import text
        def _get_loop_symbols(self):
            # try runtime state first
            try:
                rt = db_session.get(RuntimeState, 1)
            except Exception:
                rt = db_session.query(RuntimeState).get(1)
            pairs = []
            if rt is not None:
                sel = None
                for attr in ("loop_selection","selected_pairs","loop_pairs"):
                    if hasattr(rt, attr):
                        sel = getattr(rt, attr)
                        if sel:
                            break
                if isinstance(sel, str):
                    for item in sel.split(','):
                        item = item.strip()
                        if not item:
                            continue
                        if '|' in item:
                            sym, tf = item.split('|', 1)
                        else:
                            sym, tf = item, "1m"
                        pairs.append((sym.strip(), tf.strip()))
            # fallback: distinct pairs from strategy_params
            if not pairs:
                try:
                    rows = db_session.execute(text("SELECT DISTINCT symbol, timeframe FROM strategy_params LIMIT 5"))
                    pairs = [(r[0], r[1]) for r in rows]
                except Exception:
                    pass
            # final default
            if not pairs:
                pairs = [("BTC/USD", "1m")]
            return pairs
        SettingsService.get_loop_symbols = _get_loop_symbols
# --- end injected ---
