import sys
sys.path.insert(0, '.')
sys.path.insert(0, './engine')
import itertools
import yfinance as yf
import pandas as pd
from kiss_v3_engine import KISSV3Engine
from safety_filter import is_safe_to_enter, calculate_rsi

def load_data(symbol, period="1y"):
    df = yf.download(symbol, period=period, interval="1h", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def simulate_trades(df, trail, min_v):
    trades = []
    engine = KISSV3Engine()
    engine.TRAIL_PCT = trail
    engine.MIN_V_PCT = min_v
    for i in range(200, len(df)-5):
        window = df.iloc[i-200:i]
        safe, reason = is_safe_to_enter(window, min_v)
        if not safe:
            continue
        closes = window['Close'].tolist()
        try:
            if len(closes)>=3 and closes[-3] > closes[-2] < closes[-1]:
                depth = min(closes[-3], closes[-1]) - closes[-2]
                if depth / closes[-2] >= min_v:
                    entry = float(df['Close'].iloc[i])
                    peak = entry
                    exit_price = entry
                    for j in range(i+1, min(i+50, len(df))):
                        price = float(df['Close'].iloc[j])
                        peak = max(peak, price)
                        if price < peak * (1-trail):
                            exit_price = price
                            break
                        if j == min(i+49, len(df)-1):
                            exit_price = price
                    pnl = (exit_price - entry)/entry*100
                    last = window.iloc[-1]
                    gap = abs(float(last['Close']) - float(window.iloc[-2]['Close'])) / float(window.iloc[-2]['Close'])*100 if len(window)>1 else 0
                    rsi_series = calculate_rsi(window['Close'], 14)
                    rsi = float(rsi_series.iloc[-1]) if len(rsi_series)>0 else 50
                    sma200 = float(window['Close'].tail(200).mean())
                    trades.append({"entry_time": str(df.index[i]), "exit_time": str(df.index[min(i+10, len(df)-1)]), "entry_price": entry, "exit_price": exit_price, "pnl": pnl, "gap": gap, "rsi": rsi, "sma200": sma200, "vol": float(last['Volume']) if 'Volume' in window else 0, "avg_vol": float(window['Volume'].tail(20).mean()) if 'Volume' in window else 0, "price": entry, "reason": reason})
        except:
            continue
    return trades

def perfect_tune(symbol):
    df = load_data(symbol)
    best = None
    for trail, min_v in itertools.product([0.015,0.02,0.025,0.03,0.035], [0.001,0.002,0.003]):
        trades = simulate_trades(df, trail, min_v)
        if not trades: continue
        wr = sum(1 for t in trades if t['pnl']>0)/len(trades)
        total = sum(t['pnl'] for t in trades)
        losers = [t for t in trades if t['pnl']<0]
        for t in losers:
            if t['gap'] > 4.5: t['ai_comment'] = f"LOSER-GAP {t['gap']:.1f}% - thin giant skip"
            elif t['rsi'] > 80: t['ai_comment'] = f"LOSER-RSI {t['rsi']:.0f} - wrong trend"
            elif t['price'] < t['sma200']*0.94: t['ai_comment'] = "LOSER-WRONG-TREND below SMA200"
            elif t['vol'] < t['avg_vol']*0.05: t['ai_comment'] = "LOSER-THIN volume"
            else: t['ai_comment'] = "LOSER-SMALL-LOSS part of 67% game"
        if best is None or total > best['total']:
            best = {"symbol": symbol, "trail": trail, "min_v": min_v, "wr": wr, "total": total, "trades": trades, "losers": losers, "count": len(trades)}
        print(f"{symbol} trail={trail} min_v={min_v} WR={wr*100:.1f}% total={total:.1f}% trades={len(trades)}")
    return best

if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv)>1 and not sys.argv[1].startswith("--") else "QQQ"
    if "--all" in sys.argv:
        from app_sub.db import db_session
        from sqlalchemy import text
        symbols = ["QQQ","SPY","AAPL","NVDA","MSFT","TSLA","GOOGL","META","AMZN","SMH"]
        for s in symbols:
            try:
                best = perfect_tune(s)
                if best:
                    comment = f"WR {best['wr']:.2f} losers: " + ";".join([l['ai_comment'] for l in best['losers'][:5]])
                    db_session.execute(text("INSERT INTO tuning_results (symbol, mode, trail_pct, min_v_pct, win_rate, total_pnl, notes) VALUES (:s,'kiss_v3',:t,:m,:w,:p,:c)"), {"s":s,"t":best['trail'],"m":best['min_v'],"w":best['wr'],"p":best['total'],"c":comment[:500]})
                    db_session.commit()
                    print(f"SAVED {s} BEST WR {best['wr']*100:.1f}%")
            except Exception as e:
                import traceback; traceback.print_exc()
    else:
        best = perfect_tune(sym)
        if best:
            print(f"\nBEST {sym}: trail={best['trail']} min_v={best['min_v']} WR={best['wr']*100:.1f}% total={best['total']:.1f}% count={best['count']}")
            for l in best['losers'][:5]:
                print(f" LOSER {l['pnl']:.2f}% {l['ai_comment']} gap={l['gap']:.1f}% rsi={l['rsi']:.0f}")
