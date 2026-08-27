# backtest_ai_trainer.py

import json

def generate_ai_training_dataset(db):
    cursor = db.cursor()
    # Pull trades that have been reviewed and have feedback attached
    query = """
        SELECT id, symbol, side, entry_price, exit_price, pnl_pct, 
               entry_rsi_real, exit_reason, duration_seconds, 
               feedback_tags, feedback_comments 
        FROM backtest_orders 
        WHERE reviewed = 1 AND feedback_comments IS NOT NULL
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    
    training_data = []
    for row in rows:
        trade_id, symbol, side, entry_p, exit_p, pnl, rsi_real, exit_reason, duration, tags, comments = row
        
        # Determine if it's a success or failure based on PnL or your feedback
        outcome = "SUCCESS" if pnl and pnl > 0 else "FAILURE"
        
        # Build a structured prompt/response pair for AI training or fine-tuning
        prompt = (
            f"Analyze trade outcome for {symbol} ({side}). "
            f"Entry RSI Real: {rsi_real}, Entry Price: {entry_p}, Exit Price: {exit_p}, "
            f"Duration: {duration}s, Exit Reason: {exit_reason}, PnL: {pnl}%."
        )
        
        completion = (
            f"Outcome: {outcome}. "
            f"Auditor Tags: {tags}. "
            f"Auditor Notes: {comments}."
        )
        
        training_data.append({
            "messages": [
                {"role": "system", "content": "You are an expert algorithmic trading assistant reviewing backtest performance."},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": completion}
            ]
        })
        
    # Save out as a JSONL file ready for AI training / fine-tuning or vector embedding lookup
    with open("ai_trade_training_data.jsonl", "w", encoding="utf-8") as f:
        for item in training_data:
            f.write(json.dumps(item) + "\n")
            
    print(f"Compiled {len(training_data)} trade reviews into ai_trade_training_data.jsonl for AI training.")