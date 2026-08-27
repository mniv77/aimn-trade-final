from db import get_db_connection

symbol = "ETHUSD"
timeframe = "1h"

print(f"Connecting to database to fetch candles for {symbol} ({timeframe})...")

conn, cursor = get_db_connection()
try:
    cursor.execute("""
        SELECT high, low, close 
        FROM candles 
        WHERE symbol = %s AND timeframe = %s
        ORDER BY timestamp ASC
    """, (symbol, timeframe))
    rows = cursor.fetchall()
finally:
    conn.close()

print(f"Found {len(rows)} rows in the database.")

if rows:
    if isinstance(rows[0], dict):
        highs = [float(r['high']) for r in rows]
        lows = [float(r['low']) for r in rows]
        closes = [float(r['close']) for r in rows]
    else:
        highs = [float(r[0]) for r in rows]
        lows = [float(r[1]) for r in rows]
        closes = [float(r[2]) for r in rows]
        
    print(f"Successfully unpacked! First 3 closes: {closes[:3]}")
else:
    print("❌ No candles found for ETHUSD with timeframe 1h. Check if your table has data for this symbol!")
