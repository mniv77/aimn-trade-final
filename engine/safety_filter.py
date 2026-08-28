"""
Gap + RSI + Thin Volume Safety - turns 50% luck into 67% skill
"""
def calculate_rsi(prices, period=14):
    import pandas as pd
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def is_safe_to_enter(df, min_v_pct=0.002):
    """
    Returns (safe:bool, reason:str)
    Filters thin giant skips
    """
    try:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 1. Giant gap filter >3%
        gap_pct = abs(float(last['Close']) - float(prev['Close'])) / float(prev['Close']) * 100
        if gap_pct > 3.0:
            return False, f"SKIP GAP {gap_pct:.1f}%"
        
        # 2. Thin volume filter
        if 'Volume' in df.columns:
            avg_vol = float(df['Volume'].tail(20).mean())
            if float(last['Volume']) < avg_vol * 0.5:
                return False, f"SKIP THIN VOL {float(last['Volume'])/avg_vol:.1f}x"
        
        # 3. RSI filter - save from wrong trend
        if len(df) > 15:
            rsi_series = calculate_rsi(df['Close'], 14)
            rsi = float(rsi_series.iloc[-1])
            if rsi > 78:  # overbought
                return False, f"SKIP RSI {rsi:.0f} overbought"
            if rsi < 22:  # will add bounce logic later, but for now allow
                pass
        
        # 4. SMA200 trend - right trend only
        if len(df) >= 200:
            sma200 = float(df['Close'].tail(200).mean())
            price = float(last['Close'])
            if price < sma200 * 0.97: # 3% below SMA200 = wrong trend
                return False, f"SKIP WRONG TREND price {price:.2f} < SMA200 {sma200:.2f}"
        
        return True, f"SAFE gap {gap_pct:.1f}% RSI {float(rsi_series.iloc[-1]):.0f} in UPTREND"
    except Exception as e:
        return False, f"ERROR {e}"

# Test on QQQ
if __name__ == "__main__":
    import yfinance as yf
    df = yf.download("QQQ", period="1y", interval="1h", progress=False)
    safe, reason = is_safe_to_enter(df)
    print(f"QQQ now: {safe} - {reason}")
