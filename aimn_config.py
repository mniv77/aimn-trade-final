# config.py
# FINAL CLEAN VERSION - NO IMPORTS NEEDED

# --- DATABASE SETTINGS ---
# We are hardcoding these to guarantee the connection works.
DB_HOST = "MeirNiv.mysql.pythonanywhere-services.com"
DB_USER = "MeirNiv"
DB_NAME = "MeirNiv$default"
DB_PASSWORD = "TradingStrategy2025"  # <--- REPLACE THIS WITH YOUR REAL PASSWORD

# --- TRADING SETTINGS ---
ALPACA_KEY = "PK_DEFAULT"
ALPACA_SECRET = "SK_DEFAULT"
PAPER_TRADING = True
LOG_FILE = "data/aimn_crypto_trading.log"