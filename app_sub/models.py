# /app/models.py
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, JSON, UniqueConstraint
from sqlalchemy.sql import func
from .db import Base
# Import shared models for database creation

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    # Single-user system: seed one user row if needed.

#class StrategyParam(Base):
#   __tablename__ = "strategy_params"
#   __table_args__ = (UniqueConstraint("symbol", "timeframe", name="uq_strategy_symbol_tf"),)

#   id = Column(Integer, primary_key=True)
#    symbol = Column(String(32), nullable=False, index=True)
#    timeframe = Column(String(16), nullable=False, index=True)

#    mode = Column(String(8), nullable=False, default="BUY")

#    rsi_period = Column(Integer, default=14)#
#    rsi_buy_decimal = Column(Integer, default=0)
#    rsi_sell_whole = Column(Integer, default=70)
#    rsi_sell_decimal = Column(Integer, default=0)
#    macd_fast = Column(Integer, default=12)
#    macd_slow = Column(Integer, default=26)
#    vol_window = Column(Integer, default=20)

#    weight_rsi = Column(Float, default=0.5)
#    weight_macd = Column(Float, default=0.3)
#    weight_vol = Column(Float, default=0.2)
#    entry_threshold = Column(Float, default=1.0)

#    trailing_pct_primary_whole = Column(Integer, default=1)
#    trailing_pct_primary_decimal = Column(Integer, default=0)
#    trailing_pct_secondary_whole = Column(Integer, default=2)
#    trailing_pct_secondary_decimal = Column(Integer, default=0)
#    trailing_start_whole = Column(Integer, default=1)
#    trailing_start_decimal = Column(Integer, default=0)
#    stop_loss_whole = Column(Integer, default=1)
#    stop_loss_decimal = Column(Integer, default=0)
#    rsi_exit_whole = Column(Integer, default=50)
#    rsi_exit_decimal = Column(Integer, default=0)

#    position_size_usd = Column(Integer, default=50)

#    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
class ApiCredential(Base):
    __tablename__ = "api_credentials"
    id = Column(Integer, primary_key=True)
    venue = Column(String(32), nullable=False)             # "alpaca"
    key_id_enc = Column(Text, nullable=False)              # encrypted
    secret_enc = Column(Text, nullable=False)              # encrypted
    paper = Column(Boolean, default=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("venue", "paper", name="uq_venue_paper"), )

class RuntimeState(Base):
    __tablename__ = "runtime_state"
    id = Column(Integer, primary_key=True)
    bot_enabled = Column(Boolean, default=False)
    mode = Column(String(16), default="paper")             # "paper"|"live"
    last_heartbeat = Column(DateTime)
    notes = Column(Text)

#class Trade(Base):
#    __tablename__ = "trades"
#    id = Column(Integer, primary_key=True)
#    symbol = Column(String(32), nullable=False)
#    side = Column(String(4), nullable=False)               # "buy"/"sell"
#    qty = Column(Float, nullable=False)
#    price = Column(Float, nullable=False)
#    pnl = Column(Float)
#    meta = Column(JSON)
#    ts = Column(DateTime, server_default=func.now())

class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False, unique=True)
    qty = Column(Float, nullable=False, default=0.0)
    entry_price = Column(Float)
    trailing_primary = Column(Float)
    trailing_secondary = Column(Float)
    ts = Column(DateTime, server_default=func.now())

class LogEvent(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    level = Column(String(8), default="INFO")
    message = Column(Text, nullable=False)
    meta = Column(JSON)
    ts = Column(DateTime, server_default=func.now())

# Append this near your other models. Do NOT remove existing ones.
from sqlalchemy import Column, Integer, String, UniqueConstraint
from .db import Base

class LoopTarget(Base):
    __tablename__ = "loop_targets"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False)
    timeframe = Column(String(16), nullable=False)
    __table_args__ = (UniqueConstraint("symbol", "timeframe", name="uq_loop_symbol_tf"), )

class UiEvent(Base):
    __tablename__ = "ui_events"
    id   = Column(Integer, primary_key=True)
    kind = Column(String(32), nullable=False)   # trade_entry, trade_exit, etc.
    ref_id = Column(Integer, nullable=True)     # link to Trade.id (optional)
    ts   = Column(DateTime, nullable=False, server_default=func.now())
