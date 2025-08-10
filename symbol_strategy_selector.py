<<<<<<< HEAD
# filename: symbol_strategy_selector.py

import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime

st.set_page_config(page_title="AIMn Strategy Control", layout="wide")
st.title("🧠 AIMn Multi-Symbol Strategy Selector")

# ---------------------------------------------
# SECTION 1: MySQL Connection Setup (Update with actual credentials)
# ---------------------------------------------
@st.cache_resource
def get_connection():
    return mysql.connector.connect(
        host="localhost",      # or your DB hostname
        user="your_username",
        password="your_password",
        database="aimn_trading"
    )

# ---------------------------------------------
# SECTION 2: Symbol Controls
# ---------------------------------------------
symbols = ["BTC/USD", "ETH/USD", "LTC/USD", "BCH/USD", "LINK/USD", "UNI/USD", "AAVE/USD"]

if "symbol_states" not in st.session_state:
    st.session_state.symbol_states = {s: False for s in symbols}

col1, col2 = st.columns(2)
if col1.button("ALL"):
    for s in symbols:
        st.session_state.symbol_states[s] = True
if col2.button("CLEAR"):
    for s in symbols:
        st.session_state.symbol_states[s] = False

st.markdown("### Select Symbols")
symbol_cols = st.columns(4)
for i, sym in enumerate(symbols):
    with symbol_cols[i % 4]:
        st.session_state.symbol_states[sym] = st.checkbox(
            sym, value=st.session_state.symbol_states[sym], key=sym
        )

selected_symbols = [s for s in symbols if st.session_state.symbol_states[s]]

# ---------------------------------------------
# SECTION 3: Strategy Parameters (from TradingView strategy)
# ---------------------------------------------
st.markdown("### Strategy Parameters (Shared Across Selected Symbols)")

rsi_window = st.slider("RSI Real Window", 10, 200, 100)
oversold_whole = st.slider("Oversold Level (whole)", 1, 99, 30)
oversold_decimal = st.slider("Oversold Level (decimal)", 0.0, 0.9, 0.0, 0.1)
oversold_level = oversold_whole + oversold_decimal

rsi_exit_whole = st.slider("RSI Exit Level Buy (whole)", 1, 99, 70)
rsi_exit_decimal = st.slider("RSI Exit Level Buy (decimal)", 0.0, 0.9, 0.0, 0.1)
rsi_exit_level = rsi_exit_whole + rsi_exit_decimal

macd_fast = st.slider("MACD Fast Length", 5, 20, 12)
macd_slow = st.slider("MACD Slow Length", 10, 50, 26)
macd_signal = st.slider("MACD Signal Smoothing", 5, 20, 9)

volume_ma = st.slider("Volume MA Length", 5, 50, 20)
volume_thresh = st.slider("Volume Threshold Multiplier", 1.0, 2.0, 1.2, 0.1)
use_volume = st.checkbox("Use Volume Confirmation", value=True)

stoploss_whole = st.slider("Stop Loss % (whole)", 0, 5, 2)
stoploss_decimal = st.slider("Stop Loss % (decimal)", 0.0, 0.9, 0.0, 0.1)
stoploss_percent = (stoploss_whole + stoploss_decimal) / 100

# ---------------------------------------------
# SECTION 4: Display Settings Summary
# ---------------------------------------------
if selected_symbols:
    st.success(f"You have selected: {', '.join(selected_symbols)}")
    st.markdown("#### Strategy settings to apply:")
    st.json({
        "RSI Window": rsi_window,
        "Oversold Level": oversold_level,
        "RSI Exit Level": rsi_exit_level,
        "MACD": {"Fast": macd_fast, "Slow": macd_slow, "Signal": macd_signal},
        "Volume MA": volume_ma,
        "Volume Threshold": volume_thresh,
        "Use Volume Confirmation": use_volume,
        "Stop Loss %": stoploss_percent
    })
else:
    st.warning("No symbols selected. Use the checkboxes or ALL button.")

# ---------------------------------------------
# SECTION 5: Show Live Trade Log
# ---------------------------------------------
st.markdown("### 📜 Recent Trade Log")
try:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT symbol, direction, entry_price, exit_price, pnl_percent, reason, timestamp
        FROM trades
        ORDER BY timestamp DESC
        LIMIT 25
    """)
    trades = cursor.fetchall()
    if trades:
        df = pd.DataFrame(trades)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No trades logged yet.")
except Exception as e:
    st.error(f"Failed to load trade log: {e}")
=======
# symbol_strategy_selector.py

def get_strategy_for_symbol(symbol):
    def strategy(data):
        return None
    return strategy
>>>>>>> 0c0df91 (Initial push)
