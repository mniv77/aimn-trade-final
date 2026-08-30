import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import yfinance as yf
import pandas as pd
from db import get_db_connection
from datetime import datetime
import time

stocks = ["SPY","QQQ","NVDA","AAPL","TSLA","MSFT","AMZN","GOOGL"]
conn, cur = get_db_connection()
if isinstance(conn, tuple):
    conn, cur = conn[0], conn[1]

for sym in stocks:
    try:
        print(f"\n=== Downloading {sym} 60d 30m ===")
        df = yf.download(sym, period="155d", interval="30m", auto_adjust=False, progress=False)
        if len(df)==0:
            print(f"{sym} no data")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.reset_index(inplace=True)
        count=0
        for _, row in df.iterrows():
            dt = row['Datetime'] if 'Datetime' in df.columns else row['Date']
            try:
                ts = pd.to_datetime(dt).to_pydatetime()
            except:
                continue
            c = float(row['Close']) if str(row['Close'])!='nan' else 0
            if c==0: continue
            cur.execute("""
                INSERT INTO candles (symbol, timeframe, timestamp, open, high, low, close, volume)
                VALUES (%s,'30m',%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE close=VALUES(close)
            """, (sym, ts, float(row['Open']), float(row['High']), float(row['Low']), c, float(row['Volume'])))
            count+=1
        conn.commit()
        print(f"✅ {sym} saved {count} bars")
        time.sleep(1)
    except Exception as e:
        print(f"❌ {sym} failed {e}")

cur.execute("SELECT symbol, timeframe, COUNT(*) as cnt FROM candles WHERE symbol IN ('SPY','QQQ','NVDA','AAPL','TSLA') GROUP BY symbol, timeframe")
print("\n=== VERIFY ===")
for r in cur.fetchall():
    print(r)
