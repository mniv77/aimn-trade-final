# filename: AImnMLResearch/aiml_dashboard.py

from flask import Blueprint, render_template, request
from AImnMLResearch.backtest_loop_skeleton import run_backtest
import pandas as pd
from sqlalchemy import text


from shared_models import BacktestResult, Trade
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import create_engine

aiml_bp = Blueprint(
    'aiml_research', __name__, template_folder='templates',
    static_folder='static', url_prefix='/aiml'
)


@aiml_bp.route('/manual-tune', methods=['GET', 'POST'])
def manual_tune():
    pnl_pct = None
    n_trades = n_wins = n_losses = win_rate = n_buy_orders = n_sell_orders = avg_trade_pct = max_drawdown = 0
    trades = []
    session = Session()
    try:
        symbols = [row[0] for row in session.execute(text("SELECT DISTINCT symbol FROM strategy_params")).fetchall()]
    except Exception:
        symbols = []
    finally:
        session.close()
    brokers = ["Alpaca", "Gemini", "Auto"]
    if request.method == 'POST':
        try:
            rsi_exit_buy_val  = int(request.form.get('rsi_exit_buy_whole', 70))  + float(request.form.get('rsi_exit_buy_decimal', 0))
            rsi_exit_sell_val = int(request.form.get('rsi_exit_sell_whole', 30)) + float(request.form.get('rsi_exit_sell_decimal', 0))
            trade_mode = request.form.get('trade_mode', 'BUY')
            params = {
                'symbol': request.form.get('symbol', ''),
                'broker': request.form.get('broker', ''),
                'trade_mode': trade_mode,
                'rsi_window': int(request.form.get('rsi_window', 100)),
                'oversold_level': int(request.form.get('oversold_level_whole', 30)) + float(request.form.get('oversold_level_decimal', 0)),
                'overbought_level': int(request.form.get('overbought_level_whole', 70)) + float(request.form.get('overbought_level_decimal', 0)),
                'rsi_exit_buy': rsi_exit_buy_val,
                'rsi_exit_sell': rsi_exit_sell_val,
                # backward-compat: some older backtest code uses plain 'rsi_exit'
                'rsi_exit': rsi_exit_buy_val if trade_mode == 'BUY' else rsi_exit_sell_val,
                'macd_fast_length': int(request.form.get('macd_fast_length', 12)),
                'macd_slow_length': int(request.form.get('macd_slow_length', 26)),
                'macd_signal_length': int(request.form.get('macd_signal_length', 9)),
                'vol_ma_length_buy': int(request.form.get('vol_ma_length_buy', 20)),
                'vol_threshold_buy': int(request.form.get('vol_threshold_buy_whole', 1)) + float(request.form.get('vol_threshold_buy_decimal', 0.2)),
                'use_volume_filter_buy': request.form.get('use_volume_filter_buy', 'true') == 'true',
                'atr_length_buy': int(request.form.get('atr_length_buy', 14)),
                'atr_ma_length_buy': int(request.form.get('atr_ma_length_buy', 20)),
                'atr_threshold_buy': int(request.form.get('atr_threshold_buy_whole', 1)) + float(request.form.get('atr_threshold_buy_decimal', 0.3)),
                'use_atr_filter_buy': request.form.get('use_atr_filter_buy', 'true') == 'true',
                'stop_loss_percent_buy': int(request.form.get('stop_loss_percent_buy_whole', 2)) + float(request.form.get('stop_loss_percent_buy_decimal', 0)),
                'early_trail_start_percent_buy': int(request.form.get('early_trail_start_percent_buy_whole', 1)) + float(request.form.get('early_trail_start_percent_buy_decimal', 0)),
                'early_trail_minus_percent_buy': int(request.form.get('early_trail_minus_percent_buy_whole', 1)) + float(request.form.get('early_trail_minus_percent_buy_decimal', 0.5)),
                'peak_trail_start_percent_buy': int(request.form.get('peak_trail_start_percent_buy_whole', 5)) + float(request.form.get('peak_trail_start_percent_buy_decimal', 0)),
                'peak_trail_minus_percent_buy': int(request.form.get('peak_trail_minus_percent_buy_whole', 0)) + float(request.form.get('peak_trail_minus_percent_buy_decimal', 0.5)),
                # Sell mode
                'vol_ma_length_sell': int(request.form.get('vol_ma_length_sell', 20)),
                'vol_threshold_sell': int(request.form.get('vol_threshold_sell_whole', 1)) + float(request.form.get('vol_threshold_sell_decimal', 0.2)),
                'use_volume_filter_sell': request.form.get('use_volume_filter_sell', 'true') == 'true',
                'atr_length_sell': int(request.form.get('atr_length_sell', 14)),
                'atr_ma_length_sell': int(request.form.get('atr_ma_length_sell', 20)),
                'atr_threshold_sell': int(request.form.get('atr_threshold_sell_whole', 1)) + float(request.form.get('atr_threshold_sell_decimal', 0.3)),
                'use_atr_filter_sell': request.form.get('use_atr_filter_sell', 'true') == 'true',
                'stop_loss_percent_sell': int(request.form.get('stop_loss_percent_sell_whole', 2)) + float(request.form.get('stop_loss_percent_sell_decimal', 0)),
                'early_trail_start_percent_sell': int(request.form.get('early_trail_start_percent_sell_whole', 1)) + float(request.form.get('early_trail_start_percent_sell_decimal', 0)),
                'early_trail_minus_percent_sell': int(request.form.get('early_trail_minus_percent_sell_whole', 1)) + float(request.form.get('early_trail_minus_percent_sell_decimal', 0.5)),
                'peak_trail_start_percent_sell': int(request.form.get('peak_trail_start_percent_sell_whole', 5)) + float(request.form.get('peak_trail_start_percent_sell_decimal', 0)),
                'peak_trail_minus_percent_sell': int(request.form.get('peak_trail_minus_percent_sell_whole', 0)) + float(request.form.get('peak_trail_minus_percent_sell_decimal', 0.5)),
                'min_exit_profit_pct_buy': float(request.form.get('min_exit_profit_pct_buy', 1.0)),
                'min_exit_profit_pct_sell': float(request.form.get('min_exit_profit_pct_sell', 1.0)),
            }

            # Find the data file relative to this file's location
            import os as _os
            _here = _os.path.dirname(_os.path.abspath(__file__))
            _project_root = _os.path.dirname(_here)
            _data_candidates = [
                _os.path.join(_project_root, 'data', 'btcusd_sample.csv'),
                '/home/MeirNiv/aimn-trade-final/data/btcusd_sample.csv',
                _os.path.join(_here, 'data', 'btcusd_sample.csv'),
            ]
            _data_file = next((p for p in _data_candidates if _os.path.exists(p)), None)
            if _data_file is None:
                raise FileNotFoundError(
                    "btcusd_sample.csv not found. Expected at data/btcusd_sample.csv "
                    "inside the project root."
                )

            df = pd.read_csv(_data_file)
            results = run_backtest(df, params)
            pnl_pct = results['compound_total_pct']
            n_trades = results['n_trades']
            n_wins = results['n_wins']
            n_losses = results['n_losses']
            win_rate = results['win_rate']
            n_buy_orders = results['n_buy_orders']
            n_sell_orders = results['n_sell_orders']
            avg_trade_pct = results['avg_trade_pct']
            max_drawdown = results['max_drawdown']
            trades = results.get('trades', [])

            # --- SAVE TO DATABASE ---
            try:
                save_session = Session()
                backtest = BacktestResult(
                    compound_total_pct=pnl_pct,
                    n_trades=n_trades,
                    win_rate=win_rate,
                    n_buy_orders=n_buy_orders,
                    n_sell_orders=n_sell_orders,
                    avg_trade_pct=avg_trade_pct,
                    max_drawdown=max_drawdown,
                    temporary=True
                )
                save_session.add(backtest)
                save_session.commit()
                save_session.close()
            except Exception:
                pass  # DB save is non-critical; don't fail the whole request

        except Exception as _e:
            import traceback as _tb
            pnl_pct = None
            n_trades = n_wins = n_losses = win_rate = n_buy_orders = n_sell_orders = avg_trade_pct = max_drawdown = 0
            trades = []
            error_msg = str(_e)
            # Re-render the form with a readable error (not raw JSON)
            return render_template(
                'aiml/manual_tune.html',
                pnl_pct=None, n_trades=0, n_wins=0, n_losses=0,
                win_rate=0, n_buy_orders=0, n_sell_orders=0,
                avg_trade_pct=0, max_drawdown=0, trades=[],
                symbols=symbols, brokers=brokers,
                backtest_error=error_msg,
            )

    return render_template(
        'aiml/manual_tune.html',
        pnl_pct=pnl_pct,
        n_trades=n_trades,
        n_wins=n_wins,
        n_losses=n_losses,
        win_rate=win_rate,
        n_buy_orders=n_buy_orders,
        n_sell_orders=n_sell_orders,
        avg_trade_pct=avg_trade_pct,
        max_drawdown=max_drawdown,
        trades=trades,
        symbols=symbols,
        brokers=brokers
    )

# --- Database session setup (replace with your actual DB URI) ---
DB_URI = "mysql+pymysql://MeirNiv:mayyam18@MeirNiv.mysql.pythonanywhere-services.com/MeirNiv$default?charset=utf8mb4"
engine = create_engine(DB_URI, pool_pre_ping=True)
Session = scoped_session(sessionmaker(bind=engine))

@aiml_bp.route('/trades')
def show_trades():
    session = Session()
    trades = session.query(Trade).order_by(Trade.ts.desc()).limit(100).all()
    session.close()
    return render_template('aiml/trades.html', trades=trades)