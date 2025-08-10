# /app/models.py
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, JSON, UniqueConstraint
from sqlalchemy.sql import func
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    # Single-user system: seed one user row if needed.

class StrategyParam(Base):
    __tablename__ = "strategy_params"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False)            # e.g., "BTC/USD"
    timeframe = Column(String(16), nullable=False)         # e.g., "1m"
    rsi_period = Column(Integer, default=14)
    rsi_buy = Column(Float, default=30.0)
    rsi_sell = Column(Float, default=70.0)
    macd_fast = Column(Integer, default=12)
    macd_slow = Column(Integer, default=26)
    macd_signal = Column(Integer, default=9)
    vol_window = Column(Integer, default=20)
    weight_rsi = Column(Float, default=0.4)
    weight_macd = Column(Float, default=0.4)
    weight_vol = Column(Float, default=0.2)
    entry_threshold = Column(Float, default=0.6)
    trailing_pct_primary = Column(Float, default=0.8)      # %
    trailing_pct_secondary = Column(Float, default=1.5)    # %
    position_size_usd = Column(Float, default=50.0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("symbol", "timeframe", name="uq_symbol_tf"), )

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

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False)
    side = Column(String(4), nullable=False)               # "buy"/"sell"
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    pnl = Column(Float)
    meta = Column(JSON)
    ts = Column(DateTime, server_default=func.now())

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