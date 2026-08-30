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

        # HOURLY: need smaller gap threshold than daily backtest
        if gap_pct < 0.10: # 0.40 blocks all in quiet market, 0.10 allows movers
            return False, f"SKIP SMALL GAP {gap_pct:.2f}% <0.10%"

        if 'Volume' in df.columns:
            avg_vol = float(df['Volume'].tail(20).mean().iloc[0] if hasattr(df['Volume'].tail(20).mean(), 'iloc') else df['Volume'].tail(20).mean())
            last_vol = float(df['Volume'].iloc[-1].iloc[0] if hasattr(df['Volume'].iloc[-1], 'iloc') else df['Volume'].iloc[-1])
            if avg_vol > 0 and last_vol > 0 and last_vol < avg_vol * 0.80: # 1.0 too strict for live
                return False, f"SKIP WEAK VOL {last_vol/avg_vol:.2f}x <0.80x"

        if len(df) > 15:
            rsi_series = calculate_rsi(df['Close'], 14)
            rsi = float(rsi_series.iloc[-1].iloc[0] if hasattr(rsi_series.iloc[-1], 'iloc') else rsi_series.iloc[-1])
            if rsi > 68: # 62 too strict for hourly, 68 allows runners
                return False, f"SKIP HIGH RSI {rsi:.0f} >68"
            if rsi < 28: # also skip oversold bounce trap
                return False, f"SKIP LOW RSI {rsi:.0f} <28"

        return True, f"SAFE gap {gap_pct:.2f}% vol OK rsi OK"
    except Exception as e:
        return True, f"SAFE bypass {e}"

if __name__ == "__main__":
    import yfinance as yf
    for sym in ["MSFT","AMZN","GOOGL","SPY","QQQ","NVDA","AAPL","TSLA"]:
        df = yf.download(sym, period="1y", interval="1h", progress=False)
        safe, reason = is_safe_to_enter(df)
        print(f"{sym}: {safe} - {reason}")
