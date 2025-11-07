# test_scanner.py
from flask import Flask, jsonify
from datetime import datetime
import random

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>AIMn Test Scanner</h1>
    <p><a href='/scanner'>Scanner</a></p>
    """

@app.route('/scanner')
def scanner():
    return """
    <html>
    <head>
        <title>Test Scanner</title>
        <style>
            body { background: black; color: white; font-family: monospace; padding: 20px; }
            table { width: 100%; border: 1px solid #333; }
            th, td { padding: 10px; border: 1px solid #333; text-align: center; }
            th { background: #222; color: #0f0; }
            .signal-on { background: #0f0; color: black; padding: 5px 10px; border-radius: 5px; }
            .signal-off { background: #333; color: #999; padding: 5px 10px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>Simple Scanner Test</h1>
        <p>Status: <span id="status">Loading...</span></p>
        
        <table>
            <thead>
                <tr>
                    <th>TIME</th>
                    <th>SYMBOL</th>
                    <th>SIGNAL</th>
                    <th>RSI</th>
                </tr>
            </thead>
            <tbody id="data">
                <tr><td colspan="4">Waiting...</td></tr>
            </tbody>
        </table>
        
        <script>
        // Simple test - no fancy features
        function loadData() {
            document.getElementById('status').innerText = 'Fetching...';
            
            // Use full URL
            fetch('https://meirniv.pythonanywhere.com/api/test-scanner')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('status').innerText = 'Got data!';
                    
                    // Build simple table
                    let html = '';
                    data.entries.forEach(entry => {
                        html += '<tr>';
                        html += '<td>' + entry.time + '</td>';
                        html += '<td>' + entry.symbol + '</td>';
                        html += '<td><span class="' + (entry.signal ? 'signal-on' : 'signal-off') + '">' + 
                                (entry.signal ? 'ON' : 'OFF') + '</span></td>';
                        html += '<td>' + entry.rsi + '</td>';
                        html += '</tr>';
                    });
                    
                    document.getElementById('data').innerHTML = html;
                })
                .catch(error => {
                    document.getElementById('status').innerText = 'Error: ' + error;
                });
        }
        
        // Load immediately
        loadData();
        
        // Reload every 3 seconds
        setInterval(loadData, 3000);
        </script>
    </body>
    </html>
    """

@app.route('/api/test-scanner')
def test_scanner_api():
    """Simple test API"""
    entries = []
    symbols = ['BTC/USD', 'ETH/USD', 'AAPL']
    
    for symbol in symbols:
        rsi = random.randint(20, 80)
        signal = rsi < 30 or rsi > 70
        
        entries.append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'symbol': symbol,
            'signal': signal,
            'rsi': rsi
        })
    
    return jsonify({'entries': entries})

if __name__ == '__main__':
    app.run(debug=True, port=5001)