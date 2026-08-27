# backtest_importer.py

import csv
from datetime import datetime

def import_backtest_csv(db, file_path, run_id):
    cursor = db.cursor()
    inserted_count = 0
    
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            query = """
                INSERT INTO backtest_orders (
                    run_id, symbol, exchange, side, quantity, 
                    entry_price, entry_time, entry_rsi_real, entry_rsi_wilder, 
                    exit_price, exit_time, exit_reason, pnl_pct, pnl_dollar, reviewed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
            """
            cursor.execute(query, (
                run_id,
                row.get('symbol'),
                row.get('exchange', 'ALPACA'),
                row.get('side'),
                float(row.get('quantity', 10)),
                float(row.get('entry_price')),
                row.get('entry_time'),
                float(row['entry_rsi_real']) if row.get('entry_rsi_real') else None,
                float(row['entry_rsi_wilder']) if row.get('entry_rsi_wilder') else None,
                float(row['exit_price']) if row.get('exit_price') else None,
                row.get('exit_time') if row.get('exit_time') else None,
                row.get('exit_reason'),
                float(row['pnl_pct']) if row.get('pnl_pct') else None,
                float(row['pnl_dollar']) if row.get('pnl_dollar') else None
            ))
            inserted_count += 1
            
    db.commit()
    print(f"Successfully imported {inserted_count} backtest orders for run: {run_id}")