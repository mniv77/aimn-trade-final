# test_insert_trade.py

from datetime import datetime
import pymysql
from db_trades import record_trade


def get_db():
    """
    Simple direct MySQL connection for the test.
    FILL IN your own values for host, user, password, and database.
    """
  
    
    
    conn = pymysql.connect(
        host="MeirNiv.mysql.pythonanywhere-services.com",
        user="MeirNiv",
        password="mayyam28",
        database="MeirNiv$default",
        cursorclass=pymysql.cursors.DictCursor,
    )
    return conn


def main():
    conn = get_db()

    broker = "TEST_BROKER"
    symbol = "BTCUSD"
    side = "BUY"
    qty = 0.01
    entry_price = 50000.0
    exit_price = 50500.0
    entry_ts = datetime(2025, 1, 1, 0, 0, 0)
    exit_reason = "TEST_INSERT"

    record_trade(
        db_conn=conn,
        broker=broker,
        symbol=symbol,
        side=side,
        qty=qty,
        entry_price=entry_price,
        exit_price=exit_price,
        entry_ts=entry_ts,
        exit_reason=exit_reason
    )

    print("✅ Test trade inserted into `trades` table.")


if __name__ == "__main__":
    main()
