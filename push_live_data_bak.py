import mysql.connector
import time
import random
import sys

# Load credentials
sys.path.append('/home/MeirNiv/aimn-trade-final')
try:
    from db_config import DB_PASSWORD
except ImportError:
    print("Error: db_config.py missing.")
    sys.exit(1)

db_config = {
    'user': 'MeirNiv',
    'password': DB_PASSWORD,
    'host': 'MeirNiv.mysql.pythonanywhere-services.com',
    'database': 'MeirNiv$default'
}

def simulate_live_updates():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        print("--- V31 DIAGNOSTIC DATA PUMP ---")

        while True:
            # 1. Fetch all symbols to see if the script actually finds them
            cursor.execute("""
                SELECT bp.local_ticker, sp.last_price, sp.id as strategy_id
                FROM strategy_params sp
                JOIN broker_products bp ON sp.broker_product_id = bp.id
                WHERE sp.active = 1
            """)
            active_symbols = cursor.fetchall()

            if not active_symbols:
                print(f"[{time.strftime('%H:%M:%S')}] WARNING: Zero active symbols found in database!")
                time.sleep(10)
                continue

            found_list = [s['local_ticker'] for s in active_symbols]
            print(f"[{time.strftime('%H:%M:%S')}] Found {len(found_list)} symbols: {', '.join(found_list)}")

            for s in active_symbols:
                ticker = s['local_ticker']
                current_price = float(s['last_price']) if s['last_price'] and float(s['last_price']) > 0 else 100.0

                rsi = round(random.uniform(25.0, 75.0), 2)
                macd = round(random.uniform(-0.0050, 0.0050), 4)
                new_price = round(current_price + (current_price * random.uniform(-0.001, 0.001)), 2)

                # Direct Update by Strategy ID for maximum reliability
                update_sql = "UPDATE strategy_params SET rsi_real = %s, macd = %s, last_price = %s WHERE id = %s"
                cursor.execute(update_sql, (rsi, macd, new_price, s['strategy_id']))

            conn.commit()
            time.sleep(3)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    simulate_live_updates()
