import os
import mysql.connector

def get_db_connection():
    host = os.environ.get('DB_HOST') or os.environ.get('PA_MYSQL_HOST') or 'MeirNiv.mysql.pythonanywhere-services.com'
    user = os.environ.get('DB_USER') or os.environ.get('PA_MYSQL_USER') or 'MeirNiv'
    pw = os.environ.get('DB_PASSWORD') or os.environ.get('MYSQL_PASSWORD') or os.environ.get('PA_MYSQL_PW') or 'mayyam28'
    database = os.environ.get('DB_NAME') or os.environ.get('PA_MYSQL_DB') or 'MeirNiv$default'
    try:
        conn = mysql.connector.connect(
            host=host, user=user, password=pw, database=database,
            autocommit=True, charset='utf8mb4', connection_timeout=10
        )
        cursor = conn.cursor(dictionary=True)
        return conn, cursor
    except Exception as e:
        print(f"[db] ❌ Connection failed host={host} user={user} db={database} err={e}")
        return None, None

def get_db():
    c,_ = get_db_connection()
    return c

class _DB:
    def remove(self): pass
    def rollback(self): pass
db=_DB()
