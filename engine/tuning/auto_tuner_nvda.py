# /home/MeirNiv/aimn-trade-final/engine/tuning/auto_tuner_nvda.py
# NVDA-Specific Tuner — Sharp V-Peak strategy
import sys
sys.path.insert(0, '/home/MeirNiv/aimn-trade-final')
from engine.tuning.candle_fetcher import fetch_yahoo_candles
from db import get_db_connection
from datetime import datetime
from itertools import product

NVDA_DEFAULT = {
    'rsi_len_options'    : [10, 20, 30],
    'rsi_entry_options'  : [15, 20, 25, 30],
    'macd_fast'          : 8,
    'macd_slow'          : 17,
    'macd_sig'           : 5,
    'stop_loss_options'  : [0.2, 0.3, 0.5],
    'trail_start_options': [0.2, 0.3, 0.5],
    'trail_pct'          : 0.05,
    'rsi_exit_options'   : [60, 65, 70],
    'init_profit_options': [0.1, 0.2, 0.3],
    'decay_start_options': [0.25, 0.5, 1.0],
    'decay_rate'         : 1.0,
    'time_stop_hours'    : 0.5,
    'bars'               : 8000,
    'min_trades'         : 10,
}

BAR_MINUTES_MAP = {"1m":1,"5m":5,"15m":15,"30m":30}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def calc_rsi_real(highs, lows, closes, i, lookback):
    start = max(0, i - lookback)
    hi = max(highs[start:i+1])
    lo = min(lows[start:i+1])
    if hi == lo:
        return None
    return max(0.0, min(100.0, ((closes[i] - lo) / (hi - lo)) * 100))

def calc_macd_series(closes, fast, slow, sig):
    n = len(closes)
    kf = 2/(fast+1); ks = 2/(slow+1); kg = 2/(sig+1)
    ef = es = closes[0]
    ml = [0.0]*n
    for i in range(1,n):
        ef = closes[i]*kf + ef*(1-kf)
        es = closes[i]*ks + es*(1-ks)
        ml[i] = ef - es
    sv = ml[slow]; sl = [0.0]*n
    for i in range(slow,n):
        sv = ml[i]*kg + sv*(1-kg)
        sl[i] = sv
    return ml, sl

def backtest_nvda(highs, lows, closes, direction, params, bar_minutes):
    rsi_len=params["rsi_len"]; rsi_entry=params["rsi_entry"]
    stop_loss=params["stop_loss"]; trail_start=params["trail_start"]
    trail_pct=params.get("trail_pct",0.05); rsi_exit=params["rsi_exit"]
    init_profit=params["init_profit"]; decay_start=params["decay_start"]
    decay_rate=params.get("decay_rate",1.0); min_trades=params["min_trades"]
    time_stop=params.get("time_stop_hours",0.5)
    macd_fast=params["macd_fast"]; macd_slow=params["macd_slow"]; macd_sig=params["macd_sig"]
    n=len(closes)
    ml,_=calc_macd_series(closes,macd_fast,macd_slow,macd_sig)
    trades=wins=0; total_pnl=0.0; in_trade=False
    entry_price=peak_profit=0.0; entry_bar=0; total_dur=0.0
    start_bar=max(rsi_len,macd_slow+macd_sig)+4
    for i in range(start_bar,n-1):
        if not in_trade:
            rsi=calc_rsi_real(highs,lows,closes,i,rsi_len)
            if rsi is None: continue
            rsi_prev=calc_rsi_real(highs,lows,closes,i-1,rsi_len) or rsi
            if direction=="LONG":
                rsi_signal=rsi<=rsi_entry; rsi_bouncing=rsi>rsi_prev
                macd_rising=ml[i]>ml[i-1]
                dp=(closes[i-4]-closes[i-2])/closes[i-4]*100 if closes[i-4]>0 else 0
                tb=closes[i-2]<closes[i-3]<closes[i-4]
                b1up=closes[i-1]>closes[i-2]
                b2up=closes[i]>closes[i-1]
                vb=(dp>=0.5) and tb and b1up and b2up
                sd=closes[i-1]<closes[i-2]<closes[i-3]
                ms=(closes[i-2]-closes[i-1])<(closes[i-3]-closes[i-2])
                fu=closes[i]>closes[i-1]
                sr=sd and ms and fu
                entry_cond=rsi_signal and (vb or sr or (macd_rising and rsi_bouncing))
            else:
                rsi_signal=rsi>=(100-rsi_entry); rsi_bouncing=rsi<rsi_prev
                macd_falling=ml[i]<ml[i-1]
                rp=(closes[i-2]-closes[i-4])/closes[i-4]*100 if closes[i-4]>0 else 0
                tt=closes[i-2]>closes[i-3]>closes[i-4]
                b1dn=closes[i-1]<closes[i-2]
                b2dn=closes[i]<closes[i-1]
                vt=(rp>=0.5) and tt and b1dn and b2dn
                su=closes[i-1]>closes[i-2]>closes[i-3]
                ms=(closes[i-1]-closes[i-2])<(closes[i-2]-closes[i-3])
                fd=closes[i]<closes[i-1]
                sr=su and ms and fd
                entry_cond=rsi_signal and (vt or sr or (macd_falling and rsi_bouncing))
            if entry_cond:
                in_trade=True; entry_price=closes[i]
                peak_profit=-999.0; entry_bar=i
        else:
            pnl=(closes[i]-entry_price)/entry_price*100 if direction=="LONG" else (entry_price-closes[i])/entry_price*100
            peak_profit=max(peak_profit,pnl)
            dur=(i-entry_bar)*bar_minutes/60.0
            gate=max(0.0,init_profit-(dur-decay_start)*decay_rate) if dur>=decay_start else init_profit
            ex=None
            if pnl<=-stop_loss: ex="STOP"
            elif peak_profit>=trail_start and pnl<=peak_profit*(1-trail_pct): ex="TRAIL"
            if not ex and pnl>=gate:
                r=calc_rsi_real(highs,lows,closes,i,rsi_len)
                if r and ((direction=="LONG" and r>=rsi_exit) or (direction=="SHORT" and r<=(100-rsi_exit))): ex="RSI"
            if not ex and dur>decay_start and pnl>0 and pnl>=gate: ex="DECAY"
            if not ex and dur>=time_stop and pnl<0: ex="TIME-STOP"
            if ex:
                trades+=1; total_pnl+=pnl; total_dur+=dur
                if pnl>0: wins+=1
                in_trade=False; peak_profit=-999.0
    if trades<min_trades: return None
    days=(n*bar_minutes)/(60*24)
    return {"trades":trades,"wins":wins,"win_rate":round(wins/trades*100,1),
            "total_pnl":round(total_pnl,4),"profit_per_day":round(total_pnl/days,4) if days>0 else 0}

def tune_nvda(direction="LONG", timeframe="5m"):
    cfg=NVDA_DEFAULT.copy()
    bm=BAR_MINUTES_MAP.get(timeframe,5)
    log(f"NVDA TUNER: {direction} [{timeframe}]")
    candles=fetch_yahoo_candles("NVDA",timeframe,limit=cfg["bars"])
    if not candles or len(candles)<200:
        log("NOT ENOUGH CANDLES"); return
    highs=[c["high"] for c in candles]
    lows=[c["low"] for c in candles]
    closes=[c["close"] for c in candles]
    n=len(closes); split=int(n*0.7)  # 70% train
    log(f"Total:{n} Train:{split} Test:{n-split}")
    best_score=-999; best_params=None; best_train=None
    grid=list(product(cfg["rsi_len_options"],cfg["rsi_entry_options"],
        cfg["stop_loss_options"],cfg["trail_start_options"],
        cfg["rsi_exit_options"],cfg["init_profit_options"],cfg["decay_start_options"]))
    log(f"Grid:{len(grid)} combos")
    for combo in grid:
        rl,re,sl,ts,rx,ip,ds=combo
        p={"rsi_len":rl,"rsi_entry":re,"stop_loss":sl,"trail_start":ts,
           "trail_pct":cfg["trail_pct"],"rsi_exit":rx,"init_profit":ip,
           "decay_start":ds,"decay_rate":cfg["decay_rate"],
           "macd_fast":cfg["macd_fast"],"macd_slow":cfg["macd_slow"],
           "macd_sig":cfg["macd_sig"],"min_trades":cfg["min_trades"],
           "time_stop_hours":cfg["time_stop_hours"]}
        tr=backtest_nvda(highs[:split],lows[:split],closes[:split],direction,p,bm)
        if not tr: continue
        if tr["profit_per_day"]>best_score:
            best_score=tr["profit_per_day"]; best_params=p; best_train=tr
    if not best_params:
        log("NO VALID PARAMS"); return
    log(f"TRAIN: PnL={best_train['total_pnl']}% WR={best_train['win_rate']}% trades={best_train['trades']}")
    test=backtest_nvda(highs[split:],lows[split:],closes[split:],direction,best_params,bm)
    if not test or test["total_pnl"]<=-1.0:
        log("TEST NEGATIVE — NOT SAVED"); return
    if test["total_pnl"] < 0:
        log(f"TEST slightly negative {test['total_pnl']}% — saving anyway (train was strong)")
    log(f"TEST: PnL={test['total_pnl']}% WR={test['win_rate']}% trades={test['trades']}")
    conn,cursor=get_db_connection()
    try:
        cursor.execute("SELECT sp.id FROM strategy_params sp JOIN broker_products bp ON sp.broker_product_id=bp.id WHERE bp.local_ticker='NVDA' AND sp.direction=%s AND sp.candle_time=%s AND sp.active=1 LIMIT 1",(direction,timeframe))
        row=cursor.fetchone()
        if row:
            cursor.execute("UPDATE strategy_params SET rsi_len=%s,rsi_entry=%s,stop_loss=%s,trailing_start=%s,trailing_drop=%s,rsi_exit=%s,init_profit=%s,decay_start=%s,decay_rate=%s,pl_pct=%s,last_tuned=NOW() WHERE id=%s",
                (best_params["rsi_len"],best_params["rsi_entry"],best_params["stop_loss"],
                 best_params["trail_start"],best_params["trail_pct"],best_params["rsi_exit"],
                 best_params["init_profit"],best_params["decay_start"],best_params["decay_rate"],
                 test["total_pnl"],row["id"]))
            log(f"SAVED id={row['id']}")
        conn.commit()
    except Exception as e:
        log(f"DB ERROR:{e}")
    finally:
        cursor.close(); conn.close()

if __name__=="__main__":
    for d in ["LONG","SHORT"]:
        for tf in ["1m","5m"]:
            tune_nvda(d,tf)
