# ==================================
# /scripts/bootstrap_seed.py (FULL)
# ==================================
from app.db import init_db, db_session
from app.models import StrategyParam, User
init_db()
if not db_session.query(User).first():
    db_session.add(User(username="admin"))
if not db_session.query(StrategyParam).filter_by(symbol="BTC/USD", timeframe="1m").first():
    db_session.add(StrategyParam(
        symbol="BTC/USD", timeframe="1m", mode="BUY",
        rsi_period=14, rsi_buy_whole=30, rsi_buy_decimal=0, rsi_sell_whole=70, rsi_sell_decimal=0,
        macd_fast=12, macd_slow=26, macd_signal=9, vol_window=20,
        weight_rsi=0.4, weight_macd=0.4, weight_vol=0.2, entry_threshold=0.6,
        trailing_pct_primary_whole=0, trailing_pct_primary_decimal=80,
        trailing_pct_secondary_whole=1, trailing_pct_secondary_decimal=50,
        trailing_start_whole=0, trailing_start_decimal=40,
        stop_loss_whole=1, stop_loss_decimal=0,
        rsi_exit_whole=70, rsi_exit_decimal=0,
        position_size_usd=50.0
    ))
db_session.commit()
print("Seeded.")
