# backtest_routes.py

from flask import jsonify, request


def register_backtest_routes(app, db):
    @app.route('/api/backtest/orders', methods=['GET'])
    def get_backtest_orders():
        symbol = request.args.get('symbol')
        if not symbol:
            return jsonify({'error': 'Symbol is required'}), 400

        cursor = db.cursor()
        query = """
            SELECT id, run_id, symbol, exchange, side, quantity,
                   entry_price, entry_time, entry_rsi_real, entry_rsi_wilder,
                   exit_price, exit_time, exit_reason, pnl_pct, pnl_dollar
            FROM backtest_orders
            WHERE symbol = %s AND (reviewed = 0 OR reviewed IS NULL)
            ORDER BY entry_time ASC
        """
        cursor.execute(query, (symbol,))
        rows = cursor.fetchall()

        orders = []
        for row in rows:
            orders.append({
                'id': row[0],
                'run_id': row[1],
                'symbol': row[2],
                'exchange': row[3],
                'side': row[4],
                'quantity': float(row[5]),
                'entry_price': float(row[6]),
                'entry_time': str(row[7]),
                'entry_rsi_real': float(row[8]) if row[8] is not None else None,
                'entry_rsi_wilder': float(row[9]) if row[9] is not None else None,
                'exit_price': float(row[10]) if row[10] is not None else None,
                'exit_time': str(row[11]) if row[11] is not None else None,
                'exit_reason': row[12],
                'pnl_pct': float(row[13]) if row[13] is not None else None,
                'pnl_dollar': float(row[14]) if row[14] is not None else None
            })

        return jsonify({'ok': True, 'orders': orders})

    @app.route('/api/backtest/mark_reviewed', methods=['POST'])
    def mark_backtest_reviewed():
        data = request.get_json() or {}
        order_id = data.get('id')
        if not order_id:
            return jsonify({'error': 'Order ID is required'}), 400

        cursor = db.cursor()
        query = "UPDATE backtest_orders SET reviewed = 1 WHERE id = %s"
        cursor.execute(query, (order_id,))
        db.commit()

        return jsonify({'ok': True})

    # ------------------------------------------------------------------
    # Independent KISS path. Existing selector/backtest logic is untouched.
    # ------------------------------------------------------------------
    from kiss_backtest_routes import register_kiss_backtest_routes
    register_kiss_backtest_routes(app)

    @app.after_request
    def inject_kiss_button(response):
        # Add the independent KISS button to the clean Auto Tuner control page.
        # The broker/symbol/direction/timeframe selection remains on the page.
        if request.path != '/auto_tuner' or response.status_code != 200:
            return response
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            return response
        try:
            html = response.get_data(as_text=True)
            if 'id="kiss_backtest_btn"' in html:
                return response
            script = r'''<script>
(function(){
  function addKissButton(){
    if(document.getElementById('kiss_backtest_btn')) return;
    var target=document.getElementById('kiss_button_anchor');
    if(!target) return;
    var b=document.createElement('button');
    b.id='kiss_backtest_btn';
    b.type='button';
    b.textContent='🎯 RUN KISS BACKTEST';
    b.style.cssText='padding:10px 24px;background:#7f1d1d;border:1px solid #ef4444;border-radius:4px;color:#fff;font-family:Arial,sans-serif;font-weight:800;font-size:15px;letter-spacing:1px;cursor:pointer;';
    b.title='Run the independent KISS transition strategy backtest.';
    b.onclick=function(){
      var broker=document.getElementById('broker_select');
      var symbol=document.getElementById('symbol_select');
      var tf=document.getElementById('timeframe_select');
      var longBtn=document.getElementById('btn_long');
      var shortBtn=document.getElementById('btn_short');
      var direction=(shortBtn && shortBtn.className.indexOf('active-short')>=0)?'SHORT':'LONG';
      if(!broker || !broker.value){alert('Please choose a broker first.');return;}
      if(!symbol || !symbol.value){alert('Please choose a symbol first.');return;}
      var u='/kiss_backtest?broker_id='+encodeURIComponent(broker.value)+'&symbol='+encodeURIComponent(symbol.value)+'&direction='+encodeURIComponent(direction)+'&timeframe='+encodeURIComponent(tf?tf.value:'1hr');
      window.open(u,'_blank');
    };
    target.appendChild(b);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',addKissButton); else addKissButton();
})();
</script>'''
            response.set_data(html.replace('</body>', script + '</body>'))
        except Exception as exc:
            print('[KISS BUTTON] injection failed:', exc)
        return response
