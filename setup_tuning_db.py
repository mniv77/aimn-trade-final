import mysql.connector
import config

def create_tuning_table():
    conn = mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME
    )
    cursor = conn.cursor()
    
    print("🛠 Resetting 'strategy_params' table...")
    
    # 1. Drop the old table so we can rebuild it correctly
    try:
        cursor.execute("DROP TABLE IF EXISTS strategy_params")
    except Exception as e:
        print(f"Warning dropping table: {e}")

    # 2. Create the new table
    query = """
    CREATE TABLE strategy_params (
        id INT AUTO_INCREMENT PRIMARY KEY,
        broker_product_id INT NOT NULL,
        
        direction VARCHAR(10) DEFAULT 'LONG',
        
        -- Entry Group
        macd_fast INT,
        macd_slow INT,
        macd_sig INT,
        rsi_len INT,
        rsi_entry FLOAT,
        
        -- Exit Group
        rsi_exit FLOAT,
        stop_loss FLOAT,
        trailing_start FLOAT,
        trailing_drop FLOAT,
        use_hard_tp BOOLEAN,
        take_profit FLOAT,
        decay_start FLOAT,
        decay_rate FLOAT,
        
        timeframe VARCHAR(10),
        
        FOREIGN KEY (broker_product_id) REFERENCES broker_products(id) ON DELETE CASCADE
    );
    """
    
    try:
        cursor.execute(query)
        conn.commit()
        print("✅ Success! New Tuning table created.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_tuning_table()