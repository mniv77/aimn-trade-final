import pandas as pd

import alpaca_trade_api as tradeapi
import time
import os
import mysql.connector
from dotenv import load_dotenv

# --- CONFIGURATION FROM YOUR ENV ---
home_directory = os.path.expanduser('~')
project_folder = os.path.join(home_directory, 'aimn-trade-final')
load_dotenv(os.path.join(project_folder, '.env'))

DB_CONFIG = {
    'user': 'MeirNiv',
    'password': os.getenv('DB_PASSWORD'),
    'host': 'MeirNiv.mysql.pythonanywhere-services.com',
    'database': 'MeirNiv$default'
}

def get_broker_keys(broker_name="Alpaca"):
    """
    Connects to your PythonAnywhere MySQL and pulls Alpaca keys.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = "SELECT api_key, api_secret FROM brokers WHERE name = %s"
        cursor.execute(query, (broker_name,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print(f"❌ DB Error on PythonAnywhere: {e}")
        return None

# --- TEST THE CONNECTION ---
keys = get_broker_keys("Alpaca")

if keys and keys['api_key'] and keys['api_secret']:
    print(f"✅ Keys found in DB. Key ID starts with: {keys['api_key'][:5]}...")
    api = tradeapi.REST(
        key_id=keys['api_key'],
        secret_key=keys['api_secret'],
        base_url="https://paper-api.alpaca.markets",
        api_version='v2'
    )
else:
    print("❌ ERROR: Keys in database are NULL or Empty!")
    print(f"Database returned: {keys}")
    # We exit so we don't get the Traceback error anymore
    import sys
    sys.exit()


# --- THE MAIN ENGINE ---
def start_monitoring_loop():
    print("🚀 RSI Real Monitor is now active...")

    # Target 10% from the bottom of the 14-period range
    TARGET = 10
    BUFFER = 2

    while True:
        try:
            # 1. FETCH THE DATA (Getting the last 100 minutes of Bitcoin)
            symbol = "BTC/USD"
            bars = api.get_bars(symbol, "1Min", limit=100)
            df = bars.df  # This turns the data into the 'df' your tool needs

            if df.empty:
                print(f"⚠️ No data received for {symbol}. Retrying...")
                time.sleep(10)
                continue

            # 2. CALCULATE RSI REAL
            current_val = get_rsi_real_safe(df, period=14)

            # 3. CHECK THE SIGNAL (Target 10, Buffer 2)
            if check_entry_signal(current_val, target=TARGET, buffer=BUFFER):
                print(f"✅ SIGNAL: {symbol} is at {current_val:.2f}% of its 14-bar range. BUY!")
                # To actually buy, you would add: api.submit_order(...)
            else:
                print(f"📊 SCAN: {symbol} RSI Real is {current_val:.2f}. (Target: {TARGET}%)")

            # 4. WAIT
            time.sleep(60)

        except Exception as e:
            print(f"⚠️ Market Error: {e}")
            time.sleep(10)

# THE FINAL LINE: This starts everything
if __name__ == "__main__":
    start_monitoring_loop()




# --- TOOL 1: THE CALCULATION ---
def get_rsi_real(prices, period=14):
    """
    This looks at the last 14 bars.
    It finds the Max (100) and Min (0) and tells us where we are now.
    """
    recent = prices.tail(period)
    p_max = recent.max()
    p_min = recent.min()
    current = prices.iloc[-1]

    price_range = p_max - p_min
    if price_range == 0:
        return 50.0  # Safety: If price is flat, return middle

    return ((current - p_min) / price_range) * 100

# --- TOOL 2: THE TRIGGER CHECK ---
def check_entry_signal(current_rsi, target=10, buffer=2):
    """
    Checks if our current position is 'stable' near our target.
    If target is 10 and buffer is 2, it returns True for 8% to 12%.
    """
    if abs(current_rsi - target) <= buffer:
        return True
    return False


def get_rsi_real_safe(df, period=14):
    """
    RSI Real: (Current - Min) / (Max - Min) * 100
    Includes safety checks to prevent crashes on the server.
    """
    try:
        # 1. Ensure we have enough data
        if len(df) < period:
            return 50.0  # Return neutral if not enough bars

        # 2. Get the 14-period slice
        recent = df['close'].tail(period)
        p_max = recent.max()
        p_min = recent.min()
        current = df['close'].iloc[-1]

        # 3. Calculate Range
        price_range = p_max - p_min

        # 4. SAFETY: If price is flat, range is 0. Avoid division by zero!
        if price_range == 0:
            return 50.0

        # 5. Final Calculation
        rsi_real = ((current - p_min) / price_range) * 100
        return float(rsi_real)

    except Exception as e:
        print(f"⚠️ Error calculating RSI Real: {e}")
        return 50.0 # Safety fallback