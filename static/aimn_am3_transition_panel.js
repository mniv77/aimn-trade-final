/* AIMn AM3 historical research overlay. No execution or strategy changes. */
(() => {
  'use strict';
  const anchor = document.getElementById('position');
  if (!anchor || document.getElementById('aimn-am3-panel')) return;
  const panel = document.createElement('section');
  panel.id = 'aimn-am3-panel';
  panel.style.cssText = 'margin:12px 0;padding:12px;border:1px solid #34465e;border-radius:8px;background:#111c2b;color:#dce6f0;font:14px system-ui,sans-serif';
  const heading = document.createElement('strong');
  heading.textContent = 'AM3 Transition Intelligence — historical research';
  const toggle = document.createElement('button');
  toggle.type = 'button'; toggle.textContent = 'Enable AM3 overlay';
  toggle.style.cssText = 'margin-left:12px;padding:5px 10px;cursor:pointer';
  const status = document.createElement('p');
  const detail = document.createElement('div');
  const history = document.createElement('div');
  history.style.cssText = 'max-height:220px;overflow:auto;white-space:pre-wrap;font:12px monospace';
  panel.append(heading,toggle,status,detail,history);
  const chartEl = document.getElementById('chart');
  if (chartEl) chartEl.before(panel); else anchor.after(panel);
  let enabled = false, data = null, checkedArray = null, aligned = false, failure = '', generation = 0;
  const expectedCounts = {AE3_WARNING:104,AJ1_REJECTED:66,AJ1_CONFIRMED:38,AM3_GATE:38,EXECUTION_DECISION:13,ENTRY:11,EXIT:11};
  const fmt = (v,d=2) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(d) : '—';
  function clearMarkers() { if (typeof series !== 'undefined' && series && typeof series.setMarkers === 'function') series.setMarkers([]); }
  function verifyPayload(d) {
    if (!d || d.symbol !== 'NVDA' || d.direction !== 'SHORT' || d.timeframe !== '5m' || Number(d.threshold) !== 0.6 || !d.research_only || !Array.isArray(d.candles) || d.candles.length !== 4680 || !Array.isArray(d.events) || d.events.length !== 281) throw Error('Unexpected AM3 research payload');
    const counts = {};
    let last = -1;
    for (const e of d.events) {
      if (!Object.hasOwn(expectedCounts,e.kind) || !Number.isInteger(e.candle_index) || e.candle_index < last || e.candle_index < 0 || e.candle_index >= d.candles.length || e.candle_time !== d.candles[e.candle_index][0]) throw Error('Invalid event alignment');
      last = e.candle_index; counts[e.kind] = (counts[e.kind] || 0) + 1;
    }
    for (const k of Object.keys(expectedCounts)) if (counts[k] !== expectedCounts[k]) throw Error('Unexpected count: '+k);
  }
  function align() {
    if (checkedArray === candles) return aligned;
    checkedArray = candles; aligned = false; failure = '';
    if (candles.length !== data.candles.length) { failure = 'Candle count differs from frozen discovery dataset.'; return false; }
    for (let i=0;i<candles.length;i++) {
      const c = candles[i], r = data.candles[i];
      if (c.time !== aimnNYSeconds(r[0])) { failure='UTC mismatch at candle '+(i+1); return false; }
      for (const [key,j] of [['open',1],['high',2],['low',3],['close',4]]) {
        if (!Number.isFinite(c[key]) || typeof r[j] !== 'number' || Math.abs(c[key]-r[j])>1e-8) { failure='OHLC mismatch at candle '+(i+1); return false; }
      }
    }
    aligned=true; return true;
  }
  function label(e) {
    switch(e.kind) {
      case 'AE3_WARNING': return 'AE3 WATCH SHORT | peak '+fmt(e.original_peak,3);
      case 'AJ1_CONFIRMED': return 'AJ1 confirmed';
      case 'AJ1_REJECTED': return 'AJ1 rejected: '+e.reason;
      case 'AM3_GATE': return 'AM3 '+e.decision+' | W12 '+(typeof e.w12==='number'?fmt(e.w12*100)+'%':'unavailable')+' / 60%';
      case 'EXECUTION_DECISION': return 'Execution '+e.status+' | ST5 '+e.st5+' / ST30 '+e.st30;
      case 'ENTRY': return 'SHORT OPEN #'+e.trade_id+' @ '+fmt(e.price,3);
      case 'EXIT': return 'EXIT #'+e.trade_id+' @ '+fmt(e.price,3)+' | '+e.reason+' | net '+fmt(e.net_pct,4)+'%';
      default: return e.kind;
    }
  }
  function marker(e) {
    let color,shape='circle',position='aboveBar',text;
    switch(e.kind) {
      case 'AE3_WARNING': color='#eab308';text='AE3';break;
      case 'AJ1_CONFIRMED': color='#f97316';text='AJ1';break;
      case 'AJ1_REJECTED': color='#94a3b8';text='AJ1 reject';break;
      case 'AM3_GATE': color=e.decision==='PASS'?'#ef4444':'#94a3b8';text=e.decision==='PASS'?'AM3 PASS':'AM3 reject';break;
      case 'ENTRY': color='#c084fc';shape='arrowDown';text='SHORT #'+e.trade_id;break;
      case 'EXIT': color=e.net_pct>0?'#22c55e':'#ef4444';shape='arrowUp';position='belowBar';text='EXIT '+fmt(e.net_pct,2)+'%';break;
      default:return null;
    }
    return {time:candles[e.candle_index].time,position,color,shape,text};
  }
  function refresh() {
    if (!enabled) { status.textContent='Blind Research — AM3 events hidden. Enable only after independent judgments are recorded.';detail.textContent='';history.textContent='';return; }
    try {
      if (typeof candles==='undefined' || typeof visible==='undefined' || typeof selectedSymbol==='undefined' || selectedSymbol!=='NVDA' || selectedTimeframe!=='5m' || researchDirection()!=='SHORT') throw Error('Available only for NVDA SHORT 5m discovery data.');
      if (!data) { status.textContent='Loading frozen historical research…';return; }
      if (!align()) throw Error(failure);
      if (!Number.isInteger(visible) || visible<1 || visible>candles.length) throw Error('No valid replay position.');
      const events=data.events.filter(e=>e.candle_index<visible);
      const current=events.filter(e=>e.candle_index===visible-1);
      let open=null, completed=0, net=0;
      for (const e of events) { if(e.kind==='ENTRY')open=e; if(e.kind==='EXIT'){open=null;completed++;net+=e.net_pct;} }
      status.textContent='AM3 overlay active — verified historical dataset; independent blind assessment is no longer blind.';
      detail.textContent=(open?'Research SHORT OPEN #'+open.trade_id+' @ '+fmt(open.price,3):'Research position CLOSED')+' | Completed trades: '+completed+' | Cumulative net trade sum: '+fmt(net,4)+'% | Current candle: '+(current.length?current.map(label).join(' • '):'No AM3 event');
      history.textContent=events.slice(-30).reverse().map(e=>new Date(candles[e.candle_index].time*1000).toISOString().replace('T',' ').replace('.000Z',' UTC')+' | '+label(e)).join('\n');
      if (typeof series!=='undefined' && series && typeof series.setMarkers==='function') series.setMarkers(events.map(marker).filter(Boolean));
    } catch(e) { clearMarkers();status.textContent='AM3 unavailable: '+e.message;detail.textContent='';history.textContent=''; }
  }
  toggle.addEventListener('click',async()=>{
    enabled=!enabled;const ticket=++generation;
    toggle.textContent=enabled?'Hide AM3 overlay':'Enable AM3 overlay';
    if(!enabled){clearMarkers();refresh();return;}
    refresh();
    if(!data){try{const r=await fetch('/static/aimn_visual_lab/aimn_am3_transition_data.json',{credentials:'same-origin',cache:'no-cache'});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();verifyPayload(d);if(ticket!==generation||!enabled)return;data=d;checkedArray=null;}catch(e){if(ticket===generation&&enabled)status.textContent='AM3 load failed: '+e.message;return;}}
    if(ticket===generation&&enabled)refresh();
  });
  new MutationObserver(refresh).observe(anchor,{childList:true,characterData:true,subtree:true});
  const direction=document.getElementById('direction');if(direction)direction.addEventListener('change',refresh);
  const mainStatus=document.getElementById('status');if(mainStatus)new MutationObserver(refresh).observe(mainStatus,{childList:true,characterData:true,subtree:true});
  refresh();
})();
