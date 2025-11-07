<<<<<<< HEAD
# filename: app/state.py
import sqlite3
import base64
from cryptography.fernet import Fernet
import os

# --- CONFIG ---
DB_FILE = os.path.join(os.path.dirname(__file__), "state.db")
KEY_FILE = os.path.join(os.path.dirname(__file__), "secret.key")


# --- ENCRYPTION HELPERS ---
def _load_or_create_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    else:
        with open(KEY_FILE, "rb") as f:
            key = f.read()
    return Fernet(key)

fernet = _load_or_create_key()


# --- DB INIT ---
def _init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            broker TEXT PRIMARY KEY,
            api_key TEXT,
            api_secret TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS params (
            symbol TEXT PRIMARY KEY,
            params TEXT
        )
    """)
    conn.commit()
    conn.close()

_init_db()


# --- CREDENTIALS ---
def save_credentials(broker, api_key, api_secret):
    enc_key = fernet.encrypt(api_key.encode())
    enc_secret = fernet.encrypt(api_secret.encode())
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO credentials VALUES (?, ?, ?)",
              (broker, enc_key.decode(), enc_secret.decode()))
    conn.commit()
    conn.close()

def load_credentials(broker):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT api_key, api_secret FROM credentials WHERE broker = ?", (broker,))
    row = c.fetchone()
    conn.close()
    if row:
        api_key = fernet.decrypt(row[0].encode()).decode()
        api_secret = fernet.decrypt(row[1].encode()).decode()
        return api_key, api_secret
    return None, None


# --- PARAMS ---
def save_params(symbol, params_json):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO params VALUES (?, ?)", (symbol, params_json))
    conn.commit()
    conn.close()

def load_params(symbol):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT params FROM params WHERE symbol = ?", (symbol,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def load_all_params():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT symbol, params FROM params")
    rows = c.fetchall()
    conn.close()
    return {symbol: params for symbol, params in rows}
=======
# filename: app/state.py
import sqlite3
import base64
from cryptography.fernet import Fernet
import os

# --- CONFIG ---
DB_FILE = os.path.join(os.path.dirname(__file__), "state.db")
KEY_FILE = os.path.join(os.path.dirname(__file__), "secret.key")


# --- ENCRYPTION HELPERS ---
def _load_or_create_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    else:
        with open(KEY_FILE, "rb") as f:
            key = f.read()
    return Fernet(key)

fernet = _load_or_create_key()


# --- DB INIT ---
def _init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            broker TEXT PRIMARY KEY,
            api_key TEXT,
            api_secret TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS params (
            symbol TEXT PRIMARY KEY,
            params TEXT
        )
    """)
    conn.commit()
    conn.close()

_init_db()


# --- CREDENTIALS ---
def save_credentials(broker, api_key, api_secret):
    enc_key = fernet.encrypt(api_key.encode())
    enc_secret = fernet.encrypt(api_secret.encode())
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO credentials VALUES (?, ?, ?)",
              (broker, enc_key.decode(), enc_secret.decode()))
    conn.commit()
    conn.close()

def load_credentials(broker):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT api_key, api_secret FROM credentials WHERE broker = ?", (broker,))
    row = c.fetchone()
    conn.close()
    if row:
        api_key = fernet.decrypt(row[0].encode()).decode()
        api_secret = fernet.decrypt(row[1].encode()).decode()
        return api_key, api_secret
    return None, None


# --- PARAMS ---
def save_params(symbol, params_json):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO params VALUES (?, ?)", (symbol, params_json))
    conn.commit()
    conn.close()

def load_params(symbol):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT params FROM params WHERE symbol = ?", (symbol,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def load_all_params():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT symbol, params FROM params")
    rows = c.fetchall()
    conn.close()
    return {symbol: params for symbol, params in rows}
>>>>>>> 0c0df91 (Initial push)
