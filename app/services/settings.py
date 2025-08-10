# /app/services/settings.py
from dataclasses import dataclass
from typing import Dict, Tuple
from .db import db_session
from .models import StrategyParam, RuntimeState
from datetime import datetime

@dataclass
class ParamBundle:
    rsi_period:int; rsi_buy:float; rsi_sell:float
    macd_fast:int; macd_slow:int; macd_signal:int
    vol_window:int
    weight_rsi:float; weight_macd:float; weight_vol:float
    entry_threshold:float
    trailing_pct_primary:float; trailing_pct_secondary:float
    position_size_usd:float

class SettingsService:
    _cache: Dict[Tuple[str, str], ParamBundle] = {}
    def refresh_cache(self):
        self._cache.clear()
        for p in db_session.query(StrategyParam).all():
            self._cache[(p.symbol, p.timeframe)] = ParamBundle(
                p.rsi_period, p.rsi_buy, p.rsi_sell,
                p.macd_fast, p.macd_slow, p.macd_signal,
                p.vol_window, p.weight_rsi, p.weight_macd, p.weight_vol,
                p.entry_threshold, p.trailing_pct_primary, p.trailing_pct_secondary,
                p.position_size_usd
            )
    def get_params(self, symbol: str, timeframe: str) -> ParamBundle:
        key = (symbol, timeframe)
        if key not in self._cache:
            p = db_session.query(StrategyParam).filter_by(symbol=symbol, timeframe=timeframe).one_or_none()
            if not p:
                raise KeyError(f"No params for {symbol} {timeframe}")
            self.refresh_cache()
        return self._cache[key]
    def get_runtime(self) -> RuntimeState:
        rt = db_session.query(RuntimeState).get(1)
        if not rt:
            from .db import db_session
            from .models import RuntimeState as RS
            rt = RS(id=1, bot_enabled=False, mode="paper")
            db_session.add(rt); db_session.commit()
        return rt
    def set_runtime(self, enabled: bool = None, mode: str = None):
        rt = self.get_runtime()
        if enabled is not None: rt.bot_enabled = enabled
        if mode: rt.mode = mode
        rt.last_heartbeat = datetime.utcnow()
        db_session.commit()
        return rt
        # Inside your existing SettingsService class, ADD this method:
from .models import LoopTarget, StrategyParam
from .db import db_session

class SettingsService:
    # ... keep your existing methods

    def get_loop_symbols(self) -> list[tuple[str, str]]:
        """
        Returns list of (symbol, timeframe) that the worker should scan.
        If none selected, falls back to all StrategyParam profiles.
        """
        rows = db_session.query(LoopTarget).all()
        if rows:
            return [(r.symbol, r.timeframe) for r in rows]
        # fallback: all profiles
        profs = db_session.query(StrategyParam).order_by(StrategyParam.symbol, StrategyParam.timeframe).all()
        return [(p.symbol, p.timeframe) for p in profs]