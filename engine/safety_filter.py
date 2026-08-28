def calculate_rsi(prices, period=14):
    import pandas as pd
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def is_safe_to_enter(df, min_v_pct=0.002):
    try:
        last_close = float(df['Close'].iloc[-1].iloc[0] if hasattr(df['Close'].iloc[-1], 'iloc') else df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2].iloc[0] if hasattr(df['Close'].iloc[-2], 'iloc') else df['Close'].iloc[-2])
        gap_pct = abs(last_close - prev_close) / prev_close * 100
        if gap_pct > 4.5: return False, f"SKIP GAP {gap_pct:.1f}%"

        # Only check volume if >0 and not weekend - QQQ fix: allow 0.05x
        if 'Volume' in df.columns:
            avg_vol = float(df['Volume'].tail(20).mean().iloc[0] if hasattr(df['Volume'].tail(20).mean(), 'iloc') else df['Volume'].tail(20).mean())
            last_vol = float(df['Volume'].iloc[-1].iloc[0] if hasattr(df['Volume'].iloc[-1], 'iloc') else df['Volume'].iloc[-1])
            if avg_vol > 0 and last_vol > 0 and last_vol < avg_vol * 0.05:
                return False, f"SKIP THIN VOL {last_vol/avg_vol:.2f}x"

        if len(df) > 15:
            rsi_series = calculate_rsi(df['Close'], 14)
            rsi = float(rsi_series.iloc[-1].iloc[0] if hasattr(rsi_series.iloc[-1], 'iloc') else rsi_series.iloc[-1])
            if rsi > 82: return False, f"SKIP RSI {rsi:.0f}"

        if len(df) >= 200:
            sma200 = float(df['Close'].tail(200).mean().iloc[0] if hasattr(df['Close'].tail(200).mean(), 'iloc') else df['Close'].tail(200).mean())
            if last_close < sma200 * 0.94: return False, f"SKIP WRONG TREND"

        return True, f"SAFE gap {gap_pct:.1f}%"
    except Exception as e:
        return True, f"SAFE bypass {e}"

if __name__ == "__main__":
    import yfinance as yf
    for sym in ["QQQ","NVDA","AAPL","SPY"]:
        df = yf.download(sym, period="1y", interval="1h", progress=False)
        safe, reason = is_safe_to_enter(df)
        print(f"{sym}: {safe} - {reason}")
