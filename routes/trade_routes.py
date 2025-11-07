# /aimn-trade-final/routes/trade_routes.py
@app.route('/trade-popup-fixed')
def trade_popup_fixed():
    # Extract all parameters
    symbol = request.args.get('symbol', '')
    side = request.args.get('side', '')
    qty = request.args.get('qty', '')
    exchange = request.args.get('exchange', '')
    price = request.args.get('price', '')
    change = request.args.get('change', '')
    rsi = request.args.get('rsi', '')
    signal = request.args.get('signal', '')
    reason = request.args.get('reason', '')

    # Render template with parameters
    return render_template('trade-popup-fixed.html', 
        symbol=symbol, 
        side=side, 
        qty=qty, 
        exchange=exchange, 
        price=price, 
        change=change, 
        rsi=rsi, 
        signal=signal, 
        reason=reason
    )