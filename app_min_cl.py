# app_min.py - Shows ALL symbols with filter status
import os, time, json, sqlite3
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timezone
import random

# from db_connection import get_db
from db_trades import record_trade

import pymysql
from alpaca_client import place_market_order, get_latest_price







ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
STATIC    = ROOT / "static"

app = Flask(
    __name__,
    template_folder=str(TEMPLATES),
    static_folder=str(STATIC)
)



# ============================================================================
# MARKET HOURS & TRADING STATUS
# ============================================================================
def get_db():
    """
    Shared MySQL connection for the app.
    """
    conn = pymysql.connect(
        host="MeirNiv.mysql.pythonanywhere-services.com",
        user="MeirNiv",
        password="mayyam28",
        database="MeirNiv$default",
        cursorclass=pymysql.cursors.DictCursor,
    )
    return conn






def is_market_open(exchange):
    """Check if market/exchange is currently open"""
    now = datetime.now(timezone.utc)
    day_of_week = now.weekday()  # 0=Monday, 6=Sunday
    hour = now.hour

    exchange = exchange.upper()

    # Crypto - always open
    if exchange in ['CRYPTO', 'GEMINI', 'BINANCE', 'COINBASE', 'ALPACA_CRYPTO']:
        return True

    # Forex - 24/5 (closed weekends)
    if exchange == 'FOREX':
        return day_of_week < 5  # Monday-Friday

    # Stock markets (NYSE, NASDAQ, ALPACA) - only weekdays during trading hours
    if exchange in ['NYSE', 'NASDAQ', 'ALPACA']:
        # Weekend check
        if day_of_week >= 5:  # Saturday or Sunday
            return False
        # Trading hours: 9:30 AM - 4:00 PM ET (approximately 14:30-21:00 UTC)
        # Extended hours: 4:00 AM - 8:00 PM ET (approximately 9:00-1:00 UTC next day)
        # For simplicity, we'll allow 9:00-22:00 UTC on weekdays
        return 9 <= hour < 22

    # Futures - nearly 24/5
    if exchange == 'FUTURES':
        return day_of_week < 5

    # Unknown exchange - assume closed for safety
    return False

def get_mock_symbol_data(symbol, exchange):
    """Generate mock data for a symbol (replace with real broker API later)"""

    # Base prices for common symbols
    base_prices = {
        # Stocks
        'AAPL': 175.50, 'TSLA': 245.30, 'NVDA': 391.25, 'MSFT': 378.15,
        'GOOGL': 138.50, 'META': 488.90, 'NFLX': 485.20, 'AMD': 156.80,
        'AMZN': 152.30, 'JPM': 158.90, 'WMT': 168.45, 'V': 268.75,
        'INTC': 43.20, 'CSCO': 51.30, 'ADBE': 588.90, 'PYPL': 62.15,
        # Crypto
        'BTC/USD': 43250.00, 'ETH/USD': 2280.50, 'SOL/USD': 98.75, 'AVAX/USD': 36.20,
        # ETFs
        'SPY': 458.75, 'QQQ': 395.20, 'IWM': 198.50, 'DIA': 378.30
    }

    base_price = base_prices.get(symbol, 100.0)

    # Generate realistic data
    price_change_pct = (random.random() - 0.5) * 8  # -4% to +4%
    current_price = base_price * (1 + price_change_pct / 100)

    # RSI: more likely to be in middle range, but sometimes extreme
    rsi = random.gauss(50, 20)  # Normal distribution around 50
    rsi = max(0, min(100, rsi))  # Clamp to 0-100

    # ATR as % of price
    atr_pct = random.uniform(0.3, 3.5)

    # Volume (higher for stocks, lower for crypto)
    if 'CRYPTO' in exchange or '/' in symbol:
        volume = random.randint(100000, 5000000)
        avg_volume = volume * random.uniform(0.7, 1.3)
    else:
        volume = random.randint(1000000, 50000000)
        avg_volume = volume * random.uniform(0.7, 1.3)

    return {
        'symbol': symbol,
        'exchange': exchange,
        'price': round(current_price, 2),
        'change_pct': round(price_change_pct, 2),
        'rsi': round(rsi, 1),
        'atr_pct': round(atr_pct, 2),
        'volume': int(volume),
        'avg_volume': int(avg_volume),
        'volume_ratio': round(volume / avg_volume, 2),
        'last_trade_age_seconds': random.randint(1, 120)
    }

def check_filters(data):
    """
    Multi-filter system - returns which filters passed

    Filters:
    1. RSI Extremes: RSI < 25 OR RSI > 75
    2. ATR (Volatility): ATR > 1.0% (symbol is moving)
    3. Volume OR Price: (Volume > 1.5x avg) OR (Price change > 2%)
    4. Recent Activity: Last trade within 60 seconds
    """

    # Filter 1: RSI Extremes
    rsi_pass = data['rsi'] < 25 or data['rsi'] > 75

    # Filter 2: ATR (Volatility)
    atr_pass = data['atr_pct'] > 1.0

    # Filter 3: Volume Spike OR Big Move
    volume_spike = data['volume_ratio'] > 1.5
    big_move = abs(data['change_pct']) > 2.0
    volume_or_move_pass = volume_spike or big_move

    # Filter 4: Recent Activity
    recent_pass = data['last_trade_age_seconds'] < 60

    # ALL must pass
    all_passed = rsi_pass and atr_pass and volume_or_move_pass and recent_pass

    return {
        'passed_all': all_passed,
        'rsi_extreme': rsi_pass,
        'has_volatility': atr_pass,
        'volume_or_movement': volume_or_move_pass,
        'recently_traded': recent_pass,
        'score': sum([rsi_pass, atr_pass, volume_or_move_pass, recent_pass])  # 0-4
    }

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/api/health")
def api_health():
    return jsonify(ok=True)

@app.get("/api/scanner/all_symbols")
def api_scanner_all_symbols():
    """
    Returns ALL symbols with their filter status
    Scanner will color-code them based on filters
    """

    # Define symbol universe by exchange
    # NOTE: Alpaca supports both stocks AND crypto!
    symbol_universe = {
        'ALPACA': ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL', 'META', 'NFLX', 'AMD', 'AMZN'],
        'ALPACA_CRYPTO': ['BTC/USD', 'ETH/USD', 'DOGE/USD', 'SHIB/USD'],  # Alpaca crypto
        'NYSE': ['SPY', 'QQQ', 'JPM', 'WMT', 'V', 'DIA', 'IWM'],
        'NASDAQ': ['INTC', 'CSCO', 'ADBE', 'PYPL'],
        'CRYPTO': ['SOL/USD', 'AVAX/USD', 'MATIC/USD', 'DOT/USD']
    }

    all_symbols = []
    market_status = {}

    for exchange, symbols in symbol_universe.items():
        # Check if market is open
        is_open = is_market_open(exchange)
        market_status[exchange] = {
            'is_open': is_open,
            'scanning': is_open,
            'symbol_count': len(symbols)
        }

        # Scan ALL symbols (even if market closed - we'll show them grayed)
        for symbol in symbols:
            data = get_mock_symbol_data(symbol, exchange)
            filter_result = check_filters(data)

            # Determine signal based on RSI
            if data['rsi'] < 25:
                signal = 'BUY'
            elif data['rsi'] > 75:
                signal = 'SELL'
            else:
                signal = 'NEUTRAL'

            all_symbols.append({
                'symbol': symbol,
                'exchange': exchange,
                'market_open': is_open,
                'price': data['price'],
                'change_pct': data['change_pct'],
                'rsi': data['rsi'],
                'signal': signal,
                'volume': data['volume'],
                'volume_ratio': data['volume_ratio'],
                'atr_pct': data['atr_pct'],
                'quantity': 0.01 if ('CRYPTO' in exchange or '/' in symbol) else 10,
                'filters': filter_result,
                'ready_to_trade': is_open and filter_result['passed_all']
            })

    return jsonify({
        'ok': True,
        'timestamp': int(time.time() * 1000),
        'market_status': market_status,
        'symbols': all_symbols,
        'total_symbols': len(all_symbols),
        'ready_to_trade': sum(1 for s in all_symbols if s['ready_to_trade'])
    })

@app.get("/api/live_price")
def api_live_price():
    """
    Return live price (and RSI) for popup.
    This is defensive: it works even if get_mock_symbol_data() is missing
    or doesn't have 'price'/'rsi'.
    """
    symbol   = request.args.get('symbol', 'UNKNOWN')
    exchange = request.args.get('exchange', 'UNKNOWN')

    price = 0.0
    rsi   = None
    data  = {}

    # --- Try to use existing mock function if it exists ---
    try:
        # If get_mock_symbol_data is defined above in this file, this will work.
        data = get_mock_symbol_data(symbol, exchange)  # may raise NameError or anything
    except Exception:
        data = {}

    if isinstance(data, dict):
        try:
            raw_price = data.get("price", 0)
            price = float(raw_price or 0.0)
        except Exception:
            price = 0.0

        rsi = data.get("rsi")

    # --- Fallback if price is missing or <= 0 ---
    if not price or price <= 0:
        # Give a sensible base price by symbol, so ETH/BTC/etc look nicer
        base_map = {
            "BTC/USD": 50000.0,
            "ETH/USD": 3500.0,
            "CL-OIL":  80.0,
            "GC-GOLD": 2000.0,
            "ES-SPX":  5000.0,
        }
        base = base_map.get(symbol, 100.0)
        # Small random jitter so it’s not static
        price = base * (1.0 + random.uniform(-0.01, 0.01))

    # --- Fallback RSI if missing ---
    if rsi is None:
        rsi = random.uniform(15, 85)

    return jsonify({
        "ok": True,
        "symbol": symbol,
        "exchange": exchange,
        "price": float(price),
        "last": float(price),
        "rsi": float(rsi),
        "timestamp": int(time.time() * 1000),
    })
#====================================================


# ...

@app.route("/api/trade/open", methods=["POST"])
def api_trade_open():
    """
    Called by the popup when a new trade starts.
    - For ALPACA (stocks/ETFs): send a real paper order to Alpaca.
    - For anything else (CRYPTO, FUTURES, etc.): simulate entry using live price.
    Returns: { ok, entry_price }
    """
    data = request.get_json(force=True) or {}
    symbol   = data.get("symbol", "").upper()
    exchange = (data.get("exchange") or "").upper()
    side     = (data.get("side") or "BUY").upper()
    qty      = float(data.get("qty") or 0)

    # Safety defaults
    if qty <= 0:
        qty = 10.0

    # Decide if we should talk to Alpaca or simulate
    entry_price = None
    broker_name = exchange  # we store this as "broker" field in trades

    try:
        if exchange in ("ALPACA", "NYSE", "NASDAQ"):
            # Real Alpaca paper trade
            order = place_market_order(symbol=symbol, side=side, qty=qty)
            # Alpaca returns "filled_avg_price" once filled; sometimes None if not filled yet.
            filled_price = order.get("filled_avg_price")
            if filled_price:
                entry_price = float(filled_price)
            else:
                # Fallback: ask Alpaca for latest price
                entry_price = get_latest_price(symbol)
        else:
            # Simulated entry (CRYPTO / FUTURES / anything not on Alpaca)
            # Use same price API as popup for consistency
            # Here we just call the live_price endpoint logic directly
            from math import fabs
            from random import random

            # Light-weight local mock: you already do something similar in api_live_price
            # We'll re-use that to keep behavior consistent.
            from flask import current_app

            with current_app.test_request_context(
                f"/api/live_price?symbol={symbol}&exchange={exchange}"
            ):
                resp = api_live_price()
                j = resp.get_json()
                p = float(j.get("price", 0) or 0)
                if p <= 0:
                    # fallback random-ish price
                    p = 100.0 + (random() - 0.5) * 10.0
            entry_price = p

    except Exception as e:
        # If anything fails, we still want popup to keep going with a simulated entry
        print("ERROR in api_trade_open:", e)
        # Fallback: use live_price mock
        with app.test_request_context(
            f"/api/live_price?symbol={symbol}&exchange={exchange}"
        ):
            resp = api_live_price()
            j = resp.get_json()
            p = float(j.get("price", 0) or 0)
            if p <= 0:
                p = 100.0
        entry_price = p
        broker_name = f"{exchange}_SIM"

    # Return entry price to popup
    return jsonify({
        "ok": True,
        "symbol": symbol,
        "exchange": exchange,
        "side": side,
        "qty": qty,
        "broker": broker_name,
        "entry_price": entry_price,
    })


# ============================================================================
# UI ROUTES
# ============================================================================

@app.route("/", endpoint="index")
def index():
    return render_template("index.html")

@app.route("/tuning", endpoint="tuning")
def tuning():
    return render_template("tuning.html")

@app.route("/scanner", endpoint="scanner")
def scanner():
    return render_template("aimn_flowing_scanner_auto.html")

@app.route("/symbol-api-manager", endpoint="symbol-api-manager")
def symbol_api_manager():
    return render_template("symbol_api_manager.html")

@app.route("/trade-tester", endpoint="trade_tester")
def trade_tester():
    return render_template("trade_tester.html")
#-----------------------------------------------
<!-- COMPACT TRADE POPUP - Essential info only -->
<!-- This is the NEW minimal popup - replace the /trade-popup-fixed route with this -->

@app.route('/trade-popup-fixed')
def trade_popup_fixed():
    """Compact trade popup - essential info only"""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trade Monitor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @keyframes pulse-profit {
            0%, 100% { background-color: rgba(16, 185, 129, 0.3); }
            50% { background-color: rgba(16, 185, 129, 0.5); }
        }
        @keyframes pulse-loss {
            0%, 100% { background-color: rgba(239, 68, 68, 0.3); }
            50% { background-color: rgba(239, 68, 68, 0.5); }
        }
        .profit-bg { animation: pulse-profit 2s infinite; }
        .loss-bg { animation: pulse-loss 2s infinite; }
        body.profit-mode { background: linear-gradient(135deg, #065f46 0%, #064e3b 100%); }
        body.loss-mode { background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%); }
    </style>
</head>
<body class="bg-gray-900 text-white p-4">
    <div class="max-w-md mx-auto">

        <!-- Symbol & Broker Header -->
        <div class="bg-gray-800 rounded-lg p-4 mb-3 text-center">
            <div class="text-3xl font-bold mb-1" id="symbol-display">--</div>
            <div class="text-sm text-gray-400" id="broker-display">Broker: --</div>
            <div class="text-lg font-semibold mt-2" id="direction-display">
                <span class="px-3 py-1 rounded">--</span>
            </div>
        </div>

        <!-- P&L Display -->
        <div class="bg-gray-800 rounded-lg p-6 mb-3 text-center" id="pnl-container">
            <div class="text-sm text-gray-400 mb-2">Profit & Loss</div>
            <div class="text-6xl font-bold mb-2" id="pnl-display">0.00%</div>
            <div class="text-xl text-gray-300" id="pnl-dollars">$0.00</div>
            <div class="text-xs text-gray-500 mt-2" id="entry-price-display">Entry: $0.00</div>
        </div>

        <!-- Action Buttons -->
        <div id="active-buttons" class="space-y-2">
            <button onclick="panicExit()"
                    class="w-full bg-red-600 hover:bg-red-700 text-white font-bold py-4 px-6 rounded-lg text-xl transition-all shadow-lg">
                🚨 PANIC EXIT
            </button>
            <button onclick="normalExit()"
                    class="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg transition-all">
                ✓ Close Position
            </button>
        </div>

        <!-- After Exit (Hidden initially) -->
        <div id="closed-buttons" class="hidden space-y-2">
            <div class="bg-gray-700 rounded-lg p-4 text-center mb-3">
                <div class="text-sm text-gray-400">Trade Closed</div>
                <div class="text-2xl font-bold" id="final-pnl">--</div>
            </div>
            <button onclick="openFullDetails()"
                    class="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-lg transition-all">
                📊 View Full Details
            </button>
            <button onclick="window.close()"
                    class="w-full bg-gray-700 hover:bg-gray-600 text-white py-2 px-6 rounded-lg transition-all">
                Close Window
            </button>
        </div>

    </div>

    <script>
        // Get trade data from URL
        const urlParams = new URLSearchParams(window.location.search);
        const tradeData = {
            symbol: urlParams.get('symbol') || 'UNKNOWN',
            side: urlParams.get('side') || 'BUY',
            qty: parseFloat(urlParams.get('qty')) || 1,
            exchange: urlParams.get('exchange') || 'UNKNOWN',
            entryPrice: parseFloat(urlParams.get('price')) || 0,
            rsi: urlParams.get('rsi') || '50',
            signal: urlParams.get('signal') || 'NEUTRAL'
        };

        let currentPrice = tradeData.entryPrice;
        let isTradeActive = true;
        let priceInterval = null;

        // Initialize display
        function initDisplay() {
            // Symbol and broker
            document.getElementById('symbol-display').textContent = tradeData.symbol;
            document.getElementById('broker-display').textContent = `Broker: ${tradeData.exchange}`;

            // Direction
            const directionEl = document.getElementById('direction-display');
            const directionSpan = directionEl.querySelector('span');
            directionSpan.textContent = tradeData.side;
            if (tradeData.side === 'BUY') {
                directionSpan.classList.add('bg-green-600', 'text-white');
            } else {
                directionSpan.classList.add('bg-red-600', 'text-white');
            }

            // Entry price
            document.getElementById('entry-price-display').textContent = `Entry: $${tradeData.entryPrice.toFixed(2)}`;

            // Start price simulation
            simulatePrice();
        }

        // Simulate live price
        function simulatePrice() {
            priceInterval = setInterval(() => {
                if (!isTradeActive) return;

                // Simulate price movement (±0.3%)
                const change = (Math.random() - 0.5) * 0.006;
                currentPrice = currentPrice * (1 + change);

                updatePnL();
            }, 1000);
        }

        // Update P&L display
        function updatePnL() {
            // Calculate P&L
            let pnlPercent, pnlDollar;

            if (tradeData.side === 'BUY') {
                pnlPercent = ((currentPrice - tradeData.entryPrice) / tradeData.entryPrice) * 100;
                pnlDollar = (currentPrice - tradeData.entryPrice) * tradeData.qty;
            } else { // SELL
                pnlPercent = ((tradeData.entryPrice - currentPrice) / tradeData.entryPrice) * 100;
                pnlDollar = (tradeData.entryPrice - currentPrice) * tradeData.qty;
            }

            // Update display
            const pnlEl = document.getElementById('pnl-display');
            const dollarsEl = document.getElementById('pnl-dollars');
            const container = document.getElementById('pnl-container');
            const body = document.body;

            pnlEl.textContent = `${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%`;
            dollarsEl.textContent = `${pnlDollar >= 0 ? '+' : ''}$${Math.abs(pnlDollar).toFixed(2)}`;

            // Color coding
            body.classList.remove('profit-mode', 'loss-mode');
            container.classList.remove('profit-bg', 'loss-bg');

            if (pnlPercent > 0) {
                pnlEl.className = 'text-6xl font-bold mb-2 text-green-400';
                dollarsEl.className = 'text-xl text-green-300';
                if (pnlPercent > 1) {
                    container.classList.add('profit-bg');
                    body.classList.add('profit-mode');
                }
            } else if (pnlPercent < 0) {
                pnlEl.className = 'text-6xl font-bold mb-2 text-red-400';
                dollarsEl.className = 'text-xl text-red-300';
                if (pnlPercent < -1) {
                    container.classList.add('loss-bg');
                    body.classList.add('loss-mode');
                }
            } else {
                pnlEl.className = 'text-6xl font-bold mb-2 text-gray-300';
                dollarsEl.className = 'text-xl text-gray-400';
            }
        }

        // Panic exit
        function panicExit() {
            if (!isTradeActive) return;

            if (confirm('PANIC EXIT - Close position immediately?')) {
                closeTrade('Panic Exit');
            }
        }

        // Normal exit
        function normalExit() {
            if (!isTradeActive) return;

            const pnlPercent = calculateCurrentPnL();
            if (confirm(`Close position?\\nCurrent P&L: ${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%`)) {
                closeTrade('Normal Exit');
            }
        }

        // Calculate current P&L
        function calculateCurrentPnL() {
            if (tradeData.side === 'BUY') {
                return ((currentPrice - tradeData.entryPrice) / tradeData.entryPrice) * 100;
            } else {
                return ((tradeData.entryPrice - currentPrice) / tradeData.entryPrice) * 100;
            }
        }

        // Close trade
        function closeTrade(reason) {
            isTradeActive = false;
            clearInterval(priceInterval);

            const finalPnL = calculateCurrentPnL();

            // Freeze P&L display
            document.getElementById('final-pnl').textContent = `Final P&L: ${finalPnL >= 0 ? '+' : ''}${finalPnL.toFixed(2)}%`;
            document.getElementById('final-pnl').className = `text-2xl font-bold ${finalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`;

            // Switch buttons
            document.getElementById('active-buttons').classList.add('hidden');
            document.getElementById('closed-buttons').classList.remove('hidden');

            // Notify parent window
            notifyParent(finalPnL, reason);
        }

        // Notify parent scanner
        function notifyParent(pnl, reason) {
            if (window.opener) {
                window.opener.postMessage({
                    type: 'TRADE_CLOSED',
                    exchange: tradeData.exchange,
                    symbol: tradeData.symbol,
                    pnl: pnl.toFixed(2),
                    reason: reason
                }, '*');
            }
        }

        // Open full details (placeholder for now)
        function openFullDetails() {
            alert('Full details view will be implemented next!\\n\\nThis will show:\\n- Price chart\\n- Trade details\\n- Full statistics');
        }

        // Initialize
        initDisplay();
    </script>
</body>
</html>'''
#-------------------------------------------------------------
@app.route("/symbols", endpoint="symbols")
def symbols():
    return render_template("symbols.html")

@app.route("/simple-explanation", endpoint="simple_explanation")
def simple_explanation():
    return render_template("Simple_Explanation.html")

@app.route("/architectural-analysis", endpoint="architectural_analysis")
def architectural_analysis():
    return render_template("Architectural Analysis and Trading Philosophy.html")

@app.route("/scanner-simulator", endpoint="scanner_simulator")
def scanner_simulator():
    return render_template("scanner-simulator.html")

@app.route("/scanner_analysis", endpoint="scanner_analysis")
def scanner_analysis():
    return render_template("aimn_diagnostic_scanner.html")

# ============================================================================
# ORDERS VIEW  (MySQL trades table)
# ============================================================================
@app.route("/orders")
def orders():
    from_id = request.args.get("from_id", type=int)

    conn = get_db()
    with conn.cursor() as cur:
        if from_id:
            cur.execute(
                "SELECT * FROM trades WHERE id >= %s ORDER BY id DESC LIMIT 200",
                (from_id,),
            )
        else:
            cur.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 200")
        rows = cur.fetchall()
    conn.close()

    def format_duration(sec):
        try:
            sec = int(sec)
        except Exception:
            return ""
        m, s = divmod(sec, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    enriched = []
    total_pnl_percent = 0.0
    total_pnl_money = 0.0

    by_broker = {}
    by_symbol = {}
    by_side   = {}

    def agg(bucket, key, pnl_percent, pnl_money, duration_s):
        if key is None:
            key = "-"
        if key not in bucket:
            bucket[key] = {
                "count": 0,
                "pnl_percent": 0.0,
                "pnl_money": 0.0,
                "duration_total": 0,
                "duration_count": 0,
            }
        bucket[key]["count"] += 1
        if isinstance(pnl_percent, (int, float)):
            bucket[key]["pnl_percent"] += pnl_percent
        if isinstance(pnl_money, (int, float)):
            bucket[key]["pnl_money"] += pnl_money
        if duration_s is not None:
            try:
                ds = int(duration_s)
                bucket[key]["duration_total"] += ds
                bucket[key]["duration_count"] += 1
            except Exception:
                pass

    for r in rows:
        meta = r.get("meta")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        elif meta is None:
            meta = {}
        r["meta_obj"] = meta

        broker      = meta.get("broker") or meta.get("exchange") or "-"
        exit_reason = meta.get("exit_reason", "")
        pnl_percent = meta.get("pnl_percent")
        pnl_money   = meta.get("pnl_money")
        duration_s  = meta.get("duration_seconds")
        exit_ts     = meta.get("exit_ts")

        r["broker"]      = broker
        r["exit_reason"] = exit_reason
        r["pnl_percent"] = pnl_percent
        r["pnl_money"]   = pnl_money

        # Duration as mm:ss or hh:mm:ss
        if duration_s is not None:
            try:
                r["duration_str"] = format_duration(duration_s)
            except Exception:
                r["duration_str"] = ""
        else:
            r["duration_str"] = ""

        # Which timestamp to show: exit_ts (if we stored), else DB ts
        r["display_ts"] = exit_ts or r.get("ts")

        # Pretty display_ts string
        dt_val = None
        raw_ts = r["display_ts"]
        if isinstance(raw_ts, str):
            try:
                dt_val = datetime.fromisoformat(raw_ts)
            except Exception:
                dt_val = None
        else:
            dt_val = raw_ts

        if dt_val:
            r["display_ts_str"] = dt_val.strftime("%Y-%m-%d %H:%M:%S")
        else:
            r["display_ts_str"] = raw_ts or ""

        # Totals
        if isinstance(pnl_percent, (int, float)):
            total_pnl_percent += pnl_percent
        if isinstance(pnl_money, (int, float)):
            total_pnl_money += pnl_money

        # Aggregations
        symbol = r.get("symbol")
        side   = (r.get("side") or "").upper()

        agg(by_broker, broker, pnl_percent, pnl_money, duration_s)
        if symbol:
            agg(by_symbol, symbol, pnl_percent, pnl_money, duration_s)
        if side:
            agg(by_side, side, pnl_percent, pnl_money, duration_s)

        enriched.append(r)

    # Compute average duration strings for each summary bucket
    for bucket in (by_broker, by_symbol, by_side):
        for key, s in bucket.items():
            if s["duration_count"] > 0:
                avg_sec = s["duration_total"] // s["duration_count"]
                s["avg_duration_str"] = format_duration(avg_sec)
            else:
                s["avg_duration_str"] = "-"

    return render_template(
        "orders.html",
        trades=enriched,
        total_pnl_percent=total_pnl_percent,
        total_pnl_money=total_pnl_money,
        trade_count=len(enriched),
        by_broker=by_broker,
        by_symbol=by_symbol,
        by_side=by_side,
        from_id=from_id,
    )




@app.route("/beginner-guide", endpoint="beginner_guide")
def beginner_guide():
    return render_template("trading_philosophy.html")

@app.route("/diagnostics", endpoint="diagnostics")
def diagnostics():
    return render_template("functional_scanner_diagnostics.html")

@app.route("/aiml", endpoint="aiml_home")
def aiml_home():
    return render_template("aiml/home.html")

@app.route("/aiml/manual-tune", methods=["GET", "POST"], endpoint="manual_tune")
def manual_tune():
    if request.method == "POST":
        # For now, just return fake results. We'll add real logic later!
        results = {
            "pnl_pct": 12.3,
            "n_trades": 10,
            "n_wins": 6,
            "n_losses": 4,
            "win_rate": 60.0,
            "n_buy_orders": 5,
            "n_sell_orders": 5,
            "avg_trade_pct": 1.1,
            "max_drawdown": -5.0,
            "trades": [
                {"entry_price": 100, "exit_price": 105, "profit_pct": 5.0, "direction": "BUY", "exit_reason": "TP"},
                # More fake trades if you want...
            ],
            # You must also pass symbols and brokers for the dropdowns:
            "symbols": ["BTCUSD", "ETHUSD"],
            "brokers": ["BrokerA", "BrokerB"],
        }
        return render_template("aiml/manual_tune.html", **results)

    # GET request: show the form with empty results
    ctx = {
        "pnl_pct": None,
        "n_trades": None,
        "n_wins": None,
        "n_losses": None,
        "win_rate": None,
        "n_buy_orders": None,
        "n_sell_orders": None,
        "avg_trade_pct": None,
        "max_drawdown": None,
        "trades": [],
        "symbols": ["BTCUSD", "ETHUSD"],
        "brokers": ["BrokerA", "BrokerB"],
    }
    return render_template("aiml/manual_tune.html", **ctx)

@app.route("/api/trade/close", methods=["POST"])
def api_trade_close():
    data = request.get_json(force=True) or {}

    symbol         = data.get("symbol")
    exchange       = data.get("exchange")
    side           = data.get("side")
    qty            = data.get("qty", 0)
    entry_price    = data.get("entry_price", 0)
    exit_price     = data.get("exit_price", 0)
    pnl_percent    = data.get("pnl_percent", 0)
    reason         = data.get("reason", "")
    duration_sec   = data.get("duration_seconds")
    entry_ts       = data.get("entry_ts")
    exit_ts        = data.get("exit_ts")

    conn = get_db()
    try:
        record_trade(
            conn,
            symbol=symbol,
            side=side,
            qty=qty,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_percent=pnl_percent,
            reason=reason,
            broker=exchange,
            duration_seconds=duration_sec,
            entry_ts=entry_ts,
            exit_ts=exit_ts,
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()




@app.post("/aiml/run-backtest", endpoint="aiml_run_backtest")
def aiml_run_backtest():
    # read form inputs (add whichever your page has)
    # e.g. p21 = float(request.form.get("p21", 2.0))
    # ... run your backtest here ...
    # minimal fake result so page always renders:
    ctx = dict(
        pnl_pct=1.23,
        avg_trade_pct=0.18,
        win_rate=54.0,
    )
    return render_template("aiml/manual_tune.html", **ctx)




# ============================================================================
# DATABASE & TRADE SESSION MANAGEMENT
# ============================================================================

DB_PATH = os.path.join(os.path.dirname(__file__), "popup.sqlite3")
SHARED_API_KEY = os.environ.get("SHARED_API_KEY", "dev-key-12345")

def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn

def _migrate_sqlite():
    with _conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS trade_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant TEXT,
            user_id TEXT,
            signal_id INTEGER,
            symbol TEXT,
            exchange TEXT,
            side TEXT,
            qty REAL,
            entry_price REAL,
            params_json TEXT,
            status TEXT,
            created_at INTEGER,
            opened_at INTEGER,
            closed_at INTEGER,
            exit_price REAL,
            exit_value REAL,
            pnl_pct REAL,
            pnl_amount REAL,
            reason TEXT,
            snapshot_path TEXT
        )
        """)

        def add_col(name, sql_type):
            existing = [r["name"] for r in c.execute("PRAGMA table_info(trade_sessions)")]
            if name not in existing:
                c.execute(f"ALTER TABLE trade_sessions ADD COLUMN {name} {sql_type}")

        for nm, tp in [
            ("tenant","TEXT"), ("user_id","TEXT"), ("signal_id","INTEGER"),
            ("status","TEXT"), ("opened_at","INTEGER"), ("closed_at","INTEGER"),
            ("exit_price","REAL"), ("exit_value","REAL"), ("pnl_pct","REAL"),
            ("pnl_amount","REAL"), ("reason","TEXT"), ("snapshot_path","TEXT")
        ]:
            add_col(nm, tp)

        c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_signal ON trade_sessions(signal_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON trade_sessions(user_id)")

_migrate_sqlite()

def _require_bearer():
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer "):
        return False
    token = auth.split(" ",1)[1].strip()
    return token and token == SHARED_API_KEY

def _now_ms():
    return int(time.time()*1000)

@app.route("/healthz", endpoint="healthz")
def healthz():
    return {"ok": True}

@app.post("/api/trade_sessions")
def api_trade_sessions_create():
    if not _require_bearer():
        return jsonify(ok=False, error="Unauthorized"), 401

    user_id = request.headers.get("X-User-Id") or "default_user"
    tenant = request.headers.get("X-Tenant") or "public"
    idem_key = request.headers.get("Idempotency-Key")

    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify(ok=False, error="Invalid JSON"), 400

    for k in ("symbol","exchange","side","qty","entry_price"):
        if k not in data:
            return jsonify(ok=False, error=f"Missing required field: {k}"), 400

    symbol       = str(data["symbol"]).upper()
    exchange     = str(data["exchange"])
    side         = str(data["side"]).upper()
    qty          = float(data["qty"])
    entry_price  = float(data["entry_price"])
    signal_id    = int(data.get("signal_id") or 0) or None
    params       = data.get("params") or {}
    params_json  = json.dumps(params, separators=(",",":"))

    with _conn() as c:
        if idem_key and signal_id:
            row = c.execute("""
              SELECT id FROM trade_sessions
              WHERE signal_id = ? AND user_id = ? AND symbol = ? AND side = ? AND status IS NOT 'CANCELLED'
              ORDER BY id ASC LIMIT 1
            """, (signal_id, user_id, symbol, side)).fetchone()
            if row:
                sid = row["id"]
                popup_url = f"/trade-popup-fixed?symbol={symbol}&exchange={exchange}&side={side}&qty={qty}&sid={sid}&entry={entry_price}"
                return jsonify(ok=True, sid=sid, user_id=user_id, popup_url=popup_url), 200

        c.execute("""
          INSERT INTO trade_sessions
          (tenant,user_id,signal_id,symbol,exchange,side,qty,entry_price,params_json,status,created_at,opened_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (tenant, user_id, signal_id, symbol, exchange, side, qty, entry_price, params_json, "OPEN", _now_ms(), _now_ms()))
        sid = c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    popup_url = f"/trade-popup-fixed?symbol={symbol}&exchange={exchange}&side={side}&qty={qty}&sid={sid}&entry={entry_price}"
    return jsonify(ok=True, sid=sid, user_id=user_id, popup_url=popup_url), 200

@app.post("/api/trade-completed")
def api_trade_completed():
    if not _require_bearer():
        return jsonify(status="error", error="Unauthorized"), 401

    try:
        body = request.get_json(force=True) or {}
    except Exception:
        return jsonify(status="error", error="Invalid JSON"), 400

    required = ("session_id","symbol","side","exit_reason","exit_price")
    for k in required:
        if k not in body:
            return jsonify(status="error", error=f"Missing field: {k}"), 400

    sid          = int(body["session_id"])
    exit_reason  = str(body["exit_reason"]).upper()
    exit_price   = float(body["exit_price"])
    pnl_pct      = float(body.get("pnl_percentage") or 0.0)
    exit_value   = body.get("exit_value")
    ts_iso       = body.get("timestamp")
    snapshot     = body.get("snapshot_url")

    closed_at_ms = _now_ms()
    with _conn() as c:
        row = c.execute("SELECT qty, entry_price FROM trade_sessions WHERE id = ?", (sid,)).fetchone()
        pnl_amount = None
        if row:
            qty = float(row["qty"])
            entry = float(row["entry_price"])
            pnl_amount = (exit_price - entry) * qty if body.get("side","BUY").upper()=="BUY" else (entry - exit_price) * qty

        c.execute("""
           UPDATE trade_sessions
              SET status='DONE',
                  closed_at=?,
                  exit_price=?,
                  exit_value=?,
                  pnl_pct=?,
                  pnl_amount=?,
                  reason=?,
                  snapshot_path=COALESCE(?, snapshot_path)
            WHERE id=?
        """, (closed_at_ms, exit_price, exit_value, pnl_pct, pnl_amount, exit_reason, snapshot, sid))

    return jsonify(status="success",
                   message="Trade recorded; exchange resume handled by scanner"), 200

if __name__ == "__main__":
    app.run("0.0.0.0", int(os.environ.get("PORT", "5000")), debug=True)
