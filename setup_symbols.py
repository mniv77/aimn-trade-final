import mysql.connector
import requests
import config

# --- CONFIGURATION ---
GEMINI_ID = 1  # From your table
ALPACA_ID = 2  # From your table

# --- DATA LISTS ---
# Top 30 Stocks for Alpaca (Manual list because there are too many to fetch all)
ALPACA_STOCKS = [
    ("Apple", "AAPL"), ("Tesla", "TSLA"), ("Nvidia", "NVDA"), ("Microsoft", "MSFT"),
    ("Amazon", "AMZN"), ("Google", "GOOGL"), ("Meta", "META"), ("Netflix", "NFLX"),
    ("AMD", "AMD"), ("Intel", "INTC"), ("Coinbase", "COIN"), ("MicroStrategy", "MSTR"),
    ("SPY ETF", "SPY"), ("QQQ ETF", "QQQ"), ("IWM ETF", "IWM"), ("Disney", "DIS"),
    ("Ford", "F"), ("GM", "GM"), ("Uber", "UBER"), ("Palantir", "PLTR"),
    ("Gamestop", "GME"), ("AMC", "AMC"), ("Robinhood", "HOOD"), ("PayPal", "PYPL"),
    ("Square", "SQ"), ("Shopify", "SHOP"), ("Spotify", "SPOT"), ("Zoom", "ZM"),
    ("Boeing", "BA"), ("Coca-Cola", "KO")
]

def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )

def setup_gemini(cursor):
    print("🌐 Fetching all symbols from Gemini API...")
    try:
        # Fetch live list from Gemini
        response = requests.get("https://api.gemini.com/v1/symbols")
        symbols = response.json() # Returns list like ['btcusd', 'ethusd'...]
        
        count = 0
        for ticker in symbols:
            # Clean up ticker (e.g., 'btcusd')
            asset_name = ticker.upper() # Use ticker as name for now
            
            # 1. Add to Global Symbols (Ignore if exists)
            cursor.execute("SELECT id FROM global_symbols WHERE name = %s", (asset_name,))
            res = cursor.fetchone()
            if res:
                s_id = res[0]
            else:
                cursor.execute("INSERT INTO global_symbols (name, asset_class) VALUES (%s, 'Crypto')", (asset_name,))
                s_id = cursor.lastrowid
            
            # 2. Add to Broker Products
            cursor.execute("SELECT id FROM broker_products WHERE broker_id=%s AND local_ticker=%s", (GEMINI_ID, ticker))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO broker_products (broker_id, symbol_id, local_ticker, info) VALUES (%s, %s, %s, '{}')", 
                               (GEMINI_ID, s_id, ticker))
                count += 1
                
        print(f"✅ Successfully added {count} crypto pairs to Gemini.")
        
    except Exception as e:
        print(f"❌ Error syncing Gemini: {e}")

def setup_alpaca(cursor):
    print("📈 Adding Top Stocks to Alpaca...")
    count = 0
    for name, ticker in ALPACA_STOCKS:
        # 1. Add Global
        cursor.execute("SELECT id FROM global_symbols WHERE name = %s", (name,))
        res = cursor.fetchone()
        if res:
            s_id = res[0]
        else:
            cursor.execute("INSERT INTO global_symbols (name, asset_class) VALUES (%s, 'Stock')", (name,))
            s_id = cursor.lastrowid
            
        # 2. Add Broker Product
        cursor.execute("SELECT id FROM broker_products WHERE broker_id=%s AND local_ticker=%s", (ALPACA_ID, ticker))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO broker_products (broker_id, symbol_id, local_ticker, info) VALUES (%s, %s, %s, '{}')", 
                           (ALPACA_ID, s_id, ticker))
            count += 1
    print(f"✅ Successfully added {count} stocks to Alpaca.")

# --- RUN MAIN ---
if __name__ == "__main__":
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        setup_gemini(cursor)
        setup_alpaca(cursor)
        
        conn.commit()
        conn.close()
        print("\n🎉 SETUP COMPLETE! Check your Symbol Manager.")
    except Exception as e:
        print(f"🔥 Critical Error: {e}")