# price_updater.py - AiMN V3.1
# Updates last_price in broker_products every 5 seconds
# Gemini: crypto prices
# Alpaca: stock/ETF prices during market hours
import mysql.connector
import requests
import time
import db_config as config

ALPACA_KEY    = 'PK2HFODS3RW3PWLCPG2K'
ALPACA_SECRET = 'Vs09krhOfWs58GwWGezYzlow7O34pF8MTrcm0rb5'
ALPACA_URL    = 'https://data.alpaca.markets/v2/stocks'

def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True
    )

def fetch_gemini_price(symbol):
    """Fetch live price from Gemini ticker"""
    try:
        clean = symbol.replace('/', '').lower()
        url   = f"https://api.gemini.com/v1/pubticker/{clean}"
        r     = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()['last'])
        return None
    except Exception as e:
        print(f"❌ Gemini error {symbol}: {e}", flush=True)
        return None

def fetch_alpaca_prices(symbols):
    """Fetch latest prices for multiple stocks from Alpaca"""
    try:
        headers = {
            'APCA-API-KEY-ID'     : ALPACA_KEY,
            'APCA-API-SECRET-KEY' : ALPACA_SECRET
        }
        # Batch request for all symbols
        syms = ','.join(symbols)
        url  = f"{ALPACA_URL}/trades/latest?symbols={syms}&feed=iex"
        r    = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data   = r.json()
            trades = data.get('trades', {})
            prices = {}
            for sym, trade in trades.items():
                prices[sym] = float(trade.get('p', 0))
            return prices
        else:
            print(f"❌ Alpaca error: {r.status_code} {r.text[:100]}", flush=True)
            return {}
    except Exception as e:
        print(f"❌ Alpaca fetch error: {e}", flush=True)
        return {}

def is_market_open():
    """Check if US stock market is open (PST)"""
    from datetime import datetime
    import pytz
    pst  = pytz.timezone('America/Los_Angeles')
    now  = datetime.now(pst)
    dow  = now.weekday()  # 0=Mon, 6=Sun
    hour = now.hour
    mins = now.minute
    time_mins = hour * 60 + mins
    if dow >= 5:  # Weekend
        return False
    # 6:30am - 1:00pm PST
    return 390 <= time_mins < 780

def update_prices():
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT bp.id, bp.local_ticker as symbol,
                   b.name as broker_name,
                   ms.is_24_7
            FROM broker_products bp
            JOIN brokers b ON bp.broker_id = b.id
            LEFT JOIN market_sessions ms ON bp.session_id = ms.id
        """)
        products = cursor.fetchall()

        # Separate crypto and stocks
        crypto_products = [p for p in products if p.get('is_24_7') == 1 or p['broker_name'].upper() == 'GEMINI']
        stock_products  = [p for p in products if p.get('is_24_7') != 1 and p['broker_name'].upper() == 'ALPACA']

        # ── CRYPTO: Gemini ───────────────────────────────
        for p in crypto_products:
            price = fetch_gemini_price(p['symbol'])
            if not price or price <= 0:
                continue
            cursor.execute("UPDATE broker_products SET last_price = %s WHERE id = %s", (price, p['id']))
            cursor.execute("UPDATE active_trades SET last_price = %s WHERE broker_product_id = %s AND status = 'OPEN'", (price, p['id']))
            print(f"✅ {p['symbol']}: ${price:,.2f}", flush=True)

        # ── STOCKS: Alpaca (only during market hours) ───
        if stock_products and is_market_open():
            symbols = [p['symbol'] for p in stock_products]
            prices  = fetch_alpaca_prices(symbols)

            for p in stock_products:
                sym   = p['symbol']
                price = prices.get(sym, 0)
                if not price or price <= 0:
                    continue
                cursor.execute("UPDATE broker_products SET last_price = %s WHERE id = %s", (price, p['id']))
                cursor.execute("UPDATE active_trades SET last_price = %s WHERE broker_product_id = %s AND status = 'OPEN'", (price, p['id']))
                print(f"✅ {sym}: ${price:,.2f}", flush=True)
        elif stock_products:
            print("⏰ Stock market closed — skipping Alpaca", flush=True)

    except Exception as e:
        print(f"🔥 Error: {e}", flush=True)
    finally:
        cursor.close()
        conn.close()

def main():
    print("=" * 50)
    print("PRICE UPDATER — Gemini + Alpaca")
    print("Reads:  broker_products")
    print("Writes: broker_products.last_price")
    print("        active_trades.last_price")
    print("=" * 50)
    cycle = 0
    while True:
        try:
            cycle += 1
            print(f"\n[Cycle {cycle}] {time.strftime('%H:%M:%S')}", flush=True)
            update_prices()
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n👋 Stopped")
            break
        except Exception as e:
            print(f"💥 Error: {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()