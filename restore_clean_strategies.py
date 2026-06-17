"""
Run this after any bulk strategy re-enable to restore the clean 12-strategy crypto set.
BTC=6, ETH=2, SOL=4, no LINK, no 1m/2h, no pl_pct < 0.5
"""
from db import get_db_connection
conn, cur = get_db_connection()

cur.execute('UPDATE strategy_params sp JOIN broker_products bp ON sp.broker_product_id=bp.id SET sp.active=0 WHERE bp.local_ticker="LINK/USD"')
print(f'LINK deactivated: {cur.rowcount}')

cur.execute('UPDATE strategy_params SET active=0 WHERE candle_time IN ("1m","2h")')
print(f'Invalid timeframes deactivated: {cur.rowcount}')

cur.execute('''UPDATE strategy_params sp JOIN broker_products bp ON sp.broker_product_id=bp.id JOIN brokers b ON bp.broker_id=b.id SET sp.active=0 WHERE b.name="Gemini" AND sp.pl_pct < 0.5 AND sp.pl_pct > 0''')
print(f'Weak strategies deactivated: {cur.rowcount}')

cur.execute('''SELECT bp.local_ticker, COUNT(*) as cnt FROM strategy_params sp JOIN broker_products bp ON sp.broker_product_id=bp.id JOIN brokers b ON bp.broker_id=b.id WHERE b.name="Gemini" AND sp.active=1 GROUP BY bp.local_ticker''')
rows = cur.fetchall()
[print(r) for r in rows]
total = sum(r['cnt'] for r in rows)
print(f'TOTAL ACTIVE GEMINI: {total} (should be 12)')
conn.close()
