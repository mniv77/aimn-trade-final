# setup_broker_db.py - UPGRADES DATABASE FOR API MANAGER
import mysql.connector

# --- CONFIGURATION ---
DB_HOST = "MeirNiv.mysql.pythonanywhere-services.com"
DB_USER = "MeirNiv"
DB_NAME = "MeirNiv$default"
DB_PASSWORD = "TradingStrategy2025"  # <--- YOUR PASSWORD

def upgrade_db():
    print("Connecting to database...")
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    cursor = conn.cursor()

    # 1. Create table for API Keys
    print("Creating 'broker_config' table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS broker_config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        broker_name VARCHAR(50),
        api_key VARCHAR(255),
        api_secret VARCHAR(255),
        is_sandbox BOOLEAN DEFAULT FALSE
    )
    """)

    # 2. Upgrade 'symbols' table to support Exchange names
    # We will just drop and recreate it to be clean (since it only has test data)
    print("Upgrading 'symbols' table...")
    cursor.execute("DROP TABLE IF EXISTS symbols")
    cursor.execute("""
    CREATE TABLE symbols (
        id INT AUTO_INCREMENT PRIMARY KEY,
        symbol VARCHAR(20),
        exchange VARCHAR(50) DEFAULT 'GEMINI',
        status VARCHAR(10) DEFAULT 'Active'
    )
    """)

    conn.commit()
    conn.close()
    print("\nSUCCESS! Database ready for the new Symbol Manager.")

if __name__ == "__main__":
    try:
        upgrade_db()
    except Exception as e:
        print(f"\nERROR: {e}")