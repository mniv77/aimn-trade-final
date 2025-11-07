// /aimn-trade-final/static/js/trade_popup_manager.js
function openTradePopupForSignal(signalData) {
    // Block other trades on this exchange
    if (activeTradeExchange && signalData.exchange === activeTradeExchange) {
        console.log(`Trade blocked: ${signalData.symbol} - Exchange busy`);
        return;
    }

    // Prepare URL parameters securely
    const params = new URLSearchParams({
        symbol: signalData.symbol || '', 
        side: signalData.signal || '', 
        qty: signalData.quantity || '1',
        exchange: signalData.exchange || '',
        price: signalData.price || '',
        change: signalData.change || '',
        rsi: signalData.rsi || '',
        signal: signalData.signal || '',
        reason: signalData.reason || `Scanner detected ${signalData.signal} signal`
    });

    // Ensure only one popup per symbol
    if (openedPopups.has(signalData.symbol)) {
        console.log(`Popup already open for ${signalData.symbol}`);
        return;
    }

    try {
        // Open popup with more robust settings
        const popupWindow = window.open(
            `/trade-popup-fixed?${params.toString()}`, 
            `TradeWindow_${signalData.symbol}`, 
            'width=900,height=1000,resizable=no,scrollbars=no,status=no,menubar=no,toolbar=no'
        );

        // Validate popup window
        if (!popupWindow) {
            alert('Popup blocked. Please allow popups for this site.');
            return;
        }

        // Mark as opened
        openedPopups.add(signalData.symbol);

        // Set active trade state
        activeTradeSymbol = signalData.symbol;
        activeTradeExchange = signalData.exchange;

        // Timeout to remove from opened popups
        setTimeout(() => {
            openedPopups.delete(signalData.symbol);
        }, 2 * 60 * 1000); // 2 minutes

    } catch (error) {
        console.error('Failed to open trade popup:', error);
        alert('Could not open trade popup. Please check browser settings.');
    }
}