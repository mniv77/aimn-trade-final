"""
Customer Bot - receives AIMN alerts and sends to THEIR broker
User keeps money, you just send signals!
"""
import requests, time
API_URL = "https://meirniv.pythonanywhere.com/api/alerts/latest"
# Customer sets their own Alpaca keys - you never see them!
ALPACA_KEY = "YOUR_KEY_HERE"
ALPACA_SECRET = "YOUR_SECRET_HERE"

def get_alerts():
    r = requests.get(API_URL)
    return r.json()["alerts"]

def send_to_broker(alert):
    # Example: Alpaca
    print(f"Sending to broker: {alert}")
    # requests.post("https://api.alpaca.markets/v2/orders", json={...}, headers={...})
    return True

while True:
    alerts = get_alerts()
    for a in alerts[:1]: # latest
        send_to_broker(a)
    time.sleep(60) # check every minute
