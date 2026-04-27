import mysql.connector
import getpass

print("=== AIMn MySQL Setup ===")
print("We are about to create the professional database structure.")

# 1. Get Connection Details
db_host = "MeirNiv.mysql.pythonanywhere-services.com"
db_user = "MeirNiv"
db_name = "MeirNiv$aimn_db"  # Standard PythonAnywhere format
db_pass = getpass.getpass("Enter your MySQL Password: ")

try:
    # 2. Connect to MySQL
    conn = mysql.connector.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        database=db_name
    )
    c = conn.cursor()
    print("✅ Connected successfully!")

    # 3. Create Tables
    
    # --- BROKERS MASTER TABLE ---
    c.execute("DROP TABLE IF EXISTS brokers")
    c.execute("""CREATE TABLE brokers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(50) UNIQUE NOT NULL,
        website VARCHAR(100),
        api_doc_url VARCHAR(100),
        type VARCHAR(20)
    )""")
    
    # Populate Brokers
    brokers = [
        ('Alpaca', 'https://alpaca.markets', 'https://alpaca.markets/docs/', 'STOCK/CRYPTO'),
        ('Gemini', 'https://www.gemini.com', 'https://docs.gemini.com/', 'CRYPTO'),
        ('Binance', 'https://www.binance.com', 'https://binance-docs.github.io/', 'CRYPTO'),
        ('OANDA', 'https://www.oanda.com', 'https://developer.oanda.com/', 'FOREX')
    ]
    c.executemany("INSERT INTO brokers (name, website, api_doc_url, type) VALUES (%s, %s, %s, %s)", brokers)
    print(" - Created Master Brokers Table.")

    # --- TRADES TABLE ---
    c.execute("""CREATE TABLE IF NOT EXISTS trade_sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        symbol VARCHAR(20),
        exchange VARCHAR(50),
        side VARCHAR(10),
        qty FLOAT,
        entry_price FLOAT,
        exit_price FLOAT,
        status VARCHAR(20),
        pnl_amount FLOAT,
        created_at BIGINT
    )""")
    
    # Inject Dummy Trades so the page isn't empty
    c.execute("INSERT INTO trade_sessions (symbol, exchange, side, qty, entry_price, status, pnl_amount) VALUES ('SOLUSD', 'Binance', 'BUY', 10, 145.00, 'CLOSED', 55.0)")
    print(" - Created Trade History Table.")

    # --- STATE TABLES (Balance, Market, Strategy) ---
    c.execute("DROP TABLE IF EXISTS broker_state")
    c.execute("""CREATE TABLE broker_state (
        id INT AUTO_INCREMENT PRIMARY KEY,
        balance FLOAT,
        equity FLOAT,
        open_pnl FLOAT,
        margin_used FLOAT
    )""")
    c.execute("INSERT INTO broker_state (balance, equity, open_pnl, margin_used) VALUES (10000.0, 10000.0, 0.0, 1.5)")

    c.execute("DROP TABLE IF EXISTS market_state")
    c.execute("""CREATE TABLE market_state (
        symbol VARCHAR(20) PRIMARY KEY,
        price FLOAT,
        change_24h FLOAT,
        high_24h FLOAT,
        low_24h FLOAT
    )""")
    c.execute("INSERT INTO market_state VALUES ('SOL/USD', 148.50, 2.5, 150.0, 140.0)")

    c.execute("DROP TABLE IF EXISTS strategy_perf")
    c.execute("""CREATE TABLE strategy_perf (
        id INT AUTO_INCREMENT PRIMARY KEY,
        win_rate FLOAT,
        profit_factor FLOAT,
        long_exposure FLOAT,
        short_exposure FLOAT,
        total_pnl_money FLOAT,
        total_pnl_pct FLOAT
    )""")
    c.execute("INSERT INTO strategy_perf (win_rate, profit_factor, total_pnl_money) VALUES (68.5, 1.8, 250.0)")

    c.execute("DROP TABLE IF EXISTS ai_metrics")
    c.execute("""CREATE TABLE ai_metrics (
        id INT AUTO_INCREMENT PRIMARY KEY,
        confidence FLOAT,
        signal_strength FLOAT,
        trend_score FLOAT,
        sentiment FLOAT
    )""")
    c.execute("INSERT INTO ai_metrics (confidence, signal_strength) VALUES (92.0, 8.5)")

    conn.commit()
    conn.close()
    print("\n🚀 SUCCESS: MySQL Database is initialized and ready.")

except mysql.connector.Error as err:
    print(f"\n❌ ERROR: {err}")
    print("Check your password and ensure you created a database named 'aimn_db' in the dashboard.")
