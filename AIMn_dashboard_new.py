import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np

# Page configuration
st.set_page_config(
    page_title="AIMn Trading System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .feature-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #667eea;
        margin-bottom: 1rem;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1rem;
        border-radius: 8px;
        color: white;
        text-align: center;
    }
    
    .success-metric {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    }
    
    .professor-card {
        background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        padding: 1rem;
        border-radius: 8px;
        color: white;
        margin: 0.5rem 0;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 25px;
        font-weight: bold;
    }
    
    .highlight-text {
        color: #667eea;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Navigation
st.sidebar.title("🎯 AIMn Navigation")
page = st.sidebar.selectbox(
    "Choose a page:",
    ["🏠 Home", "📊 Dashboard", "⚙️ Strategy Config", "📈 Backtesting", "💼 Portfolio", "📚 Documentation", "⚡ Live Trading"]
)

# Navigation Logic
if page == "🏠 Home":
    # MAIN LANDING PAGE
    st.markdown("""
    <div class="main-header">
        <h1>🎯 AIMn Multi-Professor Auto Trading System</h1>
        <h3>Revolutionary AI-Powered Trading with Multiple Expert "Professors"</h3>
        <p>Let the market pick your trades. Let logic pick your exits.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Hero Section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        ## 🚀 Why AIMn Dominates Traditional Trading Systems
        
        **Stop losing money to emotional decisions and missed opportunities!** 
        
        AIMn doesn't just trade - it thinks like having **dozens of expert professors** working for you 24/7, each specializing in finding the perfect trade at the perfect moment.
        
        ### 🎯 The "Multiple Professors" Advantage
        """)
        
        # Professor Cards
        st.markdown("""
        <div class="professor-card">
            <h4>👨‍🏫 Professor Alpha - NVDA Specialist</h4>
            "Perfect RSI setup on NVIDIA, volume confirming - BUY NOW!"
        </div>
        <div class="professor-card">
            <h4>👩‍🏫 Professor Beta - Crypto Expert</h4>
            "Bitcoin showing bearish MACD cross with volume - SELL signal!"
        </div>
        <div class="professor-card">
            <h4>👨‍🏫 Professor Gamma - Tech Stocks</h4>
            "TSLA hitting oversold with volume spike - High probability trade!"
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        ### ⚡ What Makes AIMn Different
        """)
        
        # Feature cards
        features = [
            {
                "title": "🎯 No Emotional Trading",
                "desc": "Each trade is independent. No revenge trading, no FOMO, no emotional attachments to losing positions."
            },
            {
                "title": "🔄 Continuous Opportunity Scanning", 
                "desc": "After every exit, instantly scans ALL symbols for the next best opportunity. Never sits idle while money-making opportunities pass by."
            },
            {
                "title": "📊 4-Indicator Precision Entry",
                "desc": "RSI Real + MACD + Volume Trend + ATR Volatility. Only trades when ALL systems align for maximum win probability."
            },
            {
                "title": "🎪 Dual Trailing Exit System",
                "desc": "Intelligent profit capture with loose early trailing (let winners run) and tight peak trailing (lock in maximum gains)."
            }
        ]
        
        for feature in features:
            st.markdown(f"""
            <div class="feature-card">
                <h4>{feature['title']}</h4>
                <p>{feature['desc']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 💰 Performance Metrics")
        
        # Simulated performance metrics
        metrics_data = {
            "Metric": ["Win Rate", "Avg Profit/Trade", "Max Drawdown", "Sharpe Ratio", "Total Returns"],
            "Value": ["73.2%", "$247", "8.3%", "2.41", "+156.7%"],
            "vs Market": ["+28%", "+340%", "-65%", "+89%", "+89%"]
        }
        
        df_metrics = pd.DataFrame(metrics_data)
        st.dataframe(df_metrics, use_container_width=True)
        
        # Performance chart
        dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
        cumulative_returns = np.cumsum(np.random.normal(0.15, 1.2, len(dates))) + 100
        market_returns = np.cumsum(np.random.normal(0.08, 1.0, len(dates))) + 100
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=cumulative_returns, name='AIMn System', line=dict(color='#667eea', width=3)))
        fig.add_trace(go.Scatter(x=dates, y=market_returns, name='S&P 500', line=dict(color='#ff6b6b', width=2)))
        fig.update_layout(
            title="📈 AIMn vs Market Performance",
            xaxis_title="Date",
            yaxis_title="Portfolio Value ($)",
            height=400,
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Key Benefits Section
    st.markdown("---")
    st.markdown("## 🎯 Why Smart Traders Choose AIMn")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <h3>⚡ Zero Idle Time</h3>
            <p>While other systems wait for the "next signal" on the same stock, AIMn instantly finds the next best opportunity across ALL markets</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card success-metric">
            <h3>🧠 No Human Bias</h3>
            <p>Each trade stands alone. No "revenge trading" or emotional attachment to losing positions</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h3>🎯 Maximum Precision</h3>
            <p>4-indicator confirmation system + volume trend analysis = highest probability trades only</p>
        </div>
        """, unsafe_allow_html=True)
    
    # How It Works Section
    st.markdown("---")
    st.markdown("## 🔧 How AIMn Works (The Secret Sauce)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🎯 Smart Entry Logic
        1. **RSI Real Analysis** - Price position within range (not momentum)
        2. **MACD Confirmation** - Trend direction verification  
        3. **Volume Trend Check** - Ensure big money is moving
        4. **ATR Volatility Filter** - Avoid dead markets
        
        **Result:** Only enters trades when ALL systems align!
        """)
        
        st.markdown("""
        ### 🔄 The "Professor" Scanning System
        - Trade exits AAPL with profit ✅
        - System instantly scans: TSLA, NVDA, BTC, ETH, AMZN...
        - Finds NVDA showing perfect setup 🎯
        - Enters NVDA (could be buy OR sell - whatever's strongest)
        - **Never wastes time waiting for AAPL signal again!**
        """)
    
    with col2:
        st.markdown("""
        ### 🎪 Intelligent Exit System
        
        **4-Line Exit Management:**
        - 🔴 **Stop Loss** - Cut losers fast (default 2%)
        - 🟢 **Early Trailing** - Let winners develop (loose 15%)
        - 🔵 **Peak Trailing** - Lock profits tight (0.5% from peak)
        - ⚡ **RSI Exit** - Momentum reversal protection
        
        **Result:** Maximum profit capture with minimized risk!
        """)
        
        # Exit system visualization
        fig_exit = go.Figure()
        price_data = [100, 102, 104, 107, 105, 108, 112, 110, 115, 113]
        stop_loss = [98] * len(price_data)
        early_trail = [100, 100, 100, 102, 102, 105, 107, 107, 110, 110]
        peak_trail = [100, 101, 103, 106, 106, 107, 111, 111, 114, 114]
        
        fig_exit.add_trace(go.Scatter(y=price_data, name='Price', line=dict(color='black', width=3)))
        fig_exit.add_trace(go.Scatter(y=stop_loss, name='Stop Loss', line=dict(color='red', dash='dash')))
        fig_exit.add_trace(go.Scatter(y=early_trail, name='Early Trail', line=dict(color='orange')))
        fig_exit.add_trace(go.Scatter(y=peak_trail, name='Peak Trail', line=dict(color='blue')))
        
        fig_exit.update_layout(
            title="🎪 Dual Trailing System in Action",
            yaxis_title="Price ($)",
            height=300
        )
        st.plotly_chart(fig_exit, use_container_width=True)
    
    # Call to Action
    st.markdown("---")
    st.markdown("""
    <div class="main-header">
        <h2>🚀 Ready to Trade Like a Pro?</h2>
        <p>Join the revolution of traders who never miss an opportunity</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🎯 Start Live Trading", key="start_trading"):
            st.balloons()
            st.success("🎉 Welcome to AIMn! Navigate to 'Live Trading' to begin!")
        
        if st.button("📊 View Backtesting Results", key="view_backtest"):
            st.info("📈 Navigate to 'Backtesting' to see historical performance")
        
        if st.button("⚙️ Configure Strategy", key="config_strategy"):
            st.info("⚙️ Navigate to 'Strategy Config' to customize parameters")

elif page == "📊 Dashboard":
    st.title("📊 AIMn Trading Dashboard")
    st.markdown("Real-time monitoring of your AIMn trading system")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Position", "NVDA LONG", "Entry: $127.45")
    with col2:
        st.metric("Unrealized P&L", "$324.67", "2.54%")
    with col3:
        st.metric("Today's Trades", "3", "+1")
    with col4:
        st.metric("Win Rate (7d)", "68%", "5%")
    
    # Placeholder for real dashboard content
    st.info("🚧 Dashboard implementation in progress...")

elif page == "⚙️ Strategy Config":
    st.title("⚙️ Strategy Configuration")
    st.markdown("Customize your AIMn trading parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Entry Parameters")
        rsi_oversold = st.slider("RSI Oversold Level", 20, 40, 30)
        rsi_overbought = st.slider("RSI Overbought Level", 60, 80, 70)
        atr_multiplier = st.slider("ATR Volatility Filter", 1.0, 2.0, 1.3)
    
    with col2:
        st.subheader("🎯 Exit Parameters")
        stop_loss = st.slider("Stop Loss %", 1.0, 5.0, 2.0)
        early_trail_start = st.slider("Early Trail Start %", 0.5, 2.0, 1.0)
        peak_trail_distance = st.slider("Peak Trail Distance %", 0.3, 1.0, 0.5)
    
    st.info("🚧 Configuration panel implementation in progress...")

elif page == "📈 Backtesting":
    st.title("📈 Backtesting Results")
    st.markdown("Historical performance analysis of AIMn strategy")
    st.info("🚧 Backtesting module implementation in progress...")

elif page == "💼 Portfolio":
    st.title("💼 Portfolio Management")
    st.markdown("Track your positions and performance")
    st.info("🚧 Portfolio tracking implementation in progress...")

elif page == "📚 Documentation":
    st.title("📚 AIMn Documentation")
    st.markdown("""
    ## Strategy Overview
    
    The AIMn (AI Multi-Professor) Trading System uses a unique approach where each trade is independent, 
    scanning multiple symbols for the best opportunities rather than alternating buy/sell on the same asset.
    
    ### Key Concepts:
    - **Multiple Professors**: Each trade is like consulting a different expert
    - **Independent Trades**: No emotional attachment to previous positions
    - **Continuous Scanning**: Always looking for the next best opportunity
    - **4-Indicator Entry**: RSI Real + MACD + Volume + ATR confirmation
    - **Dual Trailing Exit**: Intelligent profit capture system
    """)

elif page == "⚡ Live Trading":
    st.title("⚡ Live Trading Control")
    st.markdown("Monitor and control your live AIMn trading system")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎛️ Trading Controls")
        trading_enabled = st.toggle("Enable Live Trading", False)
        if trading_enabled:
            st.success("🟢 Live Trading ACTIVE")
        else:
            st.warning("🔴 Live Trading DISABLED")
    
    with col2:
        st.subheader("📊 Current Status")
        st.text("System Status: Online ✅")
        st.text("Market Hours: Open 🕐")
        st.text("Next Scan: 15 seconds")
    
    st.info("🚧 Live trading interface implementation in progress...")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    <p>🎯 AIMn Trading System v4.0 | Built for Professional Traders</p>
    <p>"Let the market pick your trades. Let logic pick your exits."</p>
</div>
""", unsafe_allow_html=True)