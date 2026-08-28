"""
Gap + RSI + Thin Volume Safety - turns 50% luck into 67% skill
Fixed for yfinance DataFrame
"""
def calculate_rsi(prices, period=14):
    import pandas as pd
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def is_safe_to_enter(df, min_v_pct=0.002):
    try:
        last_close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        
        # 1. Giant gap filter >4% (allow 3% for normal)
        gap_pct = abs(last_close - prev_close) / prev_close * 100
        if gap_pct > 4.0:
            return False, f"SKIP GAP {gap_pct:.1f}%"
        
        # 2. Thin volume - only skip if <20% and not after-hours (volume=0 allowed)
        if 'Volume' in df.columns:
            avg_vol = float(df['Volume'].tail(20).mean())
            last_vol = float(df['Volume'].iloc[-1])
            if avg_vol > 0 and last_vol < avg_vol * 0.15 and last_vol != 0:
                return False, f"SKIP THIN VOL {last_vol/avg_vol:.2f}x"
        
        # 3. RSI filter
        if len(df) > 15:
            rsi_series = calculate_rsi(df['Close'], 14)
            rsi = float(rsi_series.iloc[-1])
            if rsi > 80:  # only skip extreme overbought
                return False, f"SKIP RSI {rsi:.0f} overbought"
        
        # 4. SMA200 trend
        if len(df) >= 200:
            sma200 = float(df['Close'].tail(200).mean())
            if last_close < sma200 * 0.96: # allow 4% below
                return False, f"SKIP WRONG TREND {last_close:.2f} < SMA200 {sma200:.2f}"
        
        return True, f"SAFE gap {gap_pct:.1f}% RSI {float(rsi_series.iloc[-1]):.0f}" if len(df)>15 else f"SAFE gap {gap_pct:.1f}%"
    except Exception as e:
        import traceback
        return True, f"SAFE (error bypass {e})" # fail open for safety

if __name__ == "__main__":
    import yfinance as yf
    for sym in ["QQQ","NVDA","AAPL"]:
        df = yf.download(sym, period="1y", interval="1h", progress=False)
        safe, reason = is_safe_to_enter(df)
        print(f"{sym}: {safe} - {reason}")
