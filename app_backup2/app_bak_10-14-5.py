from flask import Flask, render_template, jsonify
import random
from app_sub.views import main_bp
from AImnMLResearch.aiml_dashboard import aiml_bp

app = Flask(__name__)



# Register blueprints with a prefix to avoid route conflicts
app.register_blueprint(main_bp, url_prefix='/main')
app.register_blueprint(aiml_bp, url_prefix='/aiml')

for rule in app.url_map.iter_rules():
    print("ROUTE:", rule, rule.endpoint)


@app.route('/trade-popup')
def trade_popup():
    return render_template('aimn_trade_popup.html')


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scanner')
def scanner():
    return render_template('aimn_flowing_scanner.html')

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

@app.route('/beginner-guide')
def beginner_guide():
    return '''<!DOCTYPE html>
<html>
<head>
    <title>System Overview - AIMn Trading</title>
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
    <h1>System Overview</h1>
    <p>Architectural analysis and system explanation for non-traders.</p>
    <a href="/">Back to Dashboard</a>
</body>
</html>'''

# API endpoints
@app.route('/api/exchange-status')
def exchange_status():
    return jsonify({
        'ALPACA': {'scanning': True, 'activeSymbol': None, 'symbolCount': 250, 'status': 'ACTIVE'},
        'CRYPTO': {'scanning': False, 'activeSymbol': 'BTC/USD', 'symbolCount': 100, 'status': 'TRADING'},
        'FOREX': {'scanning': True, 'activeSymbol': None, 'symbolCount': 50, 'status': 'ACTIVE'},
        'NYSE': {'scanning': True, 'activeSymbol': None, 'symbolCount': 200, 'status': 'ACTIVE'},
        'FUTURES': {'scanning': True, 'activeSymbol': None, 'symbolCount': 30, 'status': 'ACTIVE'}
    })

@app.route('/api/flowing-scanner-data')
def flowing_scanner_data():
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
        {'symbol': 'GOOGL', 'exchange': 'ALPACA'},
        {'symbol': 'META', 'exchange': 'NYSE'},
        {'symbol': 'NFLX', 'exchange': 'ALPACA'}
    ]

    scan_results = []
    busy_broker = 'CRYPTO'
    active_symbol = 'BTC/USD'

    for symbol_data in symbols:
        symbol = symbol_data['symbol']
        exchange = symbol_data['exchange']

        price = round(random.uniform(50, 550), 2)
        change = round(random.uniform(-10, 10), 2)
        volume = random.randint(100000, 1000000)
        rsi = round(random.uniform(0, 100), 1)
        signal = 'BUY' if rsi < 30 else 'SELL' if rsi > 70 else 'NEUTRAL'

        is_actively_trading = (exchange == busy_broker and symbol == active_symbol)
        is_available = exchange != busy_broker

        scan_results.append({
            'symbol': symbol,
            'exchange': exchange,
            'price': str(price),
            'change': str(change),
            'volume': f"{volume:,}",
            'rsi': str(rsi),
            'signal': signal,
            'signalStrength': str(round(random.uniform(0.2, 1.0), 2)) if signal != 'NEUTRAL' else '0',
            'isAvailable': is_available,
            'isActivelyTrading': is_actively_trading
        })

    return jsonify({'scanResults': scan_results})

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
    busy_broker = 'CRYPTO'
    active_symbol = 'BTC/USD'

    for symbol_data in symbols:
        symbol = symbol_data['symbol']
        exchange = symbol_data['exchange']

        is_actively_trading = (exchange == busy_broker and symbol == active_symbol)
        is_available = exchange != busy_broker

        ticker_items.append({
            'symbol': symbol,
            'exchange': exchange,
            'price': str(round(random.uniform(50, 550), 2)),
            'change': str(round(random.uniform(-10, 10), 2)),
            'signal': random.choice(['BUY', 'SELL', 'NEUTRAL', 'NEUTRAL', 'NEUTRAL']),
            'isAvailable': is_available,
            'isActivelyTrading': is_actively_trading
        })

    return jsonify(ticker_items)

@app.route('/trade-popup-v2')
def trade_popup_v2():
    return render_template('aimn_trade_popup.html')


@app.route('/debug-template')
def debug_template():
    import os
    template_path = os.path.join(app.template_folder, 'aimn_trade_popup.html')
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

for rule in app.url_map.iter_rules():
    print(rule, rule.endpoint)


if __name__ == '__main__':
    app.run(debug=True)