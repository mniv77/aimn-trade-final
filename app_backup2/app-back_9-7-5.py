# filename: app.py
from flask import Flask, render_template, jsonify
import json
import random

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scanne')
def scanner():
    return render_template('scanner.html')

# API endpoints for the scanner
@app.route('/api/exchange-status')
def exchange_status():
    # Sample exchange data
    return jsonify({
        'ALPACA': {'scanning': True, 'activeSymbol': None, 'symbolCount': 250, 'status': 'ACTIVE'},
        'CRYPTO': {'scanning': False, 'activeSymbol': 'BTC/USD', 'symbolCount': 100, 'status': 'TRADING'},
        'FOREX': {'scanning': True, 'activeSymbol': None, 'symbolCount': 50, 'status': 'ACTIVE'},
        'NYSE': {'scanning': True, 'activeSymbol': None, 'symbolCount': 200, 'status': 'ACTIVE'},
        'FUTURES': {'scanning': True, 'activeSymbol': None, 'symbolCount': 30, 'status': 'ACTIVE'}
    })

@app.route('/api/flowing-scanner-data')
def flowing_scanner_data():
    # Generate sample scan data
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

if __name__ == '__main__':
    app.run(debug=True)