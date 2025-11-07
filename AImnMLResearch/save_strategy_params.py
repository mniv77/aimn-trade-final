# filename: save_strategy_params.py
import os
import pymysql

MYSQL_USER = os.environ.get("PA_MYSQL_USER")
MYSQL_DB   = os.environ.get("PA_MYSQL_DB")
MYSQL_PW   = os.environ.get("PA_MYSQL_PW")
MYSQL_HOST = os.environ.get("PA_MYSQL_HOST")

def save_strategy_params_with_profit(params, max_total_profit):
    sql = """
    INSERT INTO strategy_params (
        user_id, broker, symbol, timeframe, trade_mode, rsi_window, oversold_level, overbought_level,
        rsi_exit_buy, rsi_exit_sell, macd_fast, macd_slow, macd_signal, vol_ma_length, vol_threshold,
        use_volume_filter, atr_length, atr_ma_length, atr_threshold, use_atr_filter, stop_loss_pct,
        early_trail_start, early_trail_minus, peak_trail_start, peak_trail_minus, rsi_exit_min_profit,
        max_total_profit, enable_alerts, show_lines, show_signals
    ) VALUES (
        %(user_id)s, %(broker)s, %(symbol)s, %(timeframe)s, %(trade_mode)s, %(rsi_window)s, %(oversold_level)s, %(overbought_level)s,
        %(rsi_exit_buy)s, %(rsi_exit_sell)s, %(macd_fast)s, %(macd_slow)s, %(macd_signal)s, %(vol_ma_length)s, %(vol_threshold)s,
        %(use_volume_filter)s, %(atr_length)s, %(atr_ma_length)s, %(atr_threshold)s, %(use_atr_filter)s, %(stop_loss_pct)s,
        %(early_trail_start)s, %(early_trail_minus)s, %(peak_trail_start)s, %(peak_trail_minus)s, %(rsi_exit_min_profit)s,
        %(max_total_profit)s, %(enable_alerts)s, %(show_lines)s, %(show_signals)s
    )
    ON DUPLICATE KEY UPDATE
        rsi_window=VALUES(rsi_window),
        oversold_level=VALUES(oversold_level),
        overbought_level=VALUES(overbought_level),
        rsi_exit_buy=VALUES(rsi_exit_buy),
        rsi_exit_sell=VALUES(rsi_exit_sell),
        macd_fast=VALUES(macd_fast),
        macd_slow=VALUES(macd_slow),
        macd_signal=VALUES(macd_signal),
        vol_ma_length=VALUES(vol_ma_length),
        vol_threshold=VALUES(vol_threshold),
        use_volume_filter=VALUES(use_volume_filter),
        atr_length=VALUES(atr_length),
        atr_ma_length=VALUES(atr_ma_length),
        atr_threshold=VALUES(atr_threshold),
        use_atr_filter=VALUES(use_atr_filter),
        stop_loss_pct=VALUES(stop_loss_pct),
        early_trail_start=VALUES(early_trail_start),
        early_trail_minus=VALUES(early_trail_minus),
        peak_trail_start=VALUES(peak_trail_start),
        peak_trail_minus=VALUES(peak_trail_minus),
        rsi_exit_min_profit=VALUES(rsi_exit_min_profit),
        max_total_profit=VALUES(max_total_profit),
        enable_alerts=VALUES(enable_alerts),
        show_lines=VALUES(show_lines),
        show_signals=VALUES(show_signals),
        updated_at=NOW()
    """
    conn = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PW,
        database=MYSQL_DB,
        charset='utf8mb4'
    )
    params['max_total_profit'] = max_total_profit
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
    conn.commit()
    conn.close()

# Example usage:
params = {
    "user_id": 1,
    "broker": "Alpaca",
    "symbol": "BTC/USD",
    "timeframe": "1h",
    "trade_mode": "BUY",
    "rsi_window": 100,
    "oversold_level": 32.5,
    "overbought_level": 69.2,
    "rsi_exit_buy": 68.0,
    "rsi_exit_sell": 32.0,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "vol_ma_length": 20,
    "vol_threshold": 1.2,
    "use_volume_filter": 1,
    "atr_length": 14,
    "atr_ma_length": 20,
    "atr_threshold": 1.3,
    "use_atr_filter": 1,
    "stop_loss_pct": 2.0,
    "early_trail_start": 1.0,
    "early_trail_minus": 15.0,
    "peak_trail_start": 5.0,
    "peak_trail_minus": 0.5,
    "rsi_exit_min_profit": 1.0,
    "| max_total_profit": 2.0,
    "enable_alerts": 1,
    "show_lines": 1,
    "show_signals": 1
}
max_total_profit = 21.37  # Example: best profit percent found for these params

save_strategy_params_with_profit(params, max_total_profit)