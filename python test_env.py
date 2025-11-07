#  python test_env.py

from config import ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL

print("✅ Loaded from .env successfully")
print("ALPACA_KEY starts with:", ALPACA_KEY[:4])
print("ALPACA_SECRET ends with:", ALPACA_SECRET[-4:])
print("ALPACA_BASE_URL:", ALPACA_BASE_URL)
