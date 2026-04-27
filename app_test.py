import os
from flask import Flask, render_template, request, redirect, jsonify
from flask_mysqldb import MySQL
from dotenv import load_dotenv
import pytz
from datetime import datetime

app = Flask(__name__)

# 1. LOAD CONFIGS
project_folder = '/home/MeirNiv/aimn-trade-final'
load_dotenv(os.path.join(project_folder, '.env'))

# 2. DB CONFIG
app.config.update(
    MYSQL_USER = 'MeirNiv',
    MYSQL_PASSWORD = os.getenv('DB_PASSWORD'),
    MYSQL_HOST = 'MeirNiv.mysql.pythonanywhere-services.com',
    MYSQL_DB = 'MeirNiv$default'
)
flask_db = MySQL(app)

# --- ROUTES ---

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/tuning/<path:symbol>/<direction>')
def tuning(symbol, direction):
    cursor = flask_db.connection.cursor()
    try:
        # Fetch Brokers
        cursor.execute("SELECT id, name FROM brokers")
        brokers = cursor.fetchall()

        # Fetch Symbols for the dynamic dropdown
        cursor.execute("SELECT broker_id, local_ticker FROM broker_products")
        all_symbols = [list(row) for row in cursor.fetchall()]

        # Identify selected broker to "pin" the dropdown
        selected_broker_id = next((s[0] for s in all_symbols if s[1] == symbol), 0)

        # Fetch RSI Real Parameters (7=Entry, 8=Exit, 21=Max, 22=Min)
        query = """
            SELECT sp.* FROM strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            WHERE bp.local_ticker = %s AND sp.direction = %s
        """
        cursor.execute(query, (symbol, direction))
        params = cursor.fetchone()

        return render_template('tuning.html', 
                               symbol=symbol, 
                               direction=direction,
                               brokers=brokers, 
                               all_symbols=all_symbols, 
                               params=params,
                               selected_broker_id=selected_broker_id)
    except Exception as e:
        print(f"Error: {e}")
        return f"Tuning Page Error: {e}", 500
    finally:
        cursor.close()

@app.route('/save_tuning', methods=['POST'])
def save_tuning():
    # Capture form data
    symbol = request.form.get('local_ticker')
    direction = request.form.get('direction')
    r_max = request.form.get('rsi_real_max')
    r_min = request.form.get('rsi_real_min')
    r_entry = request.form.get('rsi_entry')
    r_exit = request.form.get('rsi_exit')

    cursor = flask_db.connection.cursor()
    try:
        query = """
            UPDATE strategy_params sp
            JOIN broker_products bp ON sp.broker_product_id = bp.id
            SET sp.rsi_real_max = %s, sp.rsi_real_min = %s, 
                sp.rsi_entry = %s, sp.rsi_exit = %s,
                sp.last_tuned = NOW()
            WHERE bp.local_ticker = %s AND sp.direction = %s
        """
        cursor.execute(query, (r_max, r_min, r_entry, r_exit, symbol, direction))
        flask_db.connection.commit()
    except Exception as e:
        print(f"Save Error: {e}")
    finally:
        cursor.close()

    return redirect(f"/tuning/{symbol}/{direction}")

if __name__ == "__main__":
    app.run(debug=True)
