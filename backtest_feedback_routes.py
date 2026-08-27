#   backtest_feedback_routes.py
from flask import jsonify, request

def register_feedback_routes(app, db):
    @app.route('/api/backtest/save_feedback', methods=['POST'])
    def save_backtest_feedback():
        data = request.get_json() or {}
        order_id = data.get('id')
        feedback_tags = data.get('tags') # e.g., comma-separated or JSON list of canned answers
        feedback_comments = data.get('comments') # free text
        
        if not order_id:
            return jsonify({'error': 'Order ID is required'}), 400
            
        cursor = db.cursor()
        query = """
            UPDATE backtest_orders 
            SET reviewed = 1, feedback_tags = %s, feedback_comments = %s 
            WHERE id = %s
        """
        cursor.execute(query, (feedback_tags, feedback_comments, order_id))
        db.commit()
        
        return jsonify({'ok': True, message: 'Feedback saved successfully'})