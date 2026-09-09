"""KISS V5.4 — Transition Anatomy Classification.

RESEARCH ONLY. No orders. No DB writes. No engine changes.

V5.4 takes the clean, event-relative V5.3 transition windows and asks a
simpler question: what kind of transition actually happened?

Primary anatomy classes:
1. EARLY_STRUCTURAL_REVERSAL
2. GRADUAL_DETERIORATION
3. SHARP_ACCELERATION
4. FALSE_REVERSAL_CONTINUATION
5. NO_CLEAN_STRUCTURE_CHANGE
6. MA_TRANSITION_LAGGING

The classification is descriptive. It is NOT a trading rule and does not
claim that the official 30m MA transition is the true market transition.
LONG->SHORT and SHORT->LONG are reported separately.

Timing discipline:
- 30m timestamp is candle START; official state is known at +30m.
- 5m timestamp is candle START; each observation is known at its CLOSE.
- Only exact completed 5m closes in T-60..T+30 are used.
- No future candle is used to manufacture an observation.

V5.4 deliberately avoids ML, prediction scores, RSI rules, optimization,
and engine changes. Its purpose is to discover repeatable transition anatomy
before designing V5.5 recognition logic.
"""
from __future__ import annotations
import argparse
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple
from db import get_db_connection

TREND_WINDOW=20
TREND_BAND=0.002
SWING_LOOKBACK=3
TARGET_OFFSETS=(-60,-45,-30,-15,0,15,30)
DEFAULT_SYMBOLS=["NVDA","AAPL","MSFT","AMZN","TSLA","SPY","QQQ"]


def f(v:Any)->float:
    try:return float(v)
    except:return float("nan")


def dt(v:Any)->datetime:
    if isinstance(v,datetime): return v.replace(tzinfo=None)
    return datetime.fromisoformat(str(v).replace("Z","+00:00").replace("+00:00","")).replace(tzinfo=None)


def load(symbol:str,tf:str,limit:int)->List[Dict[str,Any]]:
    conn,cur=get_db_connection()
    if not conn: raise RuntimeError("Database connection failed")
    try:
        cur.execute("SELECT timestamp,open,high,low,close,volume FROM candles WHERE symbol=%s AND timeframe=%s ORDER BY timestamp ASC LIMIT %s",(symbol,tf,int(limit)))
        out=[]
        for r in cur.fetchall() or []:
            d=dict(r) if isinstance(r,dict) else {"timestamp":r[0],"open":r[1],"high":r[2],"low":r[3],"close":r[4],"volume":r[5]}
            d["timestamp"]=dt(d["timestamp"])
            for k in ("open","high","low","close","volume"): d[k]=f(d[k])
            out.append(d)
        return out
    finally:
        try:cur.close()
        except:pass
        conn.close()


def state(closes:Sequence[float],i:int)->str:
    if i<TREND_WINDOW or i>=len(closes): return "FLAT"
    ma=sum(closes[i-TREND_WINDOW:i])/TREND_WINDOW
    if closes[i]>ma*(1+TREND_BAND): return "LONG"
    if closes[i]<ma*(1-TREND_BAND): return "SHORT"
    return "FLAT"


def transitions(rows:Sequence[Dict[str,Any]])->List[Dict[str,Any]]:
    c=[r["close"] for r in rows];s=[state(c,i) for i in range(len(rows))];out=[]
    for i in range(TREND_WINDOW+1,len(rows)):
        if s[i-1] in ("LONG","SHORT") and s[i] in ("LONG","SHORT") and s[i]!=s[i-1]:
            out.append({"i":i,"from":s[i-1],"to":s[i],"time":rows[i]["timestamp"]+timedelta(minutes=30),"price":rows[i]["close"]})
    return out


def close_index(rows:Sequence[Dict[str,Any]],target:datetime)->Optional[int]:
    for i,r in enumerate(rows):
        if r["timestamp"]+timedelta(minutes=5)==target:return i
    return None


def exact_window(rows:Sequence[Dict[str,Any]],t0:datetime)->Optional[List[Dict[str,Any]]]:
    out=[]
    for off in TARGET_OFFSETS:
        i=close_index(rows,t0+timedelta(minutes=off))
        if i is None:return None
        r=dict(rows[i]);r["offset"]=off;r["close_at"]=r["timestamp"]+timedelta(minutes=5);out.append(r)
    return out


def pct(a:float,b:float)->float:
    if not math.isfinite(a) or a==0:return float("nan")
    return (b/a-1.0)*100.0


def causal_swings(rows:Sequence[Dict[str,Any]],obs_close:datetime)->Tuple[List[int],List[int]]:
    """Swing confirmation uses three completed bars to the right."""
    hs=[];ls=[]
    for i in range(SWING_LOOKBACK,len(rows)-SWING_LOOKBACK):
        known_at=rows[i]["timestamp"]+timedelta(minutes=5*(SWING_LOOKBACK+1))
        if known_at>obs_close:continue
        h=rows[i]["high"];l=rows[i]["low"]
        if h>=max(r["high"] for r in rows[i-SWING_LOOKBACK:i]) and h>=max(r["high"] for r in rows[i+1:i+SWING_LOOKBACK+1]):hs.append(i)
        if l<=min(r["low"] for r in rows[i-SWING_LOOKBACK:i]) and l<=min(r["low"] for r in rows[i+1:i+SWING_LOOKBACK+1]):ls.append(i)
    return hs,ls


def window_structure(rows:Sequence[Dict[str,Any]],win:Sequence[Dict[str,Any]],prior:str)->Dict[str,Any]:
    """Describe confirmed opposite structure without looking beyond each observation."""
    first_close=win[0]["close"];t0=win[4]["close_at"]
    # Use only bars available through T0 for pre-transition structure.
    end_idx=close_index(rows,t0)
    if end_idx is None:return {}
    hs,ls=causal_swings(rows,t0)
    hs=[i for i in hs if rows[i]["timestamp"]+timedelta(minutes=5)<=t0]
    ls=[i for i in ls if rows[i]["timestamp"]+timedelta(minutes=5)<=t0]
    start_idx=close_index(rows,win[0]["close_at"])
    if start_idx is None:return {}
    hs=[i for i in hs if i>=start_idx];ls=[i for i in ls if i>=start_idx]
    if prior=="LONG":
        opp_swings=[i for i in ls if rows[i]["low"]<first_close]
        old_lows=[i for i in ls if i<end_idx]
        break_idx=None
        if old_lows:
            # A bearish break means a completed close below a previously confirmed swing low.
            for j in range(start_idx,end_idx+1):
                if any(rows[j]["close"]<rows[k]["low"] for k in old_lows if k<j):
                    break_idx=j;break
    else:
        opp_swings=[i for i in hs if rows[i]["high"]>first_close]
        old_highs=[i for i in hs if i<end_idx]
        break_idx=None
        if old_highs:
            for j in range(start_idx,end_idx+1):
                if any(rows[j]["close"]>rows[k]["high"] for k in old_highs if k<j):
                    break_idx=j;break
    opp_time=None if not opp_swings else min(rows[i]["timestamp"]+timedelta(minutes=5) for i in opp_swings)
    break_time=None if break_idx is None else rows[break_idx]["timestamp"]+timedelta(minutes=5)
    return {"opposite_swing_before_t0":opp_time,"structure_break_before_t0":break_time}


def anatomy(rows:Sequence[Dict[str,Any]],win:Sequence[Dict[str,Any]],prior:str)->Dict[str,Any]:
    c=[x["close"] for x in win];o=[x["offset"] for x in win]
    base=c[0]
    # Signed movement: positive means movement in the old trend direction.
    signed=[pct(base,x) * (1 if prior=="LONG" else -1) for x in c]
    adverse=[-x for x in signed]
    # Progress = whether each observation is still extending in the old direction.
    progress_count=0
    for a,b in zip(signed,signed[1:]):
        if b>a:progress_count+=1
    adverse_count=sum(1 for x in signed[1:5] if x<0)
    max_adverse=max(0.0,max(-x for x in signed))
    final_signed=signed[-1]
    final30=min(signed[4:])
    first_half=min(signed[:4])
    last30_move=abs(pct(c[3],c[6]))
    total_range=(max(x["high"] for x in win)-min(x["low"] for x in win))/base*100.0
    structure=window_structure(rows,win,prior)
    opp=structure.get("opposite_swing_before_t0")
    brk=structure.get("structure_break_before_t0")
    early_struct=opp is not None and brk is not None and brk<=win[4]["close_at"]
    clear_lag=False
    lag_minutes=None
    if brk is not None:
        lag_minutes=(win[4]["close_at"]-brk).total_seconds()/60.0
        clear_lag=lag_minutes>=15.0
    # A false reversal/continuation is descriptive: meaningful adverse move first,
    # followed by recovery in the old direction by T+30.
    false_cont=(max_adverse>=0.30 and final_signed>=-0.10 and final_signed>final30)
    sharp=(last30_move>=0.50 and max_adverse>=0.50 and last30_move>=max(0.01,abs(pct(c[0],c[3])))*1.25)
    gradual=(adverse_count>=3 and first_half<0 and not sharp)
    no_clean=(not early_struct and max_adverse<0.40 and not sharp and not gradual and not false_cont)

    if clear_lag:
        primary="MA_TRANSITION_LAGGING"
    elif false_cont:
        primary="FALSE_REVERSAL_CONTINUATION"
    elif early_struct:
        primary="EARLY_STRUCTURAL_REVERSAL"
    elif sharp:
        primary="SHARP_ACCELERATION"
    elif gradual:
        primary="GRADUAL_DETERIORATION"
    elif no_clean:
        primary="NO_CLEAN_STRUCTURE_CHANGE"
    else:
        # If the case does not fit a strong class, prefer gradual deterioration
        # when there is measurable adverse movement, otherwise no-clean.
        primary="GRADUAL_DETERIORATION" if max_adverse>=0.25 else "NO_CLEAN_STRUCTURE_CHANGE"

    return {
        "primary":primary,"max_adverse_pct":max_adverse,"signed_t0_pct":signed[4],"signed_tplus30_pct":final_signed,
        "adverse_count_pre_t0":adverse_count,"progress_count":progress_count,
        "last30_move_pct":last30_move,"window_range_pct":total_range,
        "opposite_swing_before_t0":opp,"structure_break_before_t0":brk,
        "ma_lag_minutes":lag_minutes,"ma_lag_flag":clear_lag,
        "false_continuation_flag":false_cont,"sharp_flag":sharp,"gradual_flag":gradual,
    }


def print_case(symbol:str,rows:Sequence[Dict[str,Any]],event:Dict[str,Any],n:int)->Dict[str,Any]:
    win=exact_window(rows,event["time"]);a=anatomy(rows,win,event["from"])
    print(f"\nCASE {n} {symbol} {event['from']}->{event['to']} T0={event['time'].strftime('%Y-%m-%d %H:%M')} official_price={event['price']:.2f}")
    print(f"PRIMARY ANATOMY: {a['primary']}")
    print("ANATOMY METRICS:")
    print(f"  max adverse before/through T0: {a['max_adverse_pct']:.3f}%")
    print(f"  signed move at T0:             {a['signed_t0_pct']:.3f}%")
    print(f"  signed move at T+30:            {a['signed_tplus30_pct']:.3f}%")
    print(f"  adverse observations T-60..T0: {a['adverse_count_pre_t0']}/4")
    print(f"  old-trend progress steps:       {a['progress_count']}/6")
    print(f"  last-30m absolute move:         {a['last30_move_pct']:.3f}%")
    print(f"  total window range:              {a['window_range_pct']:.3f}%")
    print(f"  opposite swing before T0:       {a['opposite_swing_before_t0'] or '--'}")
    print(f"  structure break before T0:       {a['structure_break_before_t0'] or '--'}")
    print(f"  MA lag >=15m flag:               {'YES' if a['ma_lag_flag'] else 'NO'}")
    print("5M PATH T-60..T+30:")
    for r in win:
        print(f"  T{r['offset']:+d} {r['close_at'].strftime('%H:%M')} O={r['open']:.2f} H={r['high']:.2f} L={r['low']:.2f} C={r['close']:.2f}")
    return a


def run(symbols,limit30=10000,limit5=50000,max_cases=10000):
    print("KISS V5.4 TRANSITION ANATOMY CLASSIFICATION — RESEARCH ONLY")
    print("No orders. No DB writes. No engine changes. No prediction scoring.")
    print("Exact causal window: T-60, T-45, T-30, T-15, T0, T+15, T+30.\n")
    stats={};cases=[];known=usable=skipped=0
    for symbol in symbols:
        r30=load(symbol,"30m",limit30);r5=load(symbol,"5m",limit5);ev=transitions(r30)
        print(f"{symbol}: 30m={len(r30)} 5m={len(r5)} transitions={len(ev)}")
        for n,e in enumerate(ev,1):
            known+=1
            if len(cases)>=max_cases:continue
            win=exact_window(r5,e["time"])
            if win is None:
                skipped+=1
                continue
            usable+=1
            a=print_case(symbol,r5,e,n)
            key=e["from"]+"->"+e["to"]
            stats.setdefault(key,{})
            stats[key][a["primary"]]=stats[key].get(a["primary"],0)+1
            cases.append((symbol,e,a))
    print("\n================ V5.4 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {known}")
    print(f"USABLE COMPLETE V5.4 WINDOWS: {usable}")
    print(f"SKIPPED FOR INCOMPLETE 5M COVERAGE: {skipped}")
    print("\nANATOMY BY DIRECTION")
    labels=["EARLY_STRUCTURAL_REVERSAL","GRADUAL_DETERIORATION","SHARP_ACCELERATION","FALSE_REVERSAL_CONTINUATION","NO_CLEAN_STRUCTURE_CHANGE","MA_TRANSITION_LAGGING"]
    for direction in ("LONG->SHORT","SHORT->LONG"):
        total=sum(stats.get(direction,{}).values())
        print(f"\n{direction}: N={total}")
        for label in labels:
            n=stats.get(direction,{}).get(label,0)
            pctv=(100*n/total) if total else 0.0
            print(f"  {label:<31} {n:>3} ({pctv:5.1f}%)")
    print("\nOVERALL ANATOMY")
    total=sum(len(v) for v in stats.values()) if False else len(cases)
    overall={}
    for _,_,a in cases:overall[a["primary"]]=overall.get(a["primary"],0)+1
    for label in labels:
        n=overall.get(label,0);pctv=(100*n/total) if total else 0.0
        print(f"  {label:<31} {n:>3} ({pctv:5.1f}%)")
    print("\nIMPORTANT: V5.4 classifications are research observations, not trading rules.")
    print("Next step is V5.5 only if one or more anatomy patterns repeat reliably.")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--symbols",nargs="+",default=DEFAULT_SYMBOLS)
    p.add_argument("--limit30",type=int,default=10000)
    p.add_argument("--limit5",type=int,default=50000)
    p.add_argument("--max-cases",type=int,default=10000)
    a=p.parse_args();run(a.symbols,a.limit30,a.limit5,a.max_cases)
