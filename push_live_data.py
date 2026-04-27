# push_live_data.py - AiMN V3.1 Global Multi-Timeframe Data Pump
import mysql.connector
import requests
import time
import db_config as config

def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True
    )

def get_broker_keys():
    """Retrieves API keys for all brokers from the database."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, api_key, api_secret FROM brokers")
    keys = {row['name'].upper(): row for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return keys

def fetch_crypto_price(symbol):
    """Fetches real-time crypto price from Gemini Public API."""
    try:
        clean_ticker = symbol.replace("/", "").lower()
        url = f"https://api.gemini.com/v1/pubticker/{clean_ticker}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return float(response.json()['last'])
    except Exception:
        pass
    return None

def fetch_alpaca_price(symbol, keys):
    """Fetches real-time stock price from Alpaca Market Data API."""
    if not keys or not keys.get('api_key'):
        return None
    try:
        # Alpaca V2 Data Endpoint
        url = f"https://data.alpaca.markets/v2/stocks/{symbol.upper()}/quotes/latest"
        headers = {
            "APCA-API-KEY-ID": keys['api_key'],
            "APCA-API-SECRET-KEY": keys['api_secret']
        }
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            # 'ap' is the ask price, 'bp' is the bid price. We use the midpoint or last trade if available.
            # Using the last quote price as a proxy for 'last_price'
            data = response.json()
            return float(data['quote']['ap'])
    except Exception:
        pass
    return None

def run_pump():
    print("--- AiMN V3.1 MULTI-GATEWAY DATA PUMP STARTING ---")
    print("Logic: Routing Crypto to Gemini | Stocks to Alpaca")
    
    while True:
        conn = None
        try:
            # 1. Refresh keys and active strategies every loop
            broker_keys = get_broker_keys()
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT DISTINCT bp.id, bp.local_ticker, b.name as broker_name
                FROM broker_products bp
                JOIN strategy_params sp ON bp.id = sp.broker_product_id
                JOIN brokers b ON bp.broker_id = b.id
                WHERE sp.active = 1
            """)
            active_assets = cursor.fetchall()

            if not active_assets:
                print(f"[{time.strftime('%H:%M:%S')}] No active strategies. Waiting...")

            for asset in active_assets:
                ticker = asset['local_ticker']
                broker_name = asset['broker_name'].upper()
                price = None

                # Route based on asset format or broker link
                if "/" in ticker:
                    price = fetch_crypto_price(ticker)
                elif "ALPACA" in broker_name:
                    price = fetch_alpaca_price(ticker, broker_keys.get('ALPACA'))
                
                # Fallback to Yahoo if Alpaca/Gemini fail or aren't configured
                if not price:
                    try:
                        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                        if res.status_code == 200:
                            price = float(res.json()['chart']['result'][0]['meta']['regularMarketPrice'])
                    except:
                        pass

                if price and price > 0:
                    # Sync price to all timeframes (1m, 1h, 2h)
                    cursor.execute("""
                        UPDATE strategy_params 
                        SET last_price = %s 
                        WHERE broker_product_id = %s
                    """, (price, asset['id']))
                    print(f"[{time.strftime('%H:%M:%S')}] Pushed: {ticker} @ {price} via {broker_name}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Warning: {ticker} data unavailable.")
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"PUMP ERROR: {e}")
            if conn: conn.close()
        
        time.sleep(3)

if __name__ == "__main__":
    run_pump()