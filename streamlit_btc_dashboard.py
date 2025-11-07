<<<<<<< HEAD
# streamlit_btc_dashboard.py
"""
Streamlit dashboard to visualize BTC/USD backtest trades
"""
import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt
from datetime import datetime

st.set_page_config(layout="wide")

st.title("📈 BTC/USD Backtest Dashboard")

TRADES_CSV = "exports/btc_demo_trades.csv"
SNAPSHOT_DIR = "trade_snapshots"

if not os.path.exists(TRADES_CSV):
    st.error("No trades file found. Run backtest first.")
    st.stop()

trades = pd.read_csv(TRADES_CSV)

# Filters
col1, col2 = st.columns([1, 2])
with col1:
    reason_filter = st.multiselect("Exit Reasons", trades['exit_code'].unique(), default=list(trades['exit_code'].unique()))
    sort_by = st.selectbox("Sort By", ["pnl", "pnl_pct", "exit_time"], index=1)
    top_n = st.slider("Show Top Trades", min_value=1, max_value=50, value=20)

# Apply filters
filtered = trades[trades['exit_code'].isin(reason_filter)]
filtered = filtered.sort_values(by=sort_by, ascending=False).head(top_n)

st.dataframe(filtered, use_container_width=True)

# Display snapshots
st.subheader("📸 Trade Snapshots")
cols = st.columns(4)
for i, (_, row) in enumerate(filtered.iterrows()):
    filename = f"{row['symbol'].replace('/', '')}_{row['exit_code']}_{pd.to_datetime(row['entry_time']).strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join(SNAPSHOT_DIR, filename)
    if os.path.exists(path):
        with cols[i % 4]:
            st.image(path, caption=f"{row['symbol']} - {row['exit_code']} | {row['pnl_pct']:.1f}%", use_column_width=True)
    else:
        st.warning(f"Missing snapshot: {filename}")
=======
# streamlit_btc_dashboard.py
"""
Streamlit dashboard to visualize BTC/USD backtest trades
"""
import streamlit as st
import pandas as pd
import os
import matplotlib.pyplot as plt
from datetime import datetime

st.set_page_config(layout="wide")

st.title("📈 BTC/USD Backtest Dashboard")

TRADES_CSV = "exports/btc_demo_trades.csv"
SNAPSHOT_DIR = "trade_snapshots"

if not os.path.exists(TRADES_CSV):
    st.error("No trades file found. Run backtest first.")
    st.stop()

trades = pd.read_csv(TRADES_CSV)

# Filters
col1, col2 = st.columns([1, 2])
with col1:
    reason_filter = st.multiselect("Exit Reasons", trades['exit_code'].unique(), default=list(trades['exit_code'].unique()))
    sort_by = st.selectbox("Sort By", ["pnl", "pnl_pct", "exit_time"], index=1)
    top_n = st.slider("Show Top Trades", min_value=1, max_value=50, value=20)

# Apply filters
filtered = trades[trades['exit_code'].isin(reason_filter)]
filtered = filtered.sort_values(by=sort_by, ascending=False).head(top_n)

st.dataframe(filtered, use_container_width=True)

# Display snapshots
st.subheader("📸 Trade Snapshots")
cols = st.columns(4)
for i, (_, row) in enumerate(filtered.iterrows()):
    filename = f"{row['symbol'].replace('/', '')}_{row['exit_code']}_{pd.to_datetime(row['entry_time']).strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join(SNAPSHOT_DIR, filename)
    if os.path.exists(path):
        with cols[i % 4]:
            st.image(path, caption=f"{row['symbol']} - {row['exit_code']} | {row['pnl_pct']:.1f}%", use_column_width=True)
    else:
        st.warning(f"Missing snapshot: {filename}")
>>>>>>> 0c0df91 (Initial push)
