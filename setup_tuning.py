# setup_tuning.py - RUN THIS ONCE TO FILL YOUR TUNING PAGE
import mysql.connector

# --- CONFIGURATION ---
DB_HOST = "MeirNiv.mysql.pythonanywhere-services.com"
DB_USER = "MeirNiv"
DB_NAME = "MeirNiv$default"
DB_PASSWORD = "TradingStrategy2025" # <--- TYPE YOUR REAL PASSWORD HERE

def populate_tuning():
    print("Connecting to database...")
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
        )
        cursor = conn.cursor()

        # These are the default strategies we want to add
        # You can edit these later on the website!
        symbols = ['BTCUSD', 'ETHUSD', 'SOLUSD']
        params = [
            ('RSI_Overbought', '70'),
            ('RSI_Oversold', '30'),
            ('MACD_Fast', '12'),
            ('MACD_Slow', '26'),
            ('Take_Profit_Pct', '1.5'),
            ('Stop_Loss_Pct', '0.5')
        ]

        print("Inserting default parameters...")
        
        for sym in symbols:
            for p_name, p_val in params:
                # The SQL below says: "Insert this ONLY if it doesn't exist yet"
                # This prevents duplicates if you run the script twice.
                sql = """
                INSERT INTO strategy_params (symbol, param_name, value) 
                SELECT %s, %s, %s 
                WHERE NOT EXISTS (
                    SELECT 1 FROM strategy_params WHERE symbol=%s AND param_name=%s
                )
                """
                cursor.execute(sql, (sym, p_name, p_val, sym, p_name))

        conn.commit()
        conn.close()
        print("\nSUCCESS! Your Tuning page is now full of data.")
        
    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    populate_tuning()