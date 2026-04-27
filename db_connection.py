# db_connection.py

import pymysql


def get_db():
    """
    Shared MySQL connection for the app.
    Uses the same settings you tested in test_insert_trade.py.
    """
    conn = pymysql.connect(
        host="meirniv.mysql.pythonanywhere-services.com",
        user="meirniv",
        password="mayyam28",
        database="meirniv$default",
        cursorclass=pymysql.cursors.DictCursor,
    )
    return conn
