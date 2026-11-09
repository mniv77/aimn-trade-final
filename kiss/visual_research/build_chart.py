import json
from pathlib import Path
BASE = Path(__file__).resolve().parent
aapl_candles = json.loads((BASE / 'aimn_aapl_candles.json').read_text())
aapl_trades = json.loads((BASE / 'aimn_aapl_exp53.json').read_text())
nvda_candles = json.loads((BASE / 'aimn_nvda_candles.json').read_text())
nvda_trades = json.loads((BASE / 'aimn_nvda_exp53.json').read_text())
data = {'AAPL': {'candles': aapl_candles, 'trades': aapl_trades}, 'NVDA': {'candles': nvda_candles, 'trades': nvda_trades}}
chart_json = json.dumps(data)
html = '''<html><head><meta charset='utf-8'><title>AIMn Exp53 Visual Research</title></head><body><h2>AIMn Exp53 - Causal V15 Research</h2><select id='symbol'><option>AAPL</option><option>NVDA</option></select><select id='outcome'><option value='all'>All trades</option><option value='win'>Winners</option><option value='loss'>Losers</option></select>
<div id='chart' style='height:650px'></div>
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<script>const researchData = '''
html += chart_json
html += ';'
html += """
const chart = LightweightCharts.createChart(document.getElementById('chart'), {width:1000,height:650});
const candles = chart.addCandlestickSeries();
"""
html += """
function loadSymbol(symbol) { const rows = researchData[symbol].candles; candles.setData(rows.map(r => ({time: Date.parse(r.timestamp.replace(' ','T')+'Z')/1000, open:+r.open, high:+r.high, low:+r.low, close:+r.close}))); chart.timeScale().fitContent(); }
document.getElementById('symbol').onchange = e => loadSymbol(e.target.value);
loadSymbol('AAPL');
function tradeTime(t) { return Date.parse(t.replace(' ','T')+'Z')/1000; }
function showTrades(symbol) { const trades = researchData[symbol].trades; const markers = [];
const filter = document.getElementById('outcome').value; for (const t of trades) { if (filter === 'win' && t.net_pnl_pct <= 0) continue; if (filter === 'loss' && t.net_pnl_pct > 0) continue;
markers.push({time:tradeTime(t.entry_time),position:'aboveBar',color:'#e74c3c',shape:'arrowDown',text:'SHORT '+t.trade_id});
markers.push({time:tradeTime(t.exit_time),position:'belowBar',color:t.net_pnl_pct>0?'#22c55e':'#f59e0b',shape:'arrowUp',text:'EXIT '+Number(t.net_pnl_pct).toFixed(2)+'%'});
}; markers.sort((a,b)=>a.time-b.time); candles.setMarkers(markers); }
document.getElementById('symbol').addEventListener('change',e=>showTrades(e.target.value));
document.getElementById('outcome').onchange=()=>showTrades(document.getElementById('symbol').value);
showTrades('AAPL');
</script></body></html>"""
(BASE / 'exp53_chart.html').write_text(html, encoding='utf-8')
