# file: test_alpaca.py
from alpaca_trade_api.rest import REST
from dotenv import load_dotenv
import os

load_dotenv()

KEY = os.getenv("ALPACA_KEY")
SECRET = os.getenv("ALPACA_SECRET")
URL = os.getenv("ALPACA_BASE_URL")

print("Connecting with:")
print("KEY =", KEY)
print("SECRET (last 4) =", SECRET[-4:])
print("URL =", URL)

api = REST(KEY, SECRET, base_url=URL)
try:
    account = api.get_account()
    print("✅ Connected! Account ID:", account.id)
    print("Account Status:", account.status)
except Exception as e:
    print("❌ ERROR:", e)
