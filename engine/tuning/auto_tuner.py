
import sys
sys.path.insert(0, '/home/MeirNiv/aimn-trade-final')
from engine.kiss_v3_engine import KISSV3Engine
from engine.tuning.candle_fetcher import fetch_candles
from db import get_db_connection
from datetime import datetime

DEFAULT = {
    'trail_pct_options': [0.008, 0.012, 0.015, 0.02, 0.025, 0.03],
    'min_v_options': [0.002, 0.003, 0.005, 0.008],
    'timeframe': '1hr',
    'bars': 8000,
    'min_trades': 10,
    'score_metric': 'profit_per_day',
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def backtest_symbol(symbol, trail_pct, min_v_pct, timeframe='1hr', bars=8000):
    try:
        candles = fetch_candles(symbol, timeframe, bars)
        if not candles or len(candles) < 100:
            return None
        closes = [c.close if hasattr(c, 'close') else c for c in candles]
        engine = KISSV3Engine(mode="tuner")
        engine.TRAIL_PCT = trail_pct
        engine.MIN_V_PCT = min_v_pct
        trades = []
        entry = None
        entry_price = 0
        for i in range(2, len(closes)):
            sig, _ = engine.detect_transition(closes, from_idx=i)
            if sig=="FLAT" and entry is None:
                continue
            state = engine.next_state(sig if sig!="FLAT" else engine.state, closes[i])
            # open
            if entry is None and state in ("LONG","SHORT"):
                entry = state
                entry_price = closes[i]
            # close on FLAT or flip
            elif entry is not None and state=="FLAT":
                profit = (closes[i]-entry_price)/entry_price*100 if entry=="LONG" else (entry_price-closes[i])/entry_price*100
                trades.append(profit)
                entry = None
            elif entry is not None and state!=entry and state!="FLAT":
                profit = (closes[i]-entry_price)/entry_price*100 if entry=="LONG" else (entry_price-closes[i])/entry_price*100
                trades.append(profit)
                entry = state
                entry_price = closes[i]

        if len(trades) < 5:
            return None
        win_rate = len([t for t in trades if t > 0]) / len(trades) * 100
        avg_profit = sum(trades) / len(trades)
        total = sum(trades)
        return {'trades': len(trades), 'win_rate': win_rate, 'avg_profit': avg_profit, 'total': total, 'profit_per_day': total / (bars/24)}
    except Exception as e:
        log(f"Error {symbol} trail {trail_pct} min_v {min_v_pct}: {e}")
        import traceback; traceback.print_exc()
        return None

def tune_symbol(symbol):
    log(f"=== KISS V3 Tuning {symbol} - Trail x MinV = {len(DEFAULT['trail_pct_options'])*len(DEFAULT['min_v_options'])} combos ===")
    best = None
    best_params = None
    for trail in DEFAULT['trail_pct_options']:
        for min_v in DEFAULT['min_v_options']:
            result = backtest_symbol(symbol, trail, min_v, DEFAULT['timeframe'], DEFAULT['bars'])
            if not result:
                continue
            log(f" Trail {trail*100:.1f}% MinV {min_v*100:.2f}%: {result['trades']} trades WR {result['win_rate']:.1f}% avg {result['avg_profit']:.3f}% total {result['total']:.2f}%")
            score = result[DEFAULT['score_metric']]
            if best is None or score > best[DEFAULT['score_metric']]:
                best = result
                best_params = (trail, min_v)
    if best:
        log(f"BEST {symbol}: Trail {best_params[0]*100:.2f}% MinV {best_params[1]*100:.2f}% -> {best['trades']} trades WR {best['win_rate']:.1f}% total {best['total']:.2f}%")
        try:
            conn = get_db_connection()
            # conn may be tuple (conn, cursor) in your old db.py
            if isinstance(conn, tuple):
                conn, cur = conn
            else:
                cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS tuning_results (symbol VARCHAR(20), trail_pct FLOAT, min_v_pct FLOAT, win_rate FLOAT, avg_profit FLOAT, total_profit FLOAT, trades INT, mode VARCHAR(20), created_at DATETIME, PRIMARY KEY (symbol, mode))")
            cur.execute("REPLACE INTO tuning_results (symbol, trail_pct, min_v_pct, win_rate, avg_profit, total_profit, trades, mode, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,'kiss_v3',NOW())",
                        (symbol, best_params[0], best_params[1], best['win_rate'], best['avg_profit'], best['total'], best['trades']))
            conn.commit()
            conn.close()
        except Exception as e:
            log(f"DB save skip: {e}")
        return best_params, best
    return None, None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="QQQ")
    args = parser.parse_args()
    tune_symbol(args.symbol)
