# file: test_alpaca_account.py

import requests
from config import ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL

def test_account():
    url = f"{ALPACA_BASE_URL.rstrip('/')}/v2/account"
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print("✅ Status:", resp.status_code)
        print("Response JSON:", resp.json())
    except Exception as e:
        print("❌ Error:", e)

if __name__ == "__main__":
    test_account()
