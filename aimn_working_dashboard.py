"""
Save this as aimn_working_dashboard.py
This version will work with your current log format
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import re
import time

st.set_page_config(page_title="AIMn Trading Monitor", page_icon="🚀", layout="wide")

st.title("🚀 AIMn Trading System Monitor")
st.markdown("**Let the market pick your trades. Let logic pick your exits.**")

def parse_account_status(lines):
    """Extract account information from logs"""
    portfolio_value = None
    buying_power = None
    session_return = None
    
    for line in reversed(lines):  # Start from newest
        if "Portfolio Value:" in line:
            match = re.search(r'\$?([\d,]+\.?\d*)', line)
            if match and not portfolio_value:
                portfolio_value = float(match.group(1).replace(',', ''))
        elif "Buying Power:" in line:
            match = re.search(r'\$?([\d,]+\.?\d*)', line)
            if match and not buying_power:
                buying_power = float(match.group(1).replace(',', ''))
        elif "Session Return:" in line:
            match = re.search(r'([+-]?\d+\.?\d*)%', line)
            if match and not session_return:
                session_return = float(match.group(1))
        
        if portfolio_value and buying_power and session_return:
            break
    
    return portfolio_value, buying_power, session_return

def count_scans(lines):
    """Count scanning activities"""
    scan_count = 0
    for line in lines:
        if "scanning for opportunities" in line.lower():
            scan_count += 1
    return scan_count

def get_latest_activity(lines):
    """Get recent activity messages"""
    activities = []
    for line in lines:
        timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if timestamp_match:
            timestamp = timestamp_match.group(1)
            
            if "No trading opportunities found" in line:
                activities.append({
                    'time': timestamp,
                    'type': 'scan',
                    'message': '🔍 Scanned - No signals met criteria'
                })
            elif "scanning for opportunities" in line:
                activities.append({
                    'time': timestamp,
                    'type': 'scanning',
                    'message': '👀 Scanning all symbols...'
                })
            elif "Trading cycle started" in line:
                activities.append({
                    'time': timestamp,
                    'type': 'cycle',
                    'message': '🔄 New trading cycle started'
                })
    
    return activities

# Get log data
log_file = 'aimn_crypto_trading.log'
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()[-200:]  # Last 200 lines
else:
    lines = []

# Parse data
portfolio_value, buying_power, session_return = parse_account_status(lines)
scan_count = count_scans(lines)
activities = get_latest_activity(lines)

# Load trades
trades = []
if os.path.exists('aimn_trades.json'):
    with open('aimn_trades.json', 'r') as f:
        for line in f:
            try:
                trades.append(json.loads(line))
            except:
                pass

# Sidebar
with st.sidebar:
    st.header("⚙️ System Status")
    
    # Check system status
    if os.path.exists(log_file):
        mod_time = os.path.getmtime(log_file)
        seconds_ago = datetime.now().timestamp() - mod_time
        
        if seconds_ago < 45:  # 30s scan + buffer
            st.success(f"🟢 ACTIVE ({int(seconds_ago)}s ago)")
        elif seconds_ago < 120:
            st.warning(f"🟡 DELAYED ({int(seconds_ago)}s ago)")
        else:
            st.error(f"🔴 STOPPED ({int(seconds_ago/60)}m ago)")
    
    st.info(f"Scan Interval: 30 seconds")
    
    if portfolio_value:
        st.metric("Portfolio", f"${portfolio_value:,.2f}")
    if buying_power:
        st.metric("Buying Power", f"${buying_power:,.2f}")
    
    auto_refresh = st.checkbox("Auto-refresh", value=True)

# Main metrics
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Trades", len(trades))

with col2:
    if len(trades) > 0:
        wins = len([t for t in trades if t.get('pnl', 0) > 0])
        win_rate = (wins / len(trades)) * 100
        st.metric("Win Rate", f"{win_rate:.1f}%")
    else:
        st.metric("Win Rate", "0%")

with col3:
    total_pnl = sum(t.get('pnl', 0) for t in trades)
    st.metric("Total P&L", f"${total_pnl:,.2f}")

with col4:
    st.metric("Scans Today", scan_count)

with col5:
    if session_return is not None:
        st.metric("Session", f"{session_return:+.2f}%", 
                  delta=f"${(portfolio_value or 0) * session_return / 100:.2f}" if portfolio_value else None)
    else:
        st.metric("Session", "0.00%")

# Info box
st.info("""
📊 **System Status**: Your AIMn bot is actively scanning 7 crypto pairs every 30 seconds.
- **BTC/USD**, **ETH/USD**, **LTC/USD**, **BCH/USD**, **LINK/USD**, **UNI/USD**, **AAVE/USD**
- Looking for: RSI < 30 (BUY) or > 70 (SELL) + MACD crossover + Volume confirmation
- Current market conditions may not be showing extreme RSI values needed for signals
""")

# Tabs
tab1, tab2, tab3 = st.tabs(["📈 Activity Feed", "💰 Trade History", "📊 Strategy Info"])

with tab1:
    st.subheader("Recent Activity")
    
    if activities:
        # Show last 20 activities
        for activity in reversed(activities[-20:]):
            if activity['type'] == 'scan':
                st.text(f"{activity['time']} - {activity['message']}")
            elif activity['type'] == 'scanning':
                st.info(f"{activity['time']} - {activity['message']}")
            else:
                st.text(f"{activity['time']} - {activity['message']}")
    
    st.markdown("---")
    st.caption("💡 When opportunities are found, you'll see them here with details like:")
    st.caption("- 💡 Opportunity found: BTC/USD BUY (score: 85.2)")
    st.caption("- 🎯 TRADE EXECUTED: BUY 0.0947 units of BTC/USD @ $117,408.88")

with tab2:
    st.subheader("Trade History")
    
    if trades:
        df = pd.DataFrame(trades)
        st.dataframe(df, use_container_width=True)
        
        # Stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Avg Trade", f"${df['pnl'].mean():.2f}")
        with col2:
            st.metric("Best Trade", f"${df['pnl'].max():.2f}")
        with col3:
            st.metric("Worst Trade", f"${df['pnl'].min():.2f}")
    else:
        st.info("No completed trades yet. Your system is being selective - this is good!")
        st.markdown("""
        **Why no trades yet?**
        - Your strategy requires extreme RSI values (< 30 or > 70)
        - Plus MACD and volume confirmation
        - This selectiveness helps avoid false signals
        """)

with tab3:
    st.subheader("Your Trading Strategy")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Entry Criteria (ALL must be true):**
        1. **RSI Real** 
           - BUY: RSI < 30 (oversold)
           - SELL: RSI > 70 (overbought)
        2. **MACD Crossover**
           - BUY: MACD crosses above signal
           - SELL: MACD crosses below signal
        3. **Volume Confirmation**
           - Above average volume
           - Price/volume agreement
        """)
    
    with col2:
        st.markdown("""
        **Exit Strategy:**
        - **Stop Loss**: 2% loss limit
        - **Early Trail**: Activates at 1% profit, trails 15%
        - **Peak Trail**: Activates at 5% profit, trails 0.5%
        - **RSI Exit**: Optional exit on RSI reversal
        
        **Position Sizing:**
        - 30% of capital per trade
        - ~$111,000 per position
        """)

# Auto refresh
if auto_refresh:
    time.sleep(5)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("**AIMn Trading System** | Triple confirmation strategy for high-probability trades")