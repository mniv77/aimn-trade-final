#  app.py

from flask import Flask, jsonify, render_template_string
from datetime import datetime
import random
import time

app = Flask(__name__)

# Store scanner history (in production, use a database)
scanner_history = []

# HTML template with live feed functionality
SCANNER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AIMn Live Scanner</title>
    <style>
        body {
            background: #0a0a0a;
            color: #e0e0e0;
            font-family: monospace;
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #00ff00;
            text-align: center;
        }
        .scanner-container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .controls {
            text-align: center;
            margin: 20px 0;
        }
        .live-indicator {
            display: inline-block;
            background: #ff0000;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        /* Fixed table layout */
        .table-container {
            background: #1a1a1a;
            border: 2px solid #333;
            border-radius: 5px;
            padding: 0;
            margin: 20px 0;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
        }
        
        thead {
            background: #252525;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        
        th {
            padding: 15px 10px;
            text-align: center;
            font-weight: bold;
            color: #00ff00;
            border-right: 1px solid #333;
            font-size: 1.1em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        th:last-child {
            border-right: none;
        }
        
        tbody tr {
            border-bottom: 1px solid #333;
            transition: all 0.3s ease;
        }
        
        tbody tr:hover {
            background: rgba(0, 255, 0, 0.05);
        }
        
        td {
            padding: 20px 10px;
            text-align: center;
            border-right: 1px solid #222;
            vertical-align: middle;
        }
        
        td:last-child {
            border-right: none;
        }
        
        /* Fixed 3 rows */
        tbody {
            display: block;
            height: 240px; /* 3 rows x 80px per row */
        }
        
        thead, tbody tr {
            display: table;
            width: 100%;
            table-layout: fixed;
        }
        
        /* Column widths */
        th:nth-child(1), td:nth-child(1) { width: 10%; } /* Time */
        th:nth-child(2), td:nth-child(2) { width: 15%; } /* Symbol */
        th:nth-child(3), td:nth-child(3) { width: 12%; } /* Direction */
        th:nth-child(4), td:nth-child(4) { width: 12%; } /* Signal */
        th:nth-child(5), td:nth-child(5) { width: 10%; } /* RSI */
        th:nth-child(6), td:nth-child(6) { width: 11%; } /* MACD */
        th:nth-child(7), td:nth-child(7) { width: 10%; } /* Volume */
        th:nth-child(8), td:nth-child(8) { width: 10%; } /* ATR */
        th:nth-child(9), td:nth-child(9) { width: 10%; } /* Action */
        
        /* Cell styling */
        .timestamp {
            color: #666;
            font-size: 0.9em;
        }
        
        .symbol {
            color: #00ffff;
            font-weight: bold;
            font-size: 1.3em;
        }
        
        .signal-long {
            color: #00ff00;
            font-weight: bold;
        }
        
        .signal-short {
            color: #ff0000;
            font-weight: bold;
        }
        
        .signal-on {
            background: #00ff00;
            color: #000;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        }
        
        .signal-off {
            background: #444;
            color: #999;
            padding: 5px 15px;
            border-radius: 20px;
        }
        
        .thumb-up {
            color: #00ff00;
            font-size: 1.3em;
        }
        
        .thumb-down {
            color: #ff0000;
            font-size: 1.3em;
        }
        
        .neutral {
            color: #666;
            font-size: 1.3em;
        }
        
        .action-btn {
            background: #0066ff;
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        
        .action-btn:hover {
            background: #0099ff;
            transform: scale(1.05);
        }
        
        .action-btn:disabled {
            background: #333;
            color: #666;
            cursor: not-allowed;
            transform: none;
        }
        
        /* New entry animation */
        .new-row {
            animation: highlight 2s ease-out;
        }
        
        @keyframes highlight {
            0% {
                background: rgba(0, 255, 0, 0.3);
                transform: scale(1.02);
            }
            100% {
                background: transparent;
                transform: scale(1);
            }
        }
        
        /* Empty row */
        .empty-row td {
            color: #444;
            font-style: italic;
        }
        
        .stats {
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
            padding: 15px;
            background: #1a1a1a;
            border-radius: 5px;
        }
        
        .stat-box {
            text-align: center;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #00ff00;
        }
        
        .stat-label {
            color: #666;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="scanner-container">
        <h1>🚀 AIMn Live Market Scanner</h1>
        
        <div class="controls">
            <span class="live-indicator">● LIVE</span>
        </div>
        
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value" id="total-scans">0</div>
                <div class="stat-label">Total Scans</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="active-signals">0</div>
                <div class="stat-label">Active Signals</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="long-signals">0</div>
                <div class="stat-label">Long Signals</div>
            </div>
            <div class="stat-box">
                <div class="stat-value" id="short-signals">0</div>
                <div class="stat-label">Short Signals</div>
            </div>
        </div>
        
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>TIME</th>
                        <th>SYMBOL</th>
                        <th>DIRECTION</th>
                        <th>SIGNAL</th>
                        <th>RSI</th>
                        <th>MACD</th>
                        <th>VOLUME</th>
                        <th>ATR</th>
                        <th>ACTION</th>
                    </tr>
                </thead>
                <tbody id="scanner-tbody">
                    <!-- Fixed 3 rows -->
                    <tr class="empty-row">
                        <td colspan="9">Waiting for data...</td>
                    </tr>
                    <tr class="empty-row">
                        <td colspan="9">Waiting for data...</td>
                    </tr>
                    <tr class="empty-row">
                        <td colspan="9">Waiting for data...</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <p style="text-align: center; margin-top: 20px;">
            <a href="/" style="color: #00ff00;">← Back to Dashboard</a>
        </p>
    </div>
    
    <script>
        let scannerData = [];
        let stats = {
            total: 0,
            active: 0,
            long: 0,
            short: 0
        };
        
        function updateStats() {
            document.getElementById('total-scans').textContent = stats.total;
            document.getElementById('active-signals').textContent = stats.active;
            document.getElementById('long-signals').textContent = stats.long;
            document.getElementById('short-signals').textContent = stats.short;
        }
        
        function getThumbIndicator(value, thresholds) {
            if (value >= thresholds.good) return '<span class="thumb-up">👍</span>';
            if (value <= thresholds.bad) return '<span class="thumb-down">👎</span>';
            return '<span class="neutral">➖</span>';
        }
        
        function updateTable() {
            const tbody = document.getElementById('scanner-tbody');
            let html = '';
            
            // Always show exactly 3 rows
            for (let i = 0; i < 3; i++) {
                if (i < scannerData.length) {
                    const data = scannerData[i];
                    const isNew = i === 0 && data.isNew;
                    
                    html += '<tr class="' + (isNew ? 'new-row' : '') + '">';
                    html += '<td class="timestamp">' + data.timestamp + '</td>';
                    html += '<td class="symbol">' + data.symbol + '</td>';
                    
                    // Direction
                    const directionClass = data.direction === 'LONG' ? 'signal-long' : 'signal-short';
                    html += '<td><span class="' + directionClass + '">' + data.direction + '</span></td>';
                    
                    // Signal
                    const signalClass = data.signal ? 'signal-on' : 'signal-off';
                    html += '<td><span class="' + signalClass + '">' + (data.signal ? 'ON' : 'OFF') + '</span></td>';
                    
                    // RSI with thumb
                    const rsiThumb = data.direction === 'LONG' ? 
                        getThumbIndicator(data.rsi, {good: 0, bad: 35}) : 
                        getThumbIndicator(data.rsi, {good: 65, bad: 100});
                    html += '<td>' + data.rsi + ' ' + rsiThumb + '</td>';
                    
                    // MACD with thumb
                    const macdThumb = data.direction === 'LONG' ?
                        getThumbIndicator(data.macd, {good: 0.05, bad: -0.05}) :
                        getThumbIndicator(data.macd, {good: -0.05, bad: 0.05});
                    html += '<td>' + data.macd.toFixed(3) + ' ' + macdThumb + '</td>';
                    
                    // Volume with thumb
                    const volThumb = getThumbIndicator(data.volume, {good: 1.5, bad: 0.8});
                    html += '<td>' + data.volume + 'x ' + volThumb + '</td>';
                    
                    // ATR with thumb
                    const atrThumb = getThumbIndicator(data.atr, {good: 1.2, bad: 0.8});
                    html += '<td>' + data.atr + ' ' + atrThumb + '</td>';
                    
                    // Action
                    if (data.signal) {
                        html += '<td><button class="action-btn" onclick="viewTrade(\'' + data.symbol + '\')">VIEW</button></td>';
                    } else {
                        html += '<td><button class="action-btn" disabled>-</button></td>';
                    }
                    
                    html += '</tr>';
                } else {
                    // Empty row
                    html += '<tr class="empty-row"><td colspan="9">-</td></tr>';
                }
            }
            
            tbody.innerHTML = html;
            
            // Remove new class after animation
            setTimeout(() => {
                const newRows = tbody.querySelectorAll('.new-row');
                newRows.forEach(row => row.classList.remove('new-row'));
            }, 2000);
        }
        
        function viewTrade(symbol) {
            window.open('/popup?symbol=' + symbol, 'trade-popup', 'width=800,height=600');
        }
        
        async function fetchScannerData() {
            try {
                const response = await fetch('/api/scanner-feed');
                const data = await response.json();
                
                if (data.new_entries && data.new_entries.length > 0) {
                    // Mark new entries
                    data.new_entries.forEach(entry => {
                        entry.isNew = true;
                        stats.total++;
                        if (entry.signal) {
                            stats.active++;
                            if (entry.direction === 'LONG') stats.long++;
                            else stats.short++;
                        }
                    });
                    
                    // Add new entries to beginning and keep only 3
                    scannerData = [...data.new_entries, ...scannerData].slice(0, 3);
                    
                    updateTable();
                    updateStats();
                }
            } catch (error) {
                console.error('Error fetching scanner data:', error);
            }
        }
        
        // Fetch data every 2 seconds
        setInterval(fetchScannerData, 2000);
        
        // Initial fetch
        fetchScannerData();
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return """
    <h1>🚀 AIMn Multi-Professor Trading System</h1>
    <p><a href='/scanner'>📈 Live Scanner Feed</a></p>
    <p><a href='/popup'>🪟 Trade Popup</a></p>
    <p><a href='/api/data'>📊 API Data</a></p>
    """

@app.route('/scanner')
def scanner():
    return render_template_string(SCANNER_TEMPLATE)

@app.route('/api/scanner-feed')
def scanner_feed():
    """Generate new scanner entries"""
    global scanner_history
    
    # Simulate new scanner data
    symbols = ['BTC/USD', 'ETH/USD', 'AAPL', 'TSLA', 'LINK/USD', 'DOGE/USD', 'SPY', 'QQQ']
    new_entries = []
    
    # Generate 1-3 new entries
    for _ in range(random.randint(1, 3)):
        symbol = random.choice(symbols)
        rsi = random.randint(20, 80)
        macd = round(random.uniform(-0.1, 0.1), 3)
        volume = round(random.uniform(0.5, 2.5), 1)
        atr = round(random.uniform(0.7, 1.8), 1)
        
        # Determine if signal
        is_long_signal = rsi < 35 and macd > 0 and volume > 1.2
        is_short_signal = rsi > 65 and macd < 0 and volume > 1.2
        has_signal = is_long_signal or is_short_signal
        
        # Calculate signal strength
        signal_strength = 0
        if has_signal:
            if is_long_signal:
                signal_strength = (35 - rsi) / 35 * 0.5 + (macd / 0.1) * 0.3 + (volume / 2) * 0.2
            else:
                signal_strength = (rsi - 65) / 35 * 0.5 + (abs(macd) / 0.1) * 0.3 + (volume / 2) * 0.2
            signal_strength = min(1.0, max(0.0, signal_strength))
        
        entry = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'symbol': symbol,
            'direction': 'LONG' if is_long_signal else 'SHORT' if is_short_signal else 'NEUTRAL',
            'signal': has_signal,
            'signal_strength': round(signal_strength, 2),
            'rsi': rsi,
            'macd': macd,
            'volume': volume,
            'atr': atr
        }
        
        new_entries.append(entry)
        scanner_history.insert(0, entry)
    
    # Keep only last 100 entries in history
    scanner_history = scanner_history[:100]
    
    return jsonify({
        'new_entries': new_entries,
        'total_entries': len(scanner_history)
    })

@app.route('/popup')
def popup():
    return '''
    <body style="background: black; color: white; padding: 20px;">
        <h1>🪟 LIVE TRADE ACTIVE</h1>
        <h2>📈 BTC/USD LONG Position</h2>
        <div style="font-size: 36px; color: #00ff00;">P&L: +2.35%</div>
        <p>Entry: $43,250 | Current: $44,267</p>
        <button style="background: red; color: white; padding: 15px;">🚨 PANIC EXIT NOW</button>
    </body>
    '''

@app.route('/api/data')
def api_data():
    return jsonify({'status': 'working', 'time': str(datetime.now())})

if __name__ == '__main__':
    app.run(debug=True, port=5001)