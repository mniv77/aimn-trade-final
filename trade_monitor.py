import os
import time
import pandas as pd
import mysql.connector
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
import sys

# --- CONFIGURATION ---
home_directory = os.path.expanduser('~') 
project_folder = os.path.join(home_directory, 'aimn-trade-final')
load_dotenv(os.path.join(project_folder, '.env'))

DB_CONFIG = {
    'user': 'MeirNiv',
    'password': os.getenv('DB_PASSWORD'),
    'host': 'MeirNiv.mysql.pythonanywhere-services.com', 
    'database': 'MeirNiv$default' 
}

# --- DATABASE TOOL ---
def get_broker_keys(broker_name="Alpaca"):
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
        print(f"❌ DB Error: {e}")
        return None

# --- RSI REAL TOOLS ---
def get_rsi_real_safe(df, period=14):
    try:
        if len(df) < period: return 50.0
        recent = df['close'].tail(period)
        p_max, p_min = recent.max(), recent.min()
        current = df['close'].iloc[-1]
        price_range = p_max - p_min
        if price_range == 0: return 50.0
        return float(((current - p_min) / price_range) * 100)
    except: return 50.0

def check_entry_signal(current_rsi, target=10, buffer=2):
    return abs(current_rsi - target) <= buffer

# --- THE ENGINE ---
def start_monitoring_loop(api):
    print("🚀 RSI Real Monitor is now LIVE...")
    TARGET, BUFFER = 10, 2
    
    while True:
        try:
            symbol = "BTC/USD"
            bars = api.get_bars(symbol, "1Min", limit=100)
            df = bars.df
            
            current_val = get_rsi_real_safe(df, period=14)
            
            if check_entry_signal(current_val, TARGET, BUFFER):
                print(f"✅ SIGNAL: {symbol} at {current_val:.2f}% - BUY ZONE")
            else:
                print(f"📊 SCAN: {symbol} at {current_val:.2f}% (Wait...)")
                
            time.sleep(60)
        except Exception as e:
            print(f"⚠️ Market Error: {e}")
            time.sleep(10)

def get_watchlist():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    
    # We fetch from broker_products and join brokers to get the API keys
    query = """
        SELECT bp.id, bp.local_ticker, b.api_key, b.api_secret, b.name as broker_name
        FROM broker_products bp
        JOIN brokers b ON bp.broker_id = b.id
        WHERE b.api_key IS NOT NULL
    """
    cursor.execute(query)
    watchlist = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return watchlist




# --- STARTUP LOGIC ---
if __name__ == "__main__":
    keys = get_broker_keys("Alpaca")
    
    if keys and keys['api_key'] and keys['api_secret']:
        print(f"✅ Keys Loaded (ID: {keys['api_key'][:5]}...)")
        api = tradeapi.REST(
            key_id=keys['api_key'], 
            secret_key=keys['api_secret'], 
            base_url="https://paper-api.alpaca.markets", 
            api_version='v2'
        )
        start_monitoring_loop(api)
    else:
        print("❌ ERROR: Database keys are empty. Update your 'brokers' table first!")
        sys.exit()