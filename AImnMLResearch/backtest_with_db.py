# backtest_with_db.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from shared_models import StrategyParam, Trade, Base
import pandas as pd
from AImnMLResearch.indicator_utils import rsi_tv, macd, atr, sma, obv, volume_direction

# --- 1. DB Setup ---
DB_URI = "mysql+pymysql:// mniv77@gmail.com: Water@288zz@HOST/DATABASE?charset=utf8mb4"  # Replace with your actual DB URI
engine = create_engine(DB_URI, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
session = Session()

# --- 2. Fetch Parameters for Symbol/Timeframe ---
SYMBOL = "BTCUSD"
TIMEFRAME = "1h"
params_db = session.query(StrategyParam).filter_by(symbol=SYMBOL, timeframe=TIMEFRAME).first()
if not params_db:
    raise Exception(f"No parameters found for {SYMBOL} {TIMEFRAME}")

params = {
    'rsi_window': params_db.rsi_period,
    'oversold_level_int': params_db.rsi_buy_whole,
    'oversold_level_dec': params_db.rsi_buy_decimal / 10,  # Adjust if needed
    'rsi_exit_buy_int': params_db.rsi_sell_whole,
    'rsi_exit_buy_dec': params_db.rsi_sell_decimal / 10,   # Adjust if needed
    'macd_fast': params_db.macd_fast,
    'macd_slow': params_db.macd_slow,
    'macd_signal': params_db.macd_signal,
    'vol_ma_length': 20,             # Add your defaults or load from DB as needed
    'vol_threshold': 1.2,
    'use_vol_filter': True,
    'atr_length': 14,
    'atr_ma_length': 20,
    'atr_threshold': 1.3,
    'use_atr_filter': True,
    'stop_loss_int': params_db.stop_loss_whole,
    'stop_loss_dec': params_db.stop_loss_decimal / 10,     # Adjust if needed
    'early_trail_start_int': params_db.trailing_pct_primary_whole,
    'early_trail_start_dec': params_db.trailing_pct_primary_decimal / 10,
    'early_trail_minus_int': 15,      # Example value
    'early_trail_minus_dec': 0.0,
    'peak_trail_start_int': params_db.trailing_pct_secondary_whole,
    'peak_trail_start_dec': params_db.trailing_pct_secondary_decimal / 10,
    'peak_trail_minus_int': 0,
    'peak_trail_minus_dec': 0.5,
    'rsi_profit_threshold_int': 1,   # Example value
    'rsi_profit_threshold_dec': 0.0  # Example value
}

# --- 3. Load Price Data (Replace this with your own data loading logic) ---
# Example: df = pd.read_csv('data/btcusd_sample.csv')
df = pd.DataFrame()  # Replace with actual historical OHLCV data

# --- 4. Run Your Backtest Logic (simplified version) ---
def run_backtest_and_log(df, params):
    # ... (insert your full backtest logic from backtest_loop_skeleton.py here) ...
    # For this example, let's assume you produce a list of trades:
    trades = [
        {
            'symbol': SYMBOL,
            'side': 'BUY',
            'qty': 1.0,
            'price': 45000.0,
            'pnl': 2.5,
            'meta': {'entry_idx': 100, 'exit_idx': 120}
        },
        # Add more trades as needed
    ]
    # --- 5. Save Each Trade to Database ---
    for t in trades:
        trade_record = Trade(
            symbol=t['symbol'],
            side=t['side'],
            qty=t['qty'],
            price=t['price'],
            pnl=t['pnl'],
            meta=t['meta']
        )
        session.add(trade_record)
    session.commit()
    print(f"Logged {len(trades)} trades to the database.")

# Run it
run_backtest_and_log(df, params)
session.close()