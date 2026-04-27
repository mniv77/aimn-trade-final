# final_repair.py
import mysql.connector
from config import DB_HOST, DB_USER, DB_NAME, DB_PASSWORD

def repair():
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    cursor = conn.cursor()

    print("Dropping old table...")
    cursor.execute("DROP TABLE IF EXISTS strategy_params")

    print("Creating table with 'param_name' column...")
    cursor.execute("""
    CREATE TABLE strategy_params (
        id INT AUTO_INCREMENT PRIMARY KEY,
        symbol VARCHAR(20),
        param_name VARCHAR(50),
        value VARCHAR(50)
    )
    """)

    # Insert minimal defaults so the code has something to 'ORDER BY'
    cursor.execute("INSERT INTO strategy_params (symbol, param_name, value) VALUES ('BTCUSD', 'rsiEntry', '30')")
    
    conn.commit()
    conn.close()
    print("✅ Repair Complete!")

if __name__ == "__main__":
    repair()
