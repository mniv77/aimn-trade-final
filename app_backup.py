from flask import Flask
from datetime import datetime
from trading_connector import TradingDataConnector

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>🚀 AIMn Multi-Professor Trading System</h1>
    <p><a href='/scanner'>📈 Live Scanner</a></p>
    <p><a href='/popup'>🪟 Trade Popup</a></p>
    """
app.route('/scanner')
def scanner():
    return f"""
    <head>
        <meta http-equiv="refresh" content="3">
        <style>
            table {{ width: 100%; border-collapse: collapse; }}
            ...
        </style>
    </head>

@app.route('/popup')
def popup():
    html_content = '''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { background: black; color: white; padding: 20px; font-family: Arial; }
            .pnl { font-size: 36px; color: #00ff00; margin: 20px 0; }
            .panic { background: red; color: white; padding: 15px; font-size: 20px; border: none; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>🪟 LIVE TRADE ACTIVE</h1>
        <h2>📈 BTC/USD LONG Position</h2>
        <div class="pnl">P&L: +2.35% ⚡</div>
        <p>Entry: $43,250 | Current: $44,267</p>
        <button class="panic">🚨 PANIC EXIT NOW</button>
        <p><a href="/" style="color: #00ff00;">← Close Window</a></p>
    </body>
    </html>
    '''
    return html_content
    @app.route('/scanner')
def scanner():
    return f"""
    <head>
        <meta http-equiv="refresh" content="3">
        <style>
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ background: #333; color: white; padding: 10px; }}
            td {{ padding: 8px; text-align: center; border: 1px solid #ddd; }}
            .on {{ background: #d4edda; color: #155724; }}
            .off {{ background: #f8d7da; color: #721c24; }}
        </style>
    </head>

    <h1>📊 Live Market Scanner</h1>
    <p>Time: {datetime.now().strftime('%H:%M:%S')} | <a href='/'>← Home</a></p>

    <table>
        <tr>
            <th>EXCHANGE</th>
            <th>SYMBOL</th>
            <th>DIRECTION</th>
            <th>ORDER</th>
            <th>RSI</th>
            <th>MACD</th>
            <th>VOL</th>
            <th>ATR</th>
        </tr>
        <tr class="on">
            <td>Alpaca</td>
            <td>BTC/USD</td>
            <td>↗️ LONG</td>
            <td><strong>ON</strong></td>
            <td>28</td>
            <td>0.045</td>
            <td>1.8</td>
            <td>1.4</td>
        </tr>
        <tr class="off">
            <td>Alpaca</td>
            <td>ETH/USD</td>
            <td>↘️ SHORT</td>
            <td><strong>OFF</strong></td>
            <td>73</td>
            <td>-0.023</td>
            <td>0.9</td>
            <td>1.1</td>
        </tr>
        <tr class="on">
            <td>Gemini</td>
            <td>AAPL</td>
            <td>↗️ LONG</td>
            <td><strong>ON</strong></td>
            <td>31</td>
            <td>0.067</td>
            <td>1.5</td>
            <td>1.2</td>
        </tr>
    </table>

    <p><a href='/popup'>🚀 VIEW ACTIVE TRADE</a></p>
    """