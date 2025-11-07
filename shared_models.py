from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()



# Keep your existing classes:

class SignalAlert(Base):
    __tablename__ = "signal_alerts"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False)
    direction = Column(String(4), nullable=False)  # "BUY" or "SELL"
    exchange = Column(String(32), nullable=False)  # "Alpaca" or "Gemini"
    user_id = Column(String(64), nullable=False)
    signal_strength = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())
    processed = Column(Boolean, default=False)

class ExchangeState(Base):
    __tablename__ = "exchange_states"
    id = Column(Integer, primary_key=True)
    exchange = Column(String(32), nullable=False, unique=True)
    is_scanning = Column(Boolean, default=True)
    active_position_symbol = Column(String(32), nullable=True)
    last_heartbeat = Column(DateTime, server_default=func.now())
    emergency_stop = Column(Boolean, default=False)

# Add these new classes below - do NOT remove the above!

class StrategyParam(Base):
    __tablename__ = "strategy_params"

    id        = Column(Integer, primary_key=True)
    symbol    = Column(String(32), nullable=False)
    timeframe = Column(String(16), nullable=False)

    # RSI Parameters
    rsi_period       = Column(Integer, default=14)
    rsi_buy_whole    = Column(Integer, default=30)
    rsi_buy_decimal  = Column(Integer, default=0)
    rsi_sell_whole   = Column(Integer, default=70)
    rsi_sell_decimal = Column(Integer, default=0)

    # MACD Parameters
    macd_fast   = Column(Integer, default=12)
    macd_slow   = Column(Integer, default=26)
    macd_signal = Column(Integer, default=9)

    # Risk Management
    trailing_pct_primary_whole     = Column(Integer, default=1)
    trailing_pct_primary_decimal   = Column(Integer, default=0)
    trailing_pct_secondary_whole   = Column(Integer, default=2)
    trailing_pct_secondary_decimal = Column(Integer, default=0)
    stop_loss_whole                = Column(Integer, default=1)
    stop_loss_decimal              = Column(Integer, default=0)

    # Position Sizing
    position_size_usd = Column(Integer, default=50)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", name="uq_strategy_symbol_tf"),
    )

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False)
    side = Column(String(4), nullable=False)  # "BUY" or "SELL"
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    pnl = Column(Float)
    meta = Column(JSON)
    ts = Column(DateTime, server_default=func.now())



class BacktestResult(Base):
    __tablename__ = "backtest_results"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    compound_total_pct = Column(Float)
    n_trades = Column(Integer)
    win_rate = Column(Float)
    n_buy_orders = Column(Integer)
    n_sell_orders = Column(Integer)
    avg_trade_pct = Column(Float)
    max_drawdown = Column(Float)
    temporary = Column(Boolean, default=True)