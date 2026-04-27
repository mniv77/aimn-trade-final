import mysql.connector
import getpass

print("=== Creating LONG Strategy ===")
db_host = "MeirNiv.mysql.pythonanywhere-services.com"
db_user = "MeirNiv"
db_name = "MeirNiv$default"
db_pass = getpass.getpass("Enter MySQL Password: ")

conn = mysql.connector.connect(host=db_host, user=db_user, password=db_pass, database=db_name)
c = conn.cursor()

# 1. Check if LONG already exists
c.execute("SELECT id FROM strategy_params WHERE direction='LONG' AND symbol='SOLUSD'")
row = c.fetchone()

if row:
    print(f"✅ LONG Strategy already exists (ID: {row[0]}). No action needed.")
else:
    # 2. Insert Default LONG Strategy
    print("... Creating Default LONG Strategy ...")
    sql = """INSERT INTO strategy_params 
             (symbol, broker, direction, timeframe, 
              macd_fast, macd_slow, macd_signal, 
              rsi_entry, rsi_exit, 
              stop_loss_pct, init_profit_pct, created_at)
             VALUES 
             ('SOLUSD', 'Alpaca', 'LONG', '15m',
              12, 26, 9,
              30.0, 70.0,
              2.0, 4.0, NOW())"""
    c.execute(sql)
    conn.commit()
    print("🚀 SUCCESS: LONG Strategy created! You can now tune it.")

conn.close()
