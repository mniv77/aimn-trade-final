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

    # New, isolated KISS strategy path. Existing backtest routes above remain unchanged.
    from kiss_backtest_routes import register_kiss_backtest_routes
    register_kiss_backtest_routes(app)
