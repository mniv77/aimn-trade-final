from flask import Flask, render_template, jsonify
import random
from app_sub.views import main_bp
from AImnMLResearch.aiml_dashboard import aiml_bp

app = Flask(__name__)

# Register blueprints with a prefix to avoid route conflicts
app.register_blueprint(main_bp, url_prefix='/main')
app.register_blueprint(aiml_bp, url_prefix='/aiml')

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>AIMn Trading System - Revolutionary AI Trading</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #0C1324 0%, #1a1a2e 50%, #16213e 100%);
                color: #F5F7FA;
                min-height: 100vh;
                overflow-x: hidden;
            }

            .header-section {
                background: linear-gradient(135deg, rgba(15,209,200,0.1) 0%, rgba(182,255,77,0.1) 100%);
                padding: 30px 20px;
                border-bottom: 2px solid rgba(15,209,200,0.3);
                position: relative;
            }

            .header-content {
                max-width: 1200px;
                margin: 0 auto;
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 20px;
            }

            .logo-container {
                display: flex;
                align-items: center;
                gap: 20px;
            }

            .logo-svg {
                filter: drop-shadow(0 4px 16px rgba(15,209,200,0.2));
                height: 80px;
                width: auto;
            }

            .header-info {
                text-align: right;
                flex: 1;
                min-width: 200px;
            }

            .system-status {
                color: #0FD1C8;
                font-size: 0.9rem;
                font-weight: 600;
                margin-bottom: 5px;
            }

            .live-indicator {
                color: #B6FF4D;
                font-size: 0.8rem;
                display: flex;
                align-items: center;
                justify-content: flex-end;
                gap: 8px;
            }

            .status-dot {
                width: 8px;
                height: 8px;
                background: #B6FF4D;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }

            .hero-section {
                padding: 60px 20px;
                text-align: center;
                position: relative;
            }

            .hero-content {
                position: relative;
                z-index: 2;
                max-width: 1200px;
                margin: 0 auto;
            }

            .main-title {
                font-size: 3.5em;
                background: linear-gradient(45deg, #0FD1C8, #B6FF4D, #0FD1C8);
                background-size: 200% 200%;
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                animation: gradient-shift 3s ease-in-out infinite;
                text-shadow: 0 0 30px rgba(15,209,200,0.5);
                margin-bottom: 20px;
                font-weight: 700;
                font-family: 'Space Grotesk', sans-serif;
            }

            @keyframes gradient-shift {
                0%, 100% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
            }

            .subtitle {
                font-size: 1.8em;
                color: #0FD1C8;
                margin-bottom: 15px;
                text-shadow: 0 0 20px rgba(15,209,200,0.5);
                font-weight: 300;
            }

            .tagline {
                font-size: 1.3em;
                color: #cccccc;
                font-style: italic;
                margin-bottom: 40px;
                opacity: 0.9;
            }

            .quote {
                font-size: 1.5em;
                color: #B6FF4D;
                font-weight: 600;
                background: rgba(0,0,0,0.3);
                padding: 25px;
                border-radius: 12px;
                border-left: 4px solid #B6FF4D;
                margin: 30px auto;
                max-width: 800px;
                box-shadow: 0 8px 32px rgba(182,255,77,0.1);
            }

            .navigation-section {
                background: rgba(0,0,0,0.4);
                padding: 50px 20px;
                margin-top: 40px;
            }

            .nav-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 20px;
                max-width: 1600px;
                margin: 0 auto;
            }

            .nav-card {
                background: linear-gradient(135deg, rgba(15,209,200,0.1) 0%, rgba(182,255,77,0.1) 100%);
                border-radius: 12px;
                padding: 25px;
                text-align: center;
                transition: all 0.3s ease;
                border: 2px solid rgba(15,209,200,0.2);
                position: relative;
                overflow: hidden;
            }

            .nav-card:hover {
                transform: translateY(-5px);
                border-color: #B6FF4D;
                box-shadow: 0 10px 30px rgba(182,255,77,0.3);
            }

            .nav-card a {
                color: #0FD1C8;
                text-decoration: none;
                font-size: 1.3em;
                font-weight: 600;
                display: block;
                position: relative;
                z-index: 2;
                margin-bottom: 10px;
            }

            .nav-card a:hover {
                color: #B6FF4D;
            }

            .nav-desc {
                color: #cccccc;
                margin-top: 10px;
                font-size: 1em;
                position: relative;
                z-index: 2;
                opacity: 0.9;
                line-height: 1.4;
            }

            .cta-section {
                background: linear-gradient(135deg, #0FD1C8 0%, #B6FF4D 100%);
                color: #0C1324;
                padding: 50px 20px;
                text-align: center;
                margin-top: 40px;
            }

            .cta-title {
                font-size: 2.5em;
                font-weight: 700;
                margin-bottom: 20px;
            }

            .cta-text {
                font-size: 1.3em;
                margin-bottom: 30px;
                opacity: 0.9;
            }

            .cta-button {
                background: #0C1324;
                color: #B6FF4D;
                padding: 15px 40px;
                border: none;
                border-radius: 10px;
                font-size: 1.2em;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                margin: 10px;
                text-decoration: none;
                display: inline-block;
                border: 2px solid transparent;
            }

            .cta-button:hover {
                background: transparent;
                color: #0C1324;
                border-color: #0C1324;
                transform: scale(1.05);
                box-shadow: 0 10px 30px rgba(12,19,36,0.3);
            }

            .nav-section-title {
                text-align: center;
                color: #0FD1C8;
                font-size: 2.2em;
                margin-bottom: 40px;
                font-weight: 600;
            }

            /* Responsive adjustments */
            @media (max-width: 768px) {
                .header-content {
                    justify-content: center;
                    text-align: center;
                }

                .header-info {
                    text-align: center;
                }

                .live-indicator {
                    justify-content: center;
                }

                .main-title {
                    font-size: 2.5em;
                }

                .logo-svg {
                    height: 60px;
                }
            }
        </style>
    </head>
    <body>
        <div class="header-section">
            <div class="header-content">
                <div class="logo-container">
                    <!-- AIMn Professional Logo -->
                    <svg class="logo-svg" width="420" height="120" viewBox="0 0 420 120" xmlns="http://www.w3.org/2000/svg">
                        <!-- Main symbol -->
                        <g transform="translate(60, 60)">
                            <!-- Outer circle with gradient -->
                            <circle cx="0" cy="0" r="28" fill="none" stroke="url(#primaryGradient)" stroke-width="2.5"/>

                            <!-- Inner geometric A representing AI -->
                            <path d="M-10,-15 L0,-22 L10,-15 L7,-10 L-7,-10 Z"
                                  fill="none" stroke="#B6FF4D" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                            <line x1="-5" y1="-6" x2="5" y2="-6" stroke="#B6FF4D" stroke-width="2.5" stroke-linecap="round"/>

                            <!-- Market chart bars -->
                            <g transform="translate(0, 10)">
                                <rect x="-8" y="0" width="2.5" height="10" fill="#0FD1C8" rx="1"/>
                                <rect x="-3" y="-3" width="2.5" height="13" fill="#B6FF4D" rx="1"/>
                                <rect x="2" y="2" width="2.5" height="8" fill="#0FD1C8" rx="1"/>
                                <rect x="7" y="-1" width="2.5" height="11" fill="#0FD1C8" rx="1"/>
                            </g>

                            <!-- Subtle connection lines suggesting network -->
                            <g stroke="#0FD1C8" stroke-width="1" opacity="0.4">
                                <line x1="-20" y1="-8" x2="-15" y2="-5"/>
                                <line x1="15" y1="-5" x2="20" y2="-8"/>
                                <line x1="-20" y1="8" x2="-15" y2="5"/>
                                <line x1="15" y1="5" x2="20" y2="8"/>
                            </g>
                        </g>

                        <!-- Wordmark -->
                        <text x="120" y="52" font-family="Space Grotesk, sans-serif" font-size="42" font-weight="600" fill="#F5F7FA">AIMn</text>

                        <!-- Tagline -->
                        <text x="120" y="76" font-family="Inter, sans-serif" font-size="12" fill="#0FD1C8" letter-spacing="2px" opacity="0.9">TRADING SYSTEM</text>

                        <!-- Gradient definition -->
                        <defs>
                            <linearGradient id="primaryGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                <stop offset="0%" stop-color="#0FD1C8"/>
                                <stop offset="100%" stop-color="#B6FF4D"/>
                            </linearGradient>
                        </defs>
                    </svg>
                </div>

                <div class="header-info">
                    <div class="system-status">Multi-Professor System Active</div>
                    <div class="live-indicator">
                        <span class="status-dot"></span>
                        Live Market Scanning
                    </div>
                </div>
            </div>
        </div>

        <div class="hero-section">
            <div class="hero-content">
                <div class="main-title">Revolutionary AI Trading Platform</div>
                <div class="subtitle">Neural Trading • Market Intelligence • Profit Optimization</div>
                <div class="tagline">Where Advanced AI Meets Precision Trading Excellence</div>
                <div class="quote">
                    "Let the market pick your trades. Let logic pick your exits."
                </div>
            </div>
        </div>

        <div class="navigation-section">
            <div class="hero-content">
                <h2 class="nav-section-title">
                    Access Your Trading Command Center
                </h2>
                <div class="nav-grid">
                    <div class="nav-card">
                        <a href="/scanne">Live Scanner</a>
                        <div class="nav-desc">Real-time market scanning across all exchanges</div>
                    </div>
                    <div class="nav-card">
                        <a href="/tuning">Tuning Parameters Center</a>
                        <div class="nav-desc">Advanced strategy optimization and parameter tuning</div>
                    </div>
                    <div class="nav-card">
                        <a href="/orders">Orders</a>
                        <div class="nav-desc">Order management and trade history</div>
                    </div>
                    <div class="nav-card">
                        <a href="/trade-tester">Trade Tester</a>
                        <div class="nav-desc">Manual trade testing and simulation tools</div>
                    </div>
                    <div class="nav-card">
                        <a href="/symbols">Symbol & API Management</a>
                        <div class="nav-desc">Configure trading pairs and broker connections</div>
                    </div>
                    <div class="nav-card">
                        <a href="/simple-explanation">Simple Explanation</a>
                        <div class="nav-desc">Easy-to-understand system overview</div>
                    </div>
                    <div class="nav-card">
                        <a href="/architectural-analysis">Architectural Analysis</a>
                        <div class="nav-desc">Detailed trading philosophy and system architecture</div>
                    </div>
                    <div class="nav-card">
                        <a href="/scanner-analysis">Multi-Professor Scanner Analysis</a>
                        <div class="nav-desc">In-depth scanner methodology and analysis</div>
                    </div>
                    <div class="nav-card">
                        <a href="/scanner-simulator">Trade Scanner Simulator</a>
                        <div class="nav-desc">Manual trade popup testing and simulation</div>
                    </div>
                    <div class="nav-card">
                        <a href="/beginner-guide">System Overview</a>
                        <div class="nav-desc">Architectural analysis for non-traders</div>
                    </div>
                    <div class="nav-card">
                        <a href="/main">Main Blueprint</a>
                        <div class="nav-desc">Access main application features</div>
                    </div>
                    <div class="nav-card">
                        <a href="/aiml">AI/ML Dashboard</a>
                        <div class="nav-desc">AI and Machine Learning analysis tools</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="cta-section">
            <div class="cta-title">Ready to Trade Like a Pro?</div>
            <div class="cta-text">
                Join the revolution of traders who never miss an opportunity
            </div>
            <a href="/scanne" class="cta-button">Start Live Scanning</a>
            <a href="/tuning" class="cta-button">Tune Parameters</a>
        </div>
    </body>
    </html>
    '''

@app.route('/scanne')
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
    return render_template('aimn_diagnostic_scanner.htm')

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


if __name__ == '__main__':
    app.run(debug=True)