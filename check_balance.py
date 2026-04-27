import ccxt
import config

print("🔍 CONNECTING TO GEMINI...")
exchange = ccxt.gemini({
    'apiKey': config.API_KEY,
    'secret': config.API_SECRET,
})

try:
    # Fetch total balance
    balance = exchange.fetch_balance()
    
    print("\n💰 YOUR WALLET BALANCES:")
    print("-" * 30)
    
    # Loop through and only show what you actually have
    for currency, amount in balance['total'].items():
        if amount > 0:
            free = balance[currency]['free']
            used = balance[currency]['used']
            print(f"💵 {currency}: {amount} (Free: {free} | Locked: {used})")
            
    print("-" * 30)
    print("NOTE: To buy ETH/USD, you need 'USD' in the 'Free' column.")

except Exception as e:
    print(f"❌ ERROR: {e}")
