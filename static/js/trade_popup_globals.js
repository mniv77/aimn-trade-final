// /aimn-trade-final/static/js/trade_popup_globals.js
// Global variables for trade management
let openedPopups = new Set();
let activeTradeSymbol = null;
let activeTradeExchange = null;

// Message listener to handle trade completion
window.addEventListener('message', (event) => {
    if (event.data.type === 'TRADE_CLOSED') {
        // Clear active trade
        if (event.data.symbol === activeTradeSymbol) {
            activeTradeSymbol = null;
            activeTradeExchange = null;
        }

        // Remove from opened popups
        openedPopups.delete(event.data.symbol);

        // Notify backend
        fetch('/api/trade-completed', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(event.data)
        });
    }
});