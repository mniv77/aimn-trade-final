#!/bin/bash
# repair_popup.sh — restore fully-fixed popup base from git, re-apply mirror mode
cd ~/aimn-trade-final
git show 1b5ff1d:templates/trade-full.html > templates/trade-full.html
python3 << 'PYEOF'
f2 = 'templates/trade-full.html'
s = open(f2, newline='').read()
nl = '\r\n' if '\r\n' in s else '\n'
old = "    autoTradeMode=(window.opener!=null);"
new = ("    tradeData.mode=urlParams.get('mode')||'';" + nl +
"    tradeData.trade_id=urlParams.get('trade_id')||null;" + nl +
"    tradeData.side=urlParams.get('side')||null;   // LONG / SHORT (engine trade)" + nl +
"    tradeData.entry=parseFloat(urlParams.get('entry'))||0;" + nl +
"    tradeData.ctime=urlParams.get('ctime')||'1h';" + nl +
"    tradeData.etime=parseInt(urlParams.get('etime'))||0;" + nl +
"    viewMode=(tradeData.mode==='view' && !!tradeData.side);" + nl +
"    autoTradeMode=(window.opener!=null) && !viewMode;")
assert old in s, "2a not found"; s = s.replace(old, new, 1)
old = "  let autoTradeMode=false;"
new = "  let autoTradeMode=false, viewMode=false;"
assert old in s, "2b not found"; s = s.replace(old, new, 1)
old = "    if(autoTradeMode){ setTimeout(()=>{ enterOrder(); }, 3000); }"
new = ("    if(viewMode){ mirrorEngineTrade(); }" + nl +
"    else if(autoTradeMode){ setTimeout(()=>{ enterOrder(); }, 3000); }")
assert old in s, "2c not found"; s = s.replace(old, new, 1)
old = "  function enterOrder(){"
new = ("  function mirrorEngineTrade(){" + nl +
"    setDirection(tradeData.side==='LONG' ? 'BUY' : 'SELL');" + nl +
"    entryPrice = tradeData.entry || tradeData.price;" + nl +
"    topPeak = entryPrice; activeTradeId = tradeData.trade_id; inPosition = true;" + nl +
"    stopLoss = tradeDirection==='BUY' ? entryPrice*(1-params.stop_loss_pct/100) : entryPrice*(1+params.stop_loss_pct/100);" + nl +
"    document.getElementById('setup-display').classList.add('hidden');" + nl +
"    document.getElementById('position-display').classList.remove('hidden');" + nl +
"    document.getElementById('btn-panic').disabled=false;" + nl +
"    document.getElementById('btn-panic').className='bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-lg font-bold text-sm';" + nl +
"    document.getElementById('btn-enter').disabled=true;" + nl +
"    document.getElementById('btn-enter').className='flex-1 bg-gray-600 text-gray-400 py-2 rounded-lg font-bold text-sm cursor-not-allowed';" + nl +
"    document.getElementById('entry-price').textContent='\$'+entryPrice.toFixed(2);" + nl +
"    showStatus('\\uD83D\\uDCE1 Mirroring engine trade #'+(activeTradeId||'?')+' \\u2014 '+tradeData.side+' from \$'+entryPrice.toFixed(2),'info');" + nl +
"  }" + nl + nl +
"  function enterOrder(){" + nl +
"    if(viewMode){ showStatus('View mode \\u2014 this popup mirrors the engine trade','error'); return; }")
assert old in s, "2d not found"; s = s.replace(old, new, 1)
old = ("    fetch('/api/trade/close', {" + nl +
"      method:'POST', headers:{'Content-Type':'application/json'}," + nl +
"      body:JSON.stringify({trade_id:activeTradeId, symbol:tradeData.symbol," + nl +
"                           pnl:finalPnl, reason:reason, exit_price:currentPrice})" + nl +
"    }).catch(()=>{});")
new = ("    if(viewMode){" + nl +
"      const durSecs = tradeData.etime ? Math.floor((Date.now()-tradeData.etime)/1000) : 0;" + nl +
"      fetch('/finalize_order', {" + nl +
"        method:'POST', headers:{'Content-Type':'application/json'}," + nl +
"        body:JSON.stringify({strategy_id:activeTradeId, symbol:tradeData.symbol," + nl +
"                             broker:tradeData.exchange, direction:tradeData.side," + nl +
"                             candle_time:tradeData.ctime, entry_price:entryPrice," + nl +
"                             exit_price:currentPrice, pnl:finalPnl, duration:durSecs})" + nl +
"      }).catch(()=>{});" + nl +
"    } else {" + nl +
"      fetch('/api/trade/close', {" + nl +
"        method:'POST', headers:{'Content-Type':'application/json'}," + nl +
"        body:JSON.stringify({trade_id:activeTradeId, symbol:tradeData.symbol," + nl +
"                             pnl:finalPnl, reason:reason, exit_price:currentPrice})" + nl +
"      }).catch(()=>{});" + nl +
"    }")
assert old in s, "2e not found"; s = s.replace(old, new, 1)
open(f2, 'w', newline='').write(s)
print("MIRROR MODE APPLIED")
PYEOF
echo "--- VERIFICATION ---"
echo "widgetembed(>=1): $(grep -c widgetembed templates/trade-full.html)"
echo "Math.random(=0): $(grep -c Math.random templates/trade-full.html)"
echo "mirror(>=1): $(grep -c mirrorEngineTrade templates/trade-full.html)"
echo "tz-badge(>=1): $(grep -c chart-tz-badge templates/trade-full.html)"
echo "heartbeat(>=1): $(grep -c feed-heartbeat templates/trade-full.html)"
grep -o "chartInterval='[0-9]*'" templates/trade-full.html | head -1
touch /var/www/meirniv_pythonanywhere_com_wsgi.py
git add templates/trade-full.html
git commit -m "Repair popup: restore full-featured base (iframe chart, no fake prices, heartbeat, UTC badge, 30m) lost when mirror-mode was built on stale base, re-apply mirror mode on top"
git push origin main