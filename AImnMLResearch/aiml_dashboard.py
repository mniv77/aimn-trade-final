# filename: AImnMLResearch/aiml_dashboard.py

from flask import Blueprint, render_template, request
from AImnMLResearch.backtest_loop_skeleton import run_backtest
import pandas as pd
from sqlalchemy import text


from shared_models import BacktestResult, Trade
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import create_engine

aiml_bp = Blueprint(
    'aiml', __name__, template_folder='templates',
    static_folder='static', url_prefix='/aiml'
)

@aiml_bp.route('/')
def aiml_home():
    return render_template('aiml/home.html')


@aiml_bp.route('/manual-tune', methods=['GET', 'POST'])
def manual_tune():
    pnl_pct = None
    n_trades = n_wins = n_losses = win_rate = n_buy_orders = n_sell_orders = avg_trade_pct = max_drawdown = 0
    trades = []
    session = Session()
    symbols = [row[0] for row in session.execute(text("SELECT DISTINCT symbol FROM strategy_params")).fetchall()]
    brokers = [row[0] for row in session.execute(text("SELECT DISTINCT broker FROM strategy_params")).fetchall()]
    session.close()
    if request.method == 'POST':
        params = {
            'symbol': request.form['symbol'],
            'broker': request.form['broker'],
            'trade_mode': request.form['trade_mode'],
            'rsi_window': int(request.form['rsi_window']),
            'oversold_level': int(request.form['oversold_level_whole']) + float(request.form['oversold_level_decimal']),
            'overbought_level': int(request.form['overbought_level_whole']) + float(request.form['overbought_level_decimal']),
            'rsi_exit_buy': int(request.form['rsi_exit_buy_whole']) + float(request.form['rsi_exit_buy_decimal']),
            'rsi_exit_sell': int(request.form['rsi_exit_sell_whole']) + float(request.form['rsi_exit_sell_decimal']),
            'macd_fast_length': int(request.form['macd_fast_length']),
            'macd_slow_length': int(request.form['macd_slow_length']),
            'macd_signal_length': int(request.form['macd_signal_length']),
            'vol_ma_length_buy': int(request.form['vol_ma_length_buy']),
            'vol_threshold_buy': int(request.form['vol_threshold_buy_whole']) + float(request.form['vol_threshold_buy_decimal']),
            'use_volume_filter_buy': request.form['use_volume_filter_buy'] == 'true',
            'atr_length_buy': int(request.form['atr_length_buy']),
            'atr_ma_length_buy': int(request.form['atr_ma_length_buy']),
            'atr_threshold_buy': int(request.form['atr_threshold_buy_whole']) + float(request.form['atr_threshold_buy_decimal']),
            'use_atr_filter_buy': request.form['use_atr_filter_buy'] == 'true',
            'stop_loss_percent_buy': int(request.form['stop_loss_percent_buy_whole']) + float(request.form['stop_loss_percent_buy_decimal']),
            'early_trail_start_percent_buy': int(request.form['early_trail_start_percent_buy_whole']) + float(request.form['early_trail_start_percent_buy_decimal']),
            'early_trail_minus_percent_buy': int(request.form['early_trail_minus_percent_buy_whole']) + float(request.form['early_trail_minus_percent_buy_decimal']),
            'peak_trail_start_percent_buy': int(request.form['peak_trail_start_percent_buy_whole']) + float(request.form['peak_trail_start_percent_buy_decimal']),
            'peak_trail_minus_percent_buy': int(request.form['peak_trail_minus_percent_buy_whole']) + float(request.form['peak_trail_minus_percent_buy_decimal']),
            # Sell mode
            'vol_ma_length_sell': int(request.form['vol_ma_length_sell']),
            'vol_threshold_sell': int(request.form['vol_threshold_sell_whole']) + float(request.form['vol_threshold_sell_decimal']),
            'use_volume_filter_sell': request.form['use_volume_filter_sell'] == 'true',
            'atr_length_sell': int(request.form['atr_length_sell']),
            'atr_ma_length_sell': int(request.form['atr_ma_length_sell']),
            'atr_threshold_sell': int(request.form['atr_threshold_sell_whole']) + float(request.form['atr_threshold_sell_decimal']),
            'use_atr_filter_sell': request.form['use_atr_filter_sell'] == 'true',
            'stop_loss_percent_sell': int(request.form['stop_loss_percent_sell_whole']) + float(request.form['stop_loss_percent_sell_decimal']),
            'early_trail_start_percent_sell': int(request.form['early_trail_start_percent_sell_whole']) + float(request.form['early_trail_start_percent_sell_decimal']),
            'early_trail_minus_percent_sell': int(request.form['early_trail_minus_percent_sell_whole']) + float(request.form['early_trail_minus_percent_sell_decimal']),
            'peak_trail_start_percent_sell': int(request.form['peak_trail_start_percent_sell_whole']) + float(request.form['peak_trail_start_percent_sell_decimal']),
            'peak_trail_minus_percent_sell': int(request.form['peak_trail_minus_percent_sell_whole']) + float(request.form['peak_trail_minus_percent_sell_decimal']),
            'min_exit_profit_pct_buy': float(request.form['min_exit_profit_pct_buy']),
            'min_exit_profit_pct_sell': float(request.form['min_exit_profit_pct_sell']),
        }
        df = pd.read_csv('/home/MeirNiv/aimn-trade-final/data/btcusd_sample.csv')
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