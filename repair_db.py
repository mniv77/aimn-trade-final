import mysql.connector

# --- CONFIGURATION ---
DB_HOST = "MeirNiv.mysql.pythonanywhere-services.com"
DB_USER = "MeirNiv"
DB_NAME = "MeirNiv$default"
DB_PASSWORD = "TradingStrategy2025" # <--- IMPORTANT: PUT YOUR PASSWORD HERE

def repair():
    print("Connecting to database...")
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    cursor = conn.cursor()

    # 1. Drop the problematic table
    print("Dropping old strategy_params table...")
    cursor.execute("DROP TABLE IF EXISTS strategy_params")

    # 2. Create it with the correct columns
    print("Creating correct strategy_params table...")
    cursor.execute("""
    CREATE TABLE strategy_params (
        id INT AUTO_INCREMENT PRIMARY KEY,
        symbol VARCHAR(20),
        param_name VARCHAR(50),
        value VARCHAR(50)
    )
    """)

    # 3. Add some starting data so the scanner has rules to read
    print("Adding default rules...")
    default_rules = [
        ('BTCUSD', 'rsiEntry', '30'),
        ('BTCUSD', 'rsiExit', '70'),
        ('BTCUSD', 'sl', '2.0'),
        ('BTCUSD', 'tp', '6.0')
    ]
    cursor.executemany(
        "INSERT INTO strategy_params (symbol, param_name, value) VALUES (%s, %s, %s)",
        default_rules
    )

    conn.commit()
    conn.close()
    print("\n✅ DATABASE REPAIRED! The 'param_name' column now exists.")

if __name__ == "__main__":
    repair()
