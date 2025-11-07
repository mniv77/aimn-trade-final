# config.py

import os
from pathlib import Path

# Securely load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Load API credentials from environment
#LPACA_SECRET = os.getenv("APCA_API_SECRET_KEY", "")

ALPACA_KEY = "PKIU63SSI0ZS85BQUY2E"
ALPACA_SECRET = "lwG2g6Hrgtd6V1oWwGjzcvdOQgMxfgAmVdgo88Pq"
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

PAPER_TRADING = True  # or False if you're using a live account

# === SYMBOLS TO SCAN ===
SYMBOLS = [
    'BTC/USD',
    'ETH/USD',
    'LTC/USD',
    'BCH/USD',
    'LINK/USD',
    'UNI/USD',
    'AAVE/USD'
]

# === STRATEGY PARAMETERS ===
TIMEFRAME = '1Min'

SYMBOL_PARAMS = {
    'BTC/USD': {
        'rsi_window': 100,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'volume_threshold': 0.9,
        'atr_multiplier': 1.3,
        'obv_period': 20
    },
    'ETH/USD': {
        'rsi_window': 100,
        'rsi_oversold': 30,
        'rsi_overbought': 70,
        'macd_fast': 12,
        'macd_slow': 26,
        'macd_signal': 9,
        'volume_threshold': 0.9,
        'atr_multiplier': 1.3,
        'obv_period': 20
    }
}

# === LOGGING CONFIG ===
LOG_FILE = "data/aimn_crypto_trading.log"
LOG_LEVEL = "INFO"

# === MODE ===
PAPER_TRADING = True

# Add this at the end of config.py
settings = {
    "SYMBOL": "BTC/USD",  # Default symbol to trade
    "SLEEP_INTERVAL": 60,  # Seconds between checks
}
settings = {"SYMBOL": "BTC/USD", "SLEEP_INTERVAL": 60} 
