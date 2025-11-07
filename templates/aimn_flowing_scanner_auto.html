<!-- templates/aimn_flowing_scanner_auto.html -->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>AIMn Flowing Scanner Dashboard - AUTO MODE</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @keyframes scroll { 0% { transform: translateX(100%);} 100% { transform: translateX(-100%);} }
    @keyframes scroll-reverse { 0% { transform: translateX(-100%);} 100% { transform: translateX(100%);} }
    .animate-scroll { animation: scroll 80s linear infinite; }
    .animate-scroll-reverse { animation: scroll-reverse 60s linear infinite; }

    @keyframes scanPulse { 0%,100%{ box-shadow:0 0 0 0 rgba(59,130,246,.7); transform:scale(1);} 50%{ box-shadow:0 0 0 10px rgba(59,130,246,0); transform:scale(1.02);} }
    @keyframes scannerBeam { 0% { left: -100%; } 100% { left: 100%; } }

    .row-testing{ animation:scanPulse 2s infinite; border:2px solid #3b82f6!important; position:relative; overflow:hidden; background:linear-gradient(90deg,rgba(59,130,246,.15),rgba(59,130,246,.25),rgba(59,130,246,.15)); }
    .row-testing::before{ content:''; position:absolute; inset:0 auto 0 -100%; width:100%; background:linear-gradient(90deg,transparent,rgba(255,255,255,.25),transparent); animation:scannerBeam 2s infinite; }
    .row-testing::after{ content:'AUTO-TRADING...'; position:absolute; top:2px; right:2px; background:#3b82f6; color:#fff; padding:2px 6px; border-radius:3px; font-size:10px; font-weight:700; }

    .broker-available { background: rgba(0,128,0,0.15); border-color:#10b981; }
    .broker-busy { background: rgba(255,140,0,0.15); border-color:#f59e0b; }
    .symbol-available { background: rgba(0,200,0,0.12); border-left:4px solid #10b981; }
    .symbol-busy-active { background: rgba(220,38,38,0.18); border-left:4px solid #dc2626; }
    .symbol-busy-blocked { background: rgba(120,53,15,0.18); border-left:4px solid #92400e; }

    .ticker-available { background:#065f46; border:1px solid #10b981; color:#d1fae5; }
    .ticker-active-trade { background:#7f1d1d; border:1px solid #dc2626; color:#fecaca; }
    .ticker-blocked { background:#451a03; border:1px solid #92400e; color:#fcd34d; opacity:.85; }
  </style>
</head>
<body class="bg-gray-900 text-white">
  <div class="p-4 mb-4">
    <h1 class="text-3xl font-bold text-center mb-2">🤖 AIMn Auto-Trading Scanner</h1>
    <p class="text-center text-gray-400">Fully Automated Multi-Exchange Market Scanning & Trading</p>
    <p class="text-center text-xs text-green-400 mt-1">⚡ AUTO MODE - Trades execute automatically when signals detected</p>

    <div class="text-center mt-4">
      <div class="flex justify-center gap-4">
        <button onclick="openTradePopupTestStock()" class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold shadow-lg transition-all">
          📊 Manual Test - Stock (AAPL)
        </button>
        <button onclick="openTradePopupTestCrypto()" class="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-lg font-semibold shadow-lg transition-all">
          ₿ Manual Test - Crypto (BTC)
        </button>
      </div>
      <p class="text-gray-500 text-sm mt-2">Manual tests open popup without auto-trade | Scanner runs auto-trade mode</p>
    </div>

    <div class="text-center mt-3">
      <div class="inline-flex items-center space-x-2 bg-blue-600 px-4 py-2 rounded-lg">
        <div class="w-3 h-3 bg-white rounded-full animate-pulse"></div>
        <span class="text-sm font-semibold">Currently Testing: <span id="current-testing-symbol" class="font-mono">--</span></span>
      </div>
      <div class="text-xs text-gray-400 mt-1">Row <span id="testing-row-number">-</span> • Queue <span id="queue-size">0</span></div>
    </div>
  </div>

  <!-- Broker Status -->
  <div class="mx-4 mb-4 bg-gray-800 rounded-lg p-4">
    <h2 class="text-xl font-semibold mb-3">Broker Status</h2>
    <div id="exchange-status" class="grid grid-cols-1 md:grid-cols-5 gap-4"></div>
  </div>

  <!-- Rolling Belts -->
  <div class="mb-4 bg-black border-y border-gray-700">
    <div class="relative overflow-hidden py-3">
      <div id="main-ticker" class="flex animate-scroll whitespace-nowrap"></div>
    </div>
    <div class="space-y-1">
      <div class="relative overflow-hidden bg-gray-900 py-2">
        <div id="flow-1" class="flex animate-scroll-reverse whitespace-nowrap"></div>
      </div>
      <div class="relative overflow-hidden bg-gray-900 py-2">
        <div id="flow-2" class="flex animate-scroll whitespace-nowrap"></div>
      </div>
    </div>
  </div>

  <!-- Detailed Scan Results -->
  <div class="mx-4 bg-gray-800 rounded-lg p-4">
    <div class="flex justify-between items-center mb-3">
      <h2 class="text-xl font-semibold">Detailed Scan Results</h2>
      <div class="flex items-center space-x-2 text-sm">
        <div class="w-3 h-3 bg-blue-500 rounded animate-pulse"></div>
        <span class="text-gray-400">Row <span id="testing-row-number-2">-</span> Currently Being Analyzed</span>
      </div>
    </div>
    <div class="overflow-hidden">
      <div class="grid grid-cols-9 gap-2 text-sm font-semibold text-gray-400 mb-2 px-2">
        <div>Broker</div><div>Symbol</div><div>Status</div><div>Price</div><div>Change</div>
        <div>Volume</div><div>RSI</div><div>Signal</div><div>Action</div>
      </div>
      <div id="scan-results" class="max-h-96 overflow-y-auto space-y-1"></div>
    </div>
  </div>

  <div class="m-4 text-center">
    <a href="/" class="inline-block bg-green-600 hover:bg-green-700 text-white px-6 py-3 rounded-lg font-semibold transition-all duration-300">
      ← Back to Dashboard
    </a>
  </div>

  <!-- Legend -->
  <div class="m-4 bg-gray-800 rounded-lg p-4">
    <h3 class="text-lg font-semibold mb-2">Broker Trading Logic & Status Legend</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
      <div class="space-y-2">
        <div class="flex items-center space-x-2"><div class="w-4 h-4 bg-green-500 rounded"></div><span><strong>GREEN</strong> - Broker available</span></div>
        <div class="flex items-center space-x-2"><div class="w-4 h-4 bg-red-600 rounded"></div><span><strong>RED</strong> - Currently trading</span></div>
        <div class="flex items-center space-x-2"><div class="w-4 h-4 bg-yellow-700 rounded"></div><span><strong>BROWN</strong> - Blocked</span></div>
      </div>
    </div>
  </div>

  <!-- ===== Single unified script ===== -->
  <script>
    // --- state ---
    let exchanges = {}, scanData = [], tickerItems = [];
    const testingRowIndex = 3;
    let activeTradeSymbol = null;
    let activeTradeExchange = null;
    let activeTradeExchangeNorm = null;
    let activePopupWin = null;

    const MAX_CONCURRENT = 1;
    const MIN_GAP_BETWEEN_MS = 45_000;
    const BROKER_COOLDOWN_MS = 120_000;

    let lastPopupAt = 0;
    let lastByBroker = {};
    let popupQueue = [];
    let isOpening = false;

    // --- utils ---
    const el = id => document.getElementById(id);
    const normEx = s => String(s || "").toUpperCase().replace(/[^A-Z]/g, "");

    // --- init sample data (keep UI alive even without backend) ---
    function generateSampleExchangeData() {
      exchanges = {
        'ALPACA': { scanning: true, activeSymbol: null, symbolCount: 250 },
        'CRYPTO': { scanning: true, activeSymbol: null, symbolCount: 100 },
        'FOREX':  { scanning: true, activeSymbol: null, symbolCount: 50 },
        'NYSE':   { scanning: true, activeSymbol: null, symbolCount: 200 },
        'FUTURES':{ scanning: true, activeSymbol: null, symbolCount: 30 }
      };
    }
    function generateSampleScanData() {
      const symbols = [
        {symbol: 'BTC/USD', exchange: 'CRYPTO'},
        {symbol: 'ETH/USD', exchange: 'CRYPTO'},
        {symbol: 'AAPL',    exchange: 'ALPACA'},
        {symbol: 'TSLA',    exchange: 'ALPACA'},
        {symbol: 'NVDA',    exchange: 'ALPACA'},
        {symbol: 'SPY',     exchange: 'NYSE'},
        {symbol: 'QQQ',     exchange: 'NYSE'},
        {symbol: 'MSFT',    exchange: 'NYSE'},
        {symbol: 'AMZN',    exchange: 'NYSE'},
        {symbol: 'GOOGL',   exchange: 'ALPACA'},
        {symbol: 'META',    exchange: 'NYSE'},
        {symbol: 'NFLX',    exchange: 'ALPACA'},
        {symbol: 'AMD',     exchange: 'NYSE'},
        {symbol: 'INTC',    exchange: 'NASDAQ'}
      ];
      scanData = symbols.map(({symbol, exchange}) => {
        const rsi = (Math.random() * 100).toFixed(1);
        const signal = rsi < 30 ? 'BUY' : rsi > 70 ? 'SELL' : 'NEUTRAL';
        return {
          symbol, exchange,
          price: (Math.random() * 500 + 50).toFixed(2),
          change: ((Math.random() - 0.5) * 10).toFixed(2),
          volume: Math.floor(Math.random() * 1_000_000).toLocaleString(),
          rsi: rsi,
          signal,
          quantity: exchange === 'CRYPTO' ? 0.01 : 10
        };
      });
    }
    function generateSampleTickerData() {
      const symbols = [
        {symbol: 'BTC/USD', exchange: 'CRYPTO'},
        {symbol: 'ETH/USD', exchange: 'CRYPTO'},
        {symbol: 'AAPL', exchange: 'ALPACA'},
        {symbol: 'TSLA', exchange: 'ALPACA'},
        {symbol: 'NVDA', exchange: 'ALPACA'},
        {symbol: 'SPY', exchange: 'NYSE'},
        {symbol: 'QQQ', exchange: 'NYSE'},
        {symbol: 'MSFT', exchange: 'NYSE'},
        {symbol: 'AMZN', exchange: 'NYSE'},
        {symbol: 'GOOGL', exchange: 'ALPACA'}
      ];
      tickerItems = symbols.map(({symbol, exchange}) => ({
        symbol, exchange,
        price: (Math.random() * 500 + 50).toFixed(2),
        change: ((Math.random() - 0.5) * 10).toFixed(2),
        signal: Math.random() > 0.6 ? (Math.random() > 0.5 ? 'BUY' : 'SELL') : 'NEUTRAL'
      }));
    }

    // --- UI renderers ---
    function updateExchangeStatusDisplay() {
      const container = el('exchange-status');
      if (!container) return;
      container.innerHTML = '';
      Object.entries(exchanges).forEach(([name, info]) => {
        const nameNorm = normEx(name);
        const isAvailable = !activeTradeExchangeNorm || activeTradeExchangeNorm !== nameNorm;
        const statusClass = isAvailable ? 'broker-available' : 'broker-busy';
        const div = document.createElement('div');
        div.className = `${statusClass} border-2 rounded-lg p-3 transition-all duration-500`;
        div.innerHTML = `
          <div class="font-bold text-lg">${name}</div>
          <div class="text-sm mt-1">${info.symbolCount ?? '--'} symbols</div>
          <div class="text-xs mt-2 ${isAvailable ? 'text-green-300' : 'text-orange-300'}">
            ${isAvailable ? '🟢 AVAILABLE' : '🔴 TRADING: ' + (activeTradeSymbol ?? '')}
          </div>
        `;
        container.appendChild(div);
      });
    }

    function updateTickerDisplay() {
      ['main-ticker', 'flow-1', 'flow-2'].forEach(containerId => {
        const container = el(containerId);
        if (!container) return;
        container.innerHTML = '';
        tickerItems.forEach(item => {
          const exNorm = normEx(item.exchange);
          let klass = 'ticker-available';
          if (activeTradeSymbol && item.symbol === activeTradeSymbol) klass = 'ticker-active-trade';
          else if (activeTradeExchangeNorm && exNorm === activeTradeExchangeNorm) klass = 'ticker-blocked';
          const div = document.createElement('div');
          div.className = `${klass} px-4 py-2 mx-2 rounded inline-block transition-colors duration-500`;
          div.innerHTML = `
            <span class="font-mono font-semibold">${item.symbol}</span>
            <span class="ml-2">$${Number(item.price).toFixed(2)}</span>
            <span class="ml-2 ${parseFloat(item.change) >= 0 ? 'text-green-300' : 'text-red-300'}">${Number(item.change).toFixed(2)}%</span>
            ${item.signal && item.signal !== 'NEUTRAL' ? `<span class="ml-1 text-xs ${item.signal === 'BUY' ? 'text-green-300' : 'text-red-300'}">${item.signal}</span>` : ''}`;
          container.appendChild(div);
        });
      });
    }

    function updateScanResultsDisplay() {
      const container = el('scan-results');
      if (!container) return;
      container.innerHTML = '';

      scanData.forEach((row, index) => {
        const isTestingRow = (index === testingRowIndex);
        const rowExNorm = normEx(row.exchange);
        let statusClass = '';
        let statusText = '';

        if (isTestingRow) {
          statusClass = 'row-testing'; statusText = '🔍 TESTING NOW';
        } else if (row.symbol === activeTradeSymbol) {
          statusClass = 'symbol-busy-active'; statusText = '🔴 TRADING';
        } else if (activeTradeExchangeNorm && rowExNorm === activeTradeExchangeNorm) {
          statusClass = 'symbol-busy-blocked'; statusText = '🟤 BLOCKED';
        } else {
          statusClass = 'symbol-available'; statusText = '🟢 AVAILABLE';
        }

        const div = document.createElement('div');
        div.className = `grid grid-cols-9 gap-2 p-2 mb-1 rounded ${statusClass} text-sm items-center`;
        div.innerHTML = `
          <div class="font-semibold">${row.exchange}</div>
          <div class="font-mono font-bold ${isTestingRow ? 'text-xl' : ''}">${row.symbol}</div>
          <div class="text-xs font-semibold">${statusText}</div>
          <div>$${row.price}</div>
          <div class="${parseFloat(row.change) >= 0 ? 'text-green-400' : 'text-red-400'}">${row.change}%</div>
          <div class="text-xs">${row.volume}</div>
          <div class="${parseFloat(row.rsi) < 30 ? 'text-green-400 font-bold' : parseFloat(row.rsi) > 70 ? 'text-red-400 font-bold' : ''}">${row.rsi}</div>
          <div class="font-semibold ${row.signal === 'BUY' ? 'text-green-400' : row.signal === 'SELL' ? 'text-red-400' : 'text-gray-400'}">${row.signal}</div>
          <div class="text-xs">
            ${isTestingRow ? '🎯 ANALYZING' : row.signal !== 'NEUTRAL' ? '📊 SIGNAL' : '⏸️ WAITING'}
          </div>`;
        container.appendChild(div);
      });

      if (scanData[testingRowIndex]) {
        el('current-testing-symbol').textContent = scanData[testingRowIndex].symbol;
        el('testing-row-number').textContent = testingRowIndex + 1;
        el('testing-row-number-2').textContent = testingRowIndex + 1;
      }
      el('queue-size').textContent = popupQueue.length;
    }

    // --- rotation & belts heartbeat ---
    function conveyorBeltRotate() {
      if (scanData.length === 0) return;
      const first = scanData.shift();
      scanData.push(first);
      updateScanResultsDisplay();
      checkAndOpenPopups();
    }
    function tickerHeartbeat() {
      tickerItems.forEach(item => {
        const base = parseFloat(item.price);
        const delta = (Math.random() - 0.5) * 0.8;
        const next = Math.max(0.01, base + delta);
        item.price = next.toFixed(2);
        item.change = (((next - base) / Math.max(0.01, base)) * 100).toFixed(2);
      });
      updateTickerDisplay();
    }

    // --- popup throttle/queue ---
    function brokerCooling(nex) {
      const t = lastByBroker[nex] || 0;
      return (Date.now() - t) < BROKER_COOLDOWN_MS;
    }
    function eligibleNow(row) {
      const nex = normEx(row.exchange);
      if (activePopupWin && !activePopupWin.closed) return false;
      if (activeTradeExchangeNorm && nex === activeTradeExchangeNorm) return false;
      if (Date.now() - lastPopupAt < MIN_GAP_BETWEEN_MS) return false;
      if (brokerCooling(nex)) return false;
      return true;
    }
    function enqueuePopup(row) {
      const nex = normEx(row.exchange);
      const already = popupQueue.some(r => r.symbol === row.symbol && normEx(r.exchange) === nex);
      if (!already) popupQueue.push({...row});
      el('queue-size').textContent = popupQueue.length;
    }
    function processPopupQueue() {
      if (isOpening) return;
      if (popupQueue.length === 0) return;
      const cand = popupQueue[0];
      if (!eligibleNow(cand)) return;

      isOpening = true;
      popupQueue.shift();
      openTradePopupForSignal(cand);
      lastPopupAt = Date.now();

      const watch = setInterval(() => {
        if (!activePopupWin || activePopupWin.closed) {
          clearInterval(watch);
          activeTradeSymbol = null; activeTradeExchange = null; activeTradeExchangeNorm = null;
          isOpening = false;
          updateExchangeStatusDisplay(); updateScanResultsDisplay(); updateTickerDisplay();
          setTimeout(processPopupQueue, 300);
        }
      }, 1000);
    }
    function checkAndOpenPopups() {
      const row = scanData[testingRowIndex];
      if (!row) return;
      if (row.signal === 'BUY' || row.signal === 'SELL') enqueuePopup(row);
      processPopupQueue();
    }

    // --- popup open ---
    function openTradePopupForSignal(signalData) {
      activeTradeSymbol = signalData.symbol;
      activeTradeExchange = signalData.exchange;
      activeTradeExchangeNorm = normEx(signalData.exchange);

      updateScanResultsDisplay(); updateExchangeStatusDisplay(); updateTickerDisplay();

      const expandUrl = `/trade-full?symbol=${encodeURIComponent(signalData.symbol)}&exchange=${encodeURIComponent(signalData.exchange)}&qty=${encodeURIComponent(signalData.quantity||1)}&side=${encodeURIComponent(signalData.signal)}`;

      const params = new URLSearchParams({
        symbol: signalData.symbol,
        side: signalData.signal,
        qty: signalData.quantity || 1,
        exchange: signalData.exchange,
        price: signalData.price,
        change: signalData.change,
        rsi: signalData.rsi,
        signal: signalData.signal,
        expand_url: expandUrl,
        reason: `Scanner detected ${signalData.signal} - RSI: ${signalData.rsi}, Volume: ${signalData.volume}`
      });

      activePopupWin = window.open(
        `/trade-popup-fixed?${params.toString()}`,
        'TradeWindow_' + signalData.symbol,
        'width=560,height=90,scrollbars=no,toolbar=no,menubar=no'
      );
      setTimeout(() => { isOpening = false; }, 500);
    }

    // --- events from popup ---
    window.addEventListener('message', (event) => {
      if (event.data.type === 'TRADE_CLOSED') {
        const nex = normEx(event.data.exchange);
        lastByBroker[nex] = Date.now();
        activeTradeSymbol = null; activeTradeExchange = null; activeTradeExchangeNorm = null;
        updateExchangeStatusDisplay(); updateScanResultsDisplay(); updateTickerDisplay();
        setTimeout(processPopupQueue, 300);
      }
    });

    // --- manual test buttons ---
    function openTradePopupTestStock() {
      openTradePopupForSignal({ symbol:'AAPL', exchange:'ALPACA', signal:'BUY', quantity:10, price:'175.50', change:'+2.5', rsi:'65.3', volume:'1000000' });
    }
    function openTradePopupTestCrypto() {
      openTradePopupForSignal({ symbol:'BTC/USD', exchange:'CRYPTO', signal:'BUY', quantity:0.01, price:'43250.00', change:'+3.2', rsi:'58.5', volume:'500000' });
    }
    window.openTradePopupTestStock = openTradePopupTestStock;
    window.openTradePopupTestCrypto = openTradePopupTestCrypto;

    // --- boot ---
    function init() {
      generateSampleExchangeData();
      generateSampleScanData();
      generateSampleTickerData();
      updateExchangeStatusDisplay();
      updateTickerDisplay();
      updateScanResultsDisplay();

      setInterval(conveyorBeltRotate, 4000);
      setInterval(tickerHeartbeat, 1500);

      // soft refreshes
      setInterval(() => { updateExchangeStatusDisplay(); updateTickerDisplay(); }, 5000);
    }
    document.addEventListener('DOMContentLoaded', init);
  </script>
</body>
</html>
