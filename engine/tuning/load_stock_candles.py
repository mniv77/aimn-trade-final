import yfinance as yf
from db import get_db_connection
from datetime import datetime, timedelta
import pandas as pd

stocks = ["SPY","QQQ","NVDA","AAPL","TSLA","MSFT","AMZN","GOOGL"]
conn, _ = get_db_connection()
conn = conn if not isinstance(conn, tuple) else conn[0]
cur = conn.cursor()

for sym in stocks:
    print(f"Downloading {sym}...")
    df = yf.download(sym, period="60d", interval="30m", auto_adjust=True)
    df.reset_index(inplace=True)
    for _, row in df.iterrows():
        ts = row['Datetime'].to_pydatetime() if hasattr(row['Datetime'], 'to_pydatetime') else row['Datetime']
        cur.execute("""
            INSERT INTO candles (symbol, timeframe, timestamp, open, high, low, close, volume)
            VALUES (%s,'30m',%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE close=VALUES(close)
        """, (sym, ts, float(row['Open']), float(row['High']), float(row['Low']), float(row['Close']), float(row['Volume'])))
    conn.commit()
    print(f"✅ {sym} {len(df)} bars saved")

# Verify
cur.execute("SELECT symbol, timeframe, COUNT(*) FROM candles WHERE symbol IN ('SPY','AAPL','NVDA') GROUP BY symbol, timeframe")
print(cur.fetchall())