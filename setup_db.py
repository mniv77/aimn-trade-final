# setup_db.py - RUN THIS ONCE TO BUILD YOUR DATABASE
import mysql.connector

# --- CONFIGURATION ---
DB_HOST = "MeirNiv.mysql.pythonanywhere-services.com"
DB_USER = "MeirNiv"
DB_NAME = "MeirNiv$default"
DB_PASSWORD = "TradingStrategy2025"  # <--- YOUR PASSWORD

def create_tables():
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    cursor = conn.cursor()

    print("1. Creating 'symbols' table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS symbols (
        symbol VARCHAR(20) PRIMARY KEY,
        status VARCHAR(10) DEFAULT 'Active'
    )
    """)

    print("2. Creating 'scanner_results' table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scanner_results (
        id INT AUTO_INCREMENT PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        symbol VARCHAR(20),
        pattern VARCHAR(50),
        confidence INT
    )
    """)

    print("3. Creating 'orders' table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        symbol VARCHAR(20),
        side VARCHAR(10),
        price DECIMAL(10, 2),
        status VARCHAR(20)
    )
    """)
    
    print("4. Creating 'popup_picks' table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS popup_picks (
        id INT AUTO_INCREMENT PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        symbol VARCHAR(20),
        pick_score INT,
        reason VARCHAR(255)
    )
    """)

    print("5. Creating 'strategy_params' table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS strategy_params (
        id INT AUTO_INCREMENT PRIMARY KEY,
        symbol VARCHAR(20),
        param_name VARCHAR(50),
        value VARCHAR(50)
    )
    """)

    print("6. Creating Manager Console View...")
    # We drop it first to ensure we can recreate it cleanly
    cursor.execute("DROP VIEW IF EXISTS manager_console_view")
    cursor.execute("""
    CREATE VIEW manager_console_view AS
    SELECT 
        s.symbol, 
        'WeBull/Coinbase' as broker, 
        s.status, 
        (SELECT pattern FROM scanner_results WHERE symbol = s.symbol ORDER BY timestamp DESC LIMIT 1) as current_signal,
        NOW() as timestamp
    FROM symbols s
    """)

    print("7. Inserting default data...")
    # Add some initial symbols so the bot has something to do
    try:
        cursor.execute("INSERT IGNORE INTO symbols (symbol, status) VALUES ('BTCUSD', 'Active')")
        cursor.execute("INSERT IGNORE INTO symbols (symbol, status) VALUES ('ETHUSD', 'Active')")
        cursor.execute("INSERT IGNORE INTO symbols (symbol, status) VALUES ('SOLUSD', 'Active')")
        print("   - Added BTC, ETH, SOL")
    except:
        pass

    conn.commit()
    conn.close()
    print("\nSUCCESS! Database structure created successfully.")

if __name__ == "__main__":
    try:
        create_tables()
    except Exception as e:
        print(f"\nERROR: {e}")