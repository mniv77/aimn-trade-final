# app.py - FIXED VERSION (Removed duplicates and fixed routing)
import os
from flask import Flask, render_template, jsonify, request
import random
from app_sub.views import main_bp
from AImnMLResearch.aiml_dashboard import aiml_bp

# Explicitly set template folder
template_dir = os.path.abspath('templates')
app = Flask(__name__, template_folder=template_dir)

# Register blueprints
app.register_blueprint(main_bp, url_prefix='/main')
app.register_blueprint(aiml_bp, url_prefix='/aiml')

for rule in app.url_map.iter_rules():
    print("ROUTE:", rule, rule.endpoint)


# ============================================================================
# SCANNER API ROUTES
# ============================================================================

@app.route('/api/flowing-scanner-data')
def flowing_scanner_data():
    """Returns scanner data"""
    symbols = [
        {'symbol': 'BTC/USD', 'exchange': 'CRYPTO'},
        {'symbol': 'ETH/USD', 'exchange': 'CRYPTO'},
        {'symbol': 'AAPL', 'exchange': 'ALPACA'},
        {'symbol': 'TSLA', 'exchange': 'ALPACA'},
        {'symbol': 'NVDA', 'exchange': 'ALPACA'},
        {'symbol': 'SPY', 'exchange': 'NYSE'},
        {'symbol': 'QQQ', 'exchange': 'NYSE'},
        {'symbol': 'MSFT', 'exchange': 'NYSE'},
        {'symbol': 'AMZN', 'exchange': 'NYSE'},
        {'symbol': 'GOOGL', 'exchange': 'ALPACA'}
    ]

    scan_results = []
    for symbol_data in symbols:
        price = round(random.uniform(50, 550), 2)
        change = round(random.uniform(-10, 10), 2)
        volume = random.randint(100000, 1000000)
        rsi = round(random.uniform(0, 100), 1)

        # Determine signal
        if rsi < 30:
            signal = 'BUY'
        elif rsi > 70:
            signal = 'SELL'
        else:
            signal = 'NEUTRAL'

        scan_results.append({
            'symbol': symbol_data['symbol'],
            'exchange': symbol_data['exchange'],
            'price': str(price),
            'change': str(change),
            'volume': f"{volume:,}",
            'rsi': str(rsi),
            'signal': signal,
            'signalStrength': str(round(random.uniform(0.5, 1.0), 2)) if signal != 'NEUTRAL' else '0',
            'isAvailable': True,
            'isActivelyTrading': False,
            'quantity': 0.01 if symbol_data['exchange'] == 'CRYPTO' else 10
        })

    return jsonify({'scanResults': scan_results})


@app.route('/api/exchange-status')
def exchange_status():
    """Returns exchange status"""
    return jsonify({
        'ALPACA': {'scanning': True, 'activeSymbol': None, 'symbolCount': 250, 'status': 'ACTIVE'},
        'CRYPTO': {'scanning': True, 'activeSymbol': None, 'symbolCount': 100, 'status': 'ACTIVE'},
        'FOREX': {'scanning': True, 'activeSymbol': None, 'symbolCount': 50, 'status': 'ACTIVE'},
        'NYSE': {'scanning': True, 'activeSymbol': None, 'symbolCount': 200, 'status': 'ACTIVE'},
        'FUTURES': {'scanning': True, 'activeSymbol': None, 'symbolCount': 30, 'status': 'ACTIVE'}
    })


@app.route('/api/create-signal', methods=['POST'])
def create_signal():
    """Called by scanner when signal detected"""
    try:
        data = request.json
        print(f"🎯 Signal created: {data['symbol']} {data.get('direction', 'BUY')}")
        return jsonify({'success': True, 'message': 'Signal created'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trade-completed', methods=['POST'])
def trade_completed():
    """Called when trade completes"""
    try:
        data = request.json
        print(f"✅ Trade completed: {data.get('symbol', 'Unknown')}")
        return jsonify({'success': True, 'message': 'Scanner resumed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ticker-feed')
def ticker_feed():
    symbols = [
        {'symbol': 'BTC/USD', 'exchange': 'CRYPTO'},
        {'symbol': 'ETH/USD', 'exchange': 'CRYPTO'},
        {'symbol': 'AAPL', 'exchange': 'ALPACA'},
        {'symbol': 'TSLA', 'exchange': 'ALPACA'},
        {'symbol': 'NVDA', 'exchange': 'ALPACA'},
        {'symbol': 'SPY', 'exchange': 'NYSE'},
        {'symbol': 'QQQ', 'exchange': 'NYSE'},
        {'symbol': 'MSFT', 'exchange': 'NYSE'},
        {'symbol': 'AMZN', 'exchange': 'NYSE'},
        {'symbol': 'GOOGL', 'exchange': 'ALPACA'}
    ]

    ticker_items = []
    for symbol_data in symbols:
        ticker_items.append({
            'symbol': symbol_data['symbol'],
            'exchange': symbol_data['exchange'],
            'price': str(round(random.uniform(50, 550), 2)),
            'change': str(round(random.uniform(-10, 10), 2)),
            'signal': random.choice(['BUY', 'SELL', 'NEUTRAL', 'NEUTRAL', 'NEUTRAL']),
            'isAvailable': True,
            'isActivelyTrading': False
        })

    return jsonify(ticker_items)


@app.route('/api/scanner/create-signal', methods=['POST'])
def create_scanner_signal():
    data = request.json
    return jsonify({'ok': True, 'signal_data': data})


@app.route('/api/live_price')
def get_live_price():
    symbol = request.args.get('symbol')
    exchange = request.args.get('exchange')

    if exchange == 'CRYPTO':
        import requests
        try:
            clean_symbol = symbol.replace('/', '') + 'T'
            url = f'https://api.binance.com/api/v3/ticker/price?symbol={clean_symbol}'
            response = requests.get(url, timeout=5)
            price = float(response.json()['price'])
        except Exception as e:
            print(f"Crypto price error: {e}")
            price = 108000
    else:
        price = 175.50

    return jsonify({'price': price})


# ============================================================================
# PAGE ROUTES
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scanner')
def scanner():
    return render_template('aimn_flowing_scanner_auto.html')

# SIMPLE INLINE VERSION - Replace your trade-popup-fixed route with this:

@app.route('/trade-popup-fixed')
def trade_popup_fixed():
    """Trade popup window - inline HTML version"""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trade Monitor - AIMn Trading</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @keyframes pulse-green {
            0%, 100% { background-color: rgba(16, 185, 129, 0.2); }
            50% { background-color: rgba(16, 185, 129, 0.4); }
        }
        @keyframes pulse-red {
            0%, 100% { background-color: rgba(239, 68, 68, 0.2); }
            50% { background-color: rgba(239, 68, 68, 0.4); }
        }
        .profit-pulse { animation: pulse-green 2s infinite; }
        .loss-pulse { animation: pulse-red 2s infinite; }
    </style>
</head>
<body class="bg-gray-900 text-white p-4">
    <div class="max-w-4xl mx-auto">
        <!-- Header -->
        <div class="bg-gray-800 rounded-lg p-4 mb-4">
            <div class="flex justify-between items-center">
                <div>
                    <h1 class="text-2xl font-bold" id="symbol-display">Loading...</h1>
                    <p class="text-gray-400 text-sm" id="exchange-display">Exchange: --</p>
                </div>
                <div class="text-right">
                    <div class="text-sm text-gray-400">Signal</div>
                    <div class="text-xl font-bold" id="signal-display">--</div>
                </div>
            </div>
        </div>

        <!-- Price & P&L Display -->
        <div class="bg-gray-800 rounded-lg p-6 mb-4">
            <div class="grid grid-cols-2 gap-4 mb-4">
                <div>
                    <div class="text-sm text-gray-400 mb-1">Entry Price</div>
                    <div class="text-2xl font-bold" id="entry-price">$0.00</div>
                </div>
                <div>
                    <div class="text-sm text-gray-400 mb-1">Current Price</div>
                    <div class="text-2xl font-bold" id="current-price">$0.00</div>
                </div>
            </div>

            <div class="border-t border-gray-700 pt-4">
                <div class="text-center">
                    <div class="text-sm text-gray-400 mb-2">Profit & Loss</div>
                    <div class="text-5xl font-bold mb-2" id="pnl-display">$0.00</div>
                    <div class="text-2xl" id="pnl-percent">(0.00%)</div>
                </div>
            </div>
        </div>

        <!-- Trade Details -->
        <div class="bg-gray-800 rounded-lg p-4 mb-4">
            <h2 class="text-lg font-semibold mb-3">Trade Details</h2>
            <div class="grid grid-cols-2 gap-3 text-sm">
                <div>
                    <span class="text-gray-400">Quantity:</span>
                    <span class="float-right font-semibold" id="quantity-display">--</span>
                </div>
                <div>
                    <span class="text-gray-400">Side:</span>
                    <span class="float-right font-semibold" id="side-display">--</span>
                </div>
                <div>
                    <span class="text-gray-400">RSI:</span>
                    <span class="float-right font-semibold" id="rsi-display">--</span>
                </div>
                <div>
                    <span class="text-gray-400">Change:</span>
                    <span class="float-right font-semibold" id="change-display">--</span>
                </div>
            </div>
            <div class="mt-3 pt-3 border-t border-gray-700">
                <div class="text-gray-400 text-xs mb-1">Reason:</div>
                <div class="text-sm" id="reason-display">--</div>
            </div>
        </div>

        <!-- Price Chart -->
        <div class="bg-gray-800 rounded-lg p-4 mb-4">
            <h2 class="text-lg font-semibold mb-3">Price Movement</h2>
            <canvas id="priceChart" height="200"></canvas>
        </div>

        <!-- Action Buttons -->
        <div class="bg-gray-800 rounded-lg p-4">
            <div class="grid grid-cols-2 gap-4">
                <button onclick="closeTradeWin()" 
                        class="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg transition-all">
                    ✓ Close Winner
                </button>
                <button onclick="closeTradeLoss()" 
                        class="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 rounded-lg transition-all">
                    ✗ Close Loss
                </button>
            </div>
            <button onclick="window.close()" 
                    class="w-full mt-3 bg-gray-700 hover:bg-gray-600 text-white py-2 px-6 rounded-lg transition-all">
                Cancel / Keep Monitoring
            </button>
        </div>
    </div>

    <script>
        // Get URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const tradeData = {
            symbol: urlParams.get('symbol') || 'UNKNOWN',
            side: urlParams.get('side') || 'BUY',
            qty: parseFloat(urlParams.get('qty')) || 1,
            exchange: urlParams.get('exchange') || 'UNKNOWN',
            entryPrice: parseFloat(urlParams.get('price')) || 0,
            change: urlParams.get('change') || '0',
            rsi: urlParams.get('rsi') || '50',
            signal: urlParams.get('signal') || 'NEUTRAL',
            reason: urlParams.get('reason') || 'No reason provided'
        };

        let currentPrice = tradeData.entryPrice;
        let priceHistory = [tradeData.entryPrice];
        let chart = null;

        // Initialize display
        function initDisplay() {
            document.getElementById('symbol-display').textContent = tradeData.symbol;
            document.getElementById('exchange-display').textContent = `Exchange: ${tradeData.exchange}`;
            document.getElementById('signal-display').textContent = tradeData.signal;
            document.getElementById('entry-price').textContent = `$${tradeData.entryPrice.toFixed(2)}`;
            document.getElementById('quantity-display').textContent = tradeData.qty;
            document.getElementById('side-display').textContent = tradeData.side;
            document.getElementById('rsi-display').textContent = tradeData.rsi;
            document.getElementById('change-display').textContent = tradeData.change;
            document.getElementById('reason-display').textContent = tradeData.reason;

            // Color code the signal
            const signalEl = document.getElementById('signal-display');
            if (tradeData.signal === 'BUY') {
                signalEl.classList.add('text-green-400');
            } else if (tradeData.signal === 'SELL') {
                signalEl.classList.add('text-red-400');
            }

            initChart();
            simulatePriceMovement();
        }

        // Initialize price chart
        function initChart() {
            const ctx = document.getElementById('priceChart').getContext('2d');
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['Entry'],
                    datasets: [{
                        label: 'Price',
                        data: [tradeData.entryPrice],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            grid: { color: '#374151' },
                            ticks: { color: '#9ca3af' }
                        },
                        x: {
                            grid: { color: '#374151' },
                            ticks: { color: '#9ca3af' }
                        }
                    }
                }
            });
        }

        // Simulate price movement
        function simulatePriceMovement() {
            setInterval(() => {
                // Simulate price change (±0.5%)
                const changePercent = (Math.random() - 0.5) * 0.01;
                currentPrice = currentPrice * (1 + changePercent);
                
                priceHistory.push(currentPrice);
                if (priceHistory.length > 30) {
                    priceHistory.shift();
                }

                updateDisplay();
                updateChart();
            }, 2000);
        }

        // Update display with current prices and P&L
        function updateDisplay() {
            document.getElementById('current-price').textContent = `$${currentPrice.toFixed(2)}`;

            // Calculate P&L
            let pnlDollar, pnlPercent;
            if (tradeData.side === 'BUY') {
                pnlDollar = (currentPrice - tradeData.entryPrice) * tradeData.qty;
                pnlPercent = ((currentPrice - tradeData.entryPrice) / tradeData.entryPrice) * 100;
            } else { // SELL
                pnlDollar = (tradeData.entryPrice - currentPrice) * tradeData.qty;
                pnlPercent = ((tradeData.entryPrice - currentPrice) / tradeData.entryPrice) * 100;
            }

            const pnlEl = document.getElementById('pnl-display');
            const pnlPercentEl = document.getElementById('pnl-percent');
            const bodyEl = document.body;

            pnlEl.textContent = `$${pnlDollar.toFixed(2)}`;
            pnlPercentEl.textContent = `(${pnlPercent > 0 ? '+' : ''}${pnlPercent.toFixed(2)}%)`;

            // Color code P&L
            bodyEl.classList.remove('profit-pulse', 'loss-pulse');
            if (pnlDollar > 0) {
                pnlEl.classList.remove('text-red-400');
                pnlEl.classList.add('text-green-400');
                pnlPercentEl.classList.remove('text-red-400');
                pnlPercentEl.classList.add('text-green-400');
                if (pnlPercent > 1) bodyEl.classList.add('profit-pulse');
            } else if (pnlDollar < 0) {
                pnlEl.classList.remove('text-green-400');
                pnlEl.classList.add('text-red-400');
                pnlPercentEl.classList.remove('text-green-400');
                pnlPercentEl.classList.add('text-red-400');
                if (pnlPercent < -1) bodyEl.classList.add('loss-pulse');
            } else {
                pnlEl.classList.remove('text-green-400', 'text-red-400');
                pnlPercentEl.classList.remove('text-green-400', 'text-red-400');
            }
        }

        // Update chart with new price
        function updateChart() {
            chart.data.labels = priceHistory.map((_, i) => i === 0 ? 'Entry' : `+${i * 2}s`);
            chart.data.datasets[0].data = priceHistory;
            chart.update('none'); // Update without animation for smooth real-time feel
        }

        // Close trade as winner
        function closeTradeWin() {
            const pnlPercent = tradeData.side === 'BUY' 
                ? ((currentPrice - tradeData.entryPrice) / tradeData.entryPrice) * 100
                : ((tradeData.entryPrice - currentPrice) / tradeData.entryPrice) * 100;

            if (confirm(`Close this trade?\\nP&L: ${pnlPercent > 0 ? '+' : ''}${pnlPercent.toFixed(2)}%`)) {
                notifyParent(pnlPercent, 'Manual close - Win');
                window.close();
            }
        }

        // Close trade as loss
        function closeTradeLoss() {
            const pnlPercent = tradeData.side === 'BUY' 
                ? ((currentPrice - tradeData.entryPrice) / tradeData.entryPrice) * 100
                : ((tradeData.entryPrice - currentPrice) / tradeData.entryPrice) * 100;

            if (confirm(`Exit this position at a loss?\\nP&L: ${pnlPercent > 0 ? '+' : ''}${pnlPercent.toFixed(2)}%`)) {
                notifyParent(pnlPercent, 'Manual close - Loss');
                window.close();
            }
        }

        // Notify parent window
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

        // Initialize on load
        initDisplay();
    </script>
</body>
</html>'''


@app.route('/trade-popup')
def trade_popup():
    return render_template('aimn_trade_popup.html')

@app.route('/trade-popup-v2')
def trade_popup_v2():
    return render_template('aimn_trade_popup.html')

@app.route('/tuning')
def tuning_parameters():
    return render_template('tuning.html')

@app.route('/symbols')
def symbols():
    return render_template('symbol_api_manager.html')

@app.route('/scanner-simulator')
def scanner_simulator():
    return render_template('aimn_scanner_debug.html')

@app.route('/scanner/debug')
def scanner_debug():
    return render_template('aimn_scanner_debug.html')

@app.route('/scanner/diagnostics')
def scanner_diagnostics():
    return render_template('functional_scanner_diagnostics.html')

@app.route('/trade-tester')
def trade_tester():
    return render_template('trade_tester.html')

@app.route('/simple-explanation')
def simple_explanation():
    return render_template('doc/Simple Explanation.html')

@app.route('/architectural-analysis')
def architectural_analysis():
    return render_template('doc/Architectural Analysis and Trading Philosophy.html')

@app.route('/scanner-analysis')
def scanner_analysis():
    return render_template('doc/AIMn Multi-Professor_Scanner_Analysis.html')

@app.route('/beginner-guide')
def beginner_guide():
     return render_template('trading_philosophy.html')

@app.route('/orders')
def orders():
    return '''<!DOCTYPE html>
<html><head><title>Orders - AIMn Trading</title>
<style>body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
h1 { color: #00ff00; } a { color: #00ccff; text-decoration: none; }
.placeholder { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }</style>
</head><body><h1>Orders Management</h1>
<div class="placeholder"><h3>Order History</h3><p>View and manage your trading orders</p></div>
<div class="placeholder"><h3>Active Orders</h3><p>Monitor currently active orders</p></div>
<p><a href="/">Back to Dashboard</a></p></body></html>'''

@app.route('/popper')
def popper():
    return '''<!DOCTYPE html>
<html><head><title>Trade Popup - AIMn Trading</title>
<style>body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
h1 { color: #00ff00; } a { color: #00ccff; text-decoration: none; }
.trade-box { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }
.pnl { font-size: 24px; color: #00ff00; }</style>
</head><body><h1>Live Trade Monitor</h1>
<div class="trade-box"><h3>Active Position</h3>
<div class="pnl">P&L: +$1,234.56 (+2.45%)</div>
<p>Symbol: BTC/USD | Entry: $43,250 | Current: $44,310</p>
<button style="background: red; color: white; padding: 10px 20px; border: none; border-radius: 5px;">Emergency Exit</button></div>
<p><a href="/">Back to Dashboard</a></p></body></html>'''

@app.route('/loop')
def loop_controls():
    return '''<!DOCTYPE html>
<html><head><title>Loop Controls - AIMn Trading</title>
<style>body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
h1 { color: #00ff00; } a { color: #00ccff; text-decoration: none; }
.control-box { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }
button { background: #0066cc; color: white; padding: 10px 20px; border: none; border-radius: 5px; margin: 5px; }</style>
</head><body><h1>Trading Loop Controls</h1>
<div class="control-box"><h3>System Status</h3>
<p>Status: <span style="color: #00ff00;">ACTIVE</span></p>
<button>Start Loop</button><button>Pause Loop</button>
<button style="background: red;">Stop All</button></div>
<p><a href="/">Back to Dashboard</a></p></body></html>'''

@app.route('/snapshots')
def snapshots():
    return '''<!DOCTYPE html>
<html><head><title>Snapshots - AIMn Trading</title>
<style>body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
h1 { color: #00ff00; } a { color: #00ccff; text-decoration: none; }
.snapshot-box { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }</style>
</head><body><h1>Trade Snapshots</h1>
<div class="snapshot-box"><h3>Recent Snapshots</h3><p>View captured trading moments and analysis</p></div>
<div class="snapshot-box"><h3>Performance History</h3><p>Historical performance data and analytics</p></div>
<p><a href="/">Back to Dashboard</a></p></body></html>'''

@app.route('/trader-guide')
def trader_guide():
    return '''<!DOCTYPE html>
<html>
<head>
    <title>Trader Guide - AIMn Trading</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #1a1a1a;
            color: white;
            padding: 40px;
            margin: 0;
        }
        h1 { color: #00ff00; }
        a { color: #00ccff; text-decoration: none; }
    </style>
</head>
<body>
    <h1>Trader Guide</h1>
    <p>Simple explanation and tips for experienced traders.</p>
    <a href="/">Back to Dashboard</a>
</body>
</html>'''

@app.route('/debug-template')
def debug_template():
    import os
    template_path = os.path.join(app.template_folder, 'trade_popup_fixed.html')
    exists = os.path.exists(template_path)
    size = os.path.getsize(template_path) if exists else 0
    return f'''
    <html>
    <body style="font-family: monospace; padding: 20px;">
        <h1>Debug Info</h1>
        <p><b>Template folder:</b> {app.template_folder}</p>
        <p><b>Full path:</b> {template_path}</p>
        <p><b>File exists:</b> {exists}</p>
        <p><b>File size:</b> {size} bytes</p>
        <p><b>Working directory:</b> {os.getcwd()}</p>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True)