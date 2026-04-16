# db.py — project root
# Provides get_db_connection() for engine files using raw mysql.connector
import os
import mysql.connector

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host     = os.environ.get('PA_MYSQL_HOST', 'MeirNiv.mysql.pythonanywhere-services.com'),
            user     = os.environ.get('PA_MYSQL_USER', 'MeirNiv'),
            password = os.environ.get('PA_MYSQL_PW',   ''),
            database = os.environ.get('PA_MYSQL_DB',   'MeirNiv$default'),
            autocommit=True,
            charset  = 'utf8mb4',
        )
        cursor = conn.cursor(dictionary=True)
        return conn, cursor
    except Exception as e:
        print(f"[db] ❌ Connection failed: {e}")
        return None, None
