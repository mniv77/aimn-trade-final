import mysql.connector
import ccxt
import config

print("🔍 STARTING SYSTEM DIAGNOSTIC...\n")

# 1. TEST DATABASE CONNECTION
print("1️⃣  Testing Database Connection...")
try:
    conn = mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database="MeirNiv$default"
    )
    cursor = conn.cursor(dictionary=True)
    print("   ✅ Database Connected Successfully.")
except Exception as e:
    print(f"   ❌ DATABASE ERROR: {e}")
    exit()

# 2. TEST ACTIVE STRATEGIES
print("\n2️⃣  Checking for Active Strategies...")
cursor.execute("""
    SELECT sp.id, sp.direction, bp.local_ticker, sp.active 
    FROM strategy_params sp
    JOIN broker_products bp ON sp.broker_product_id = bp.id
    WHERE sp.active = 1
""")
rows = cursor.fetchall()

if len(rows) == 0:
    print("   ❌ NO ACTIVE STRATEGIES FOUND.")
    print("   -> Go to Tuning Page and click SAVE on a symbol again.")
else:
    print(f"   ✅ Found {len(rows)} Active Strategies:")
    for r in rows:
        print(f"      -> ID {r['id']}: {r['local_ticker']} ({r['direction']})")

# 3. TEST GEMINI API CONNECTION
print("\n3️⃣  Testing Gemini API Connection...")
try:
    exchange = ccxt.gemini({
        'apiKey': config.API_KEY,
        'secret': config.API_SECRET,
        'enableRateLimit': True,
    })
    # Try to fetch ONE price
    test_symbol = 'BTC/USD'
    print(f"   ... Attempting to fetch price for {test_symbol} ...")
    ticker = exchange.fetch_ticker(test_symbol)
    price = ticker['last']
    print(f"   ✅ API SUCCESS! Current BTC Price: ${price:,.2f}")

except Exception as e:
    print(f"   ❌ API ERROR: {e}")
    print("   -> Check your API KEY and SECRET in config.py")
    print("   -> Check if Gemini requires a specific IP whitelist.")

print("\n🏁 DIAGNOSTIC COMPLETE.")