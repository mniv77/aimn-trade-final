"""KISS V5.5 — Earliest Human Recognition / Causal Transition.

RESEARCH ONLY. No orders. No DB writes. No engine changes.

V5.5 asks a causal question at every completed 5m candle around a known
30m directional transition:

  Is the old trend still behaving normally?
  Has continuation failed?
  Has the attempted recovery failed?
  Has opposite structure appeared or broken?
  When is the earliest reasonable recognition point?

This is deliberately descriptive. It does NOT predict the future and does
not use the official 30m MA transition as the definition of truth.

Timing discipline:
- 30m timestamp is candle START; official state is known at candle CLOSE.
- 5m timestamp is candle START; evidence is known at candle CLOSE.
- All observations are causal: a candle may only use information available
  at its own close.
- Swing confirmation uses SWING_LOOKBACK completed bars on each side.
- The known 30m transition is only the reference event for the study.

V5.5 outputs a timeline of four human-readable states:
  NORMAL -> WARNING -> CHARACTER_CHANGE -> CONFIRMED_TRANSITION

It also reports the earliest candle for each state, the minutes before the
official transition, and the price path. No trading threshold is implied.
"""
from __future__ import annotations
import argparse, math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence
from db import get_db_connection

TREND_WINDOW=20
TREND_BAND=0.002
SWING_LOOKBACK=3
TARGET_OFFSETS=(-60,-45,-30,-15,0,15,30)
LOOKBACK_MINUTES=120
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
    if i<TREND_WINDOW or i>=len(closes):return "FLAT"
    ma=sum(closes[i-TREND_WINDOW:i])/TREND_WINDOW
    if closes[i]>ma*(1+TREND_BAND):return "LONG"
    if closes[i]<ma*(1-TREND_BAND):return "SHORT"
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

def signed_move(base:float,price:float,prior:str)->float:
    p=(price/base-1)*100
    return p if prior=="LONG" else -p

def causal_swings(rows:Sequence[Dict[str,Any]],obs_close:datetime)->tuple[List[int],List[int]]:
    hs=[];ls=[]
    for i in range(SWING_LOOKBACK,len(rows)-SWING_LOOKBACK):
        known_at=rows[i]["timestamp"]+timedelta(minutes=5*(SWING_LOOKBACK+1))
        if known_at>obs_close:continue
        h=rows[i]["high"];l=rows[i]["low"]
        if h>=max(x["high"] for x in rows[i-SWING_LOOKBACK:i]) and h>=max(x["high"] for x in rows[i+1:i+SWING_LOOKBACK+1]):hs.append(i)
        if l<=min(x["low"] for x in rows[i-SWING_LOOKBACK:i]) and l<=min(x["low"] for x in rows[i+1:i+SWING_LOOKBACK+1]):ls.append(i)
    return hs,ls

def features_at(rows:Sequence[Dict[str,Any]],idx:int,prior:str)->Dict[str,Any]:
    """Causal features available at this completed 5m candle."""
    r=rows[idx]; base_idx=max(0,idx-12);base=rows[base_idx]["close"]
    recent=rows[base_idx:idx+1]
    closes=[x["close"] for x in recent]
    sm=[signed_move(base,x["close"],prior) for x in recent]
    progress=sum(1 for a,b in zip(sm,sm[1:]) if b>a)
    adverse=sum(1 for x in sm[1:] if x<0)
    max_adv=max(0,-min(sm)) if sm else 0
    # Immediate continuation failure: latest completed candle moves against
    # the old direction after the preceding candle had been progressing.
    prev_progress=len(sm)>=2 and sm[-2]>sm[0]
    latest_against=sm[-1]<sm[-2] if len(sm)>=2 else False
    continuation_failed=latest_against and (prev_progress or sm[-2]>=0)
    # Recovery failure: after an adverse move, the latest candle fails to
    # recover toward the old direction and remains below the prior local peak.
    recovery_failed=False
    if len(sm)>=4 and min(sm[:-1])<0:
        recovery=max(sm[:-1])
        recovery_failed=sm[-1]<recovery and sm[-1]<0
    hs,ls=causal_swings(rows,r["timestamp"]+timedelta(minutes=5))
    start=max(0,idx-12)
    hs=[i for i in hs if start<=i<idx];ls=[i for i in ls if start<=i<idx]
    opposite_swing=False;structure_break=False
    if prior=="LONG":
        opposite_swing=any(rows[i]["low"]<base for i in ls)
        old_lows=[i for i in ls if i<idx]
        structure_break=any(r["close"]<rows[k]["low"] for k in old_lows if k<idx)
    else:
        opposite_swing=any(rows[i]["high"]>base for i in hs)
        old_highs=[i for i in hs if i<idx]
        structure_break=any(r["close"]>rows[k]["high"] for k in old_highs if k<idx)
    return {"signed":sm[-1],"progress":progress,"adverse":adverse,"max_adverse":max_adv,
            "continuation_failed":continuation_failed,"recovery_failed":recovery_failed,
            "opposite_swing":opposite_swing,"structure_break":structure_break}

def classify_timeline(rows:Sequence[Dict[str,Any]],event:Dict[str,Any])->List[Dict[str,Any]]:
    t0=event["time"]; prior=event["from"]
    start=close_index(rows,t0-timedelta(minutes=LOOKBACK_MINUTES))
    end=close_index(rows,t0+timedelta(minutes=30))
    if start is None or end is None:return []
    out=[];seen_warning=seen_change=seen_confirm=False
    for idx in range(start,end+1):
        obs=rows[idx]["timestamp"]+timedelta(minutes=5)
        x=features_at(rows,idx,prior)
        # Evidence hierarchy. We deliberately require causal persistence rather
        # than treating one opposite candle as a transition.
        warning=x["continuation_failed"] and x["adverse"]>=1
        change=(x["recovery_failed"] or x["opposite_swing"]) and x["adverse"]>=1
        confirm=x["structure_break"]
        if warning and not seen_warning:
            seen_warning=True;out.append({"stage":"WARNING","time":obs,"idx":idx,"minutes_to_t0":(t0-obs).total_seconds()/60,"reason":"continuation_failed"})
        if change and not seen_change:
            seen_change=True;out.append({"stage":"CHARACTER_CHANGE","time":obs,"idx":idx,"minutes_to_t0":(t0-obs).total_seconds()/60,"reason":"recovery_failed_or_opposite_structure"})
        if confirm and not seen_confirm:
            seen_confirm=True;out.append({"stage":"CONFIRMED_TRANSITION","time":obs,"idx":idx,"minutes_to_t0":(t0-obs).total_seconds()/60,"reason":"structure_break"})
    return out

def print_case(symbol:str,rows:Sequence[Dict[str,Any]],event:Dict[str,Any],n:int)->Optional[Dict[str,Any]]:
    win=exact_window(rows,event["time"])
    timeline=classify_timeline(rows,event)
    if win is None or not timeline:return None
    print(f"\nCASE {n} {symbol} {event['from']}->{event['to']} T0={event['time'].strftime('%Y-%m-%d %H:%M')} official_price={event['price']:.2f}")
    print("EARLIEST CAUSAL RECOGNITION:")
    for s in ("WARNING","CHARACTER_CHANGE","CONFIRMED_TRANSITION"):
        z=next((x for x in timeline if x["stage"]==s),None)
        if z:print(f"  {s:<21} {z['time'].strftime('%Y-%m-%d %H:%M')}  ({z['minutes_to_t0']:+.0f}m)  {z['reason']}")
        else:print(f"  {s:<21} --")
    print("CAUSAL TIMELINE:")
    for z in timeline:print(f"  {z['time'].strftime('%H:%M')}  {z['stage']:<21} {z['reason']}")
    print("5M PATH T-60..T+30:")
    for r in win:print(f"  T{r['offset']:+d} {r['close_at'].strftime('%H:%M')} O={r['open']:.2f} H={r['high']:.2f} L={r['low']:.2f} C={r['close']:.2f}")
    return {"direction":event["from"]+"->"+event["to"],"timeline":timeline}

def run(symbols,limit30=10000,limit5=50000):
    print("KISS V5.5 EARLIEST HUMAN RECOGNITION / CAUSAL TRANSITION — RESEARCH ONLY")
    print("No orders. No DB writes. No engine changes. No prediction scoring.")
    print("Causal evidence is evaluated only at completed 5m closes.\n")
    known=usable=skipped=0;allcases=[]
    for symbol in symbols:
        r30=load(symbol,"30m",limit30);r5=load(symbol,"5m",limit5);ev=transitions(r30)
        print(f"{symbol}: 30m={len(r30)} 5m={len(r5)} transitions={len(ev)}")
        for n,e in enumerate(ev,1):
            known+=1
            if exact_window(r5,e["time"]) is None:skipped+=1;continue
            x=print_case(symbol,r5,e,n)
            if x:usable+=1;allcases.append(x)
    print("\n================ V5.5 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {known}")
    print(f"USABLE COMPLETE V5.5 WINDOWS: {usable}")
    print(f"SKIPPED FOR INCOMPLETE 5M COVERAGE: {skipped}")
    for direction in ("LONG->SHORT","SHORT->LONG"):
        subset=[x for x in allcases if x["direction"]==direction]
        print(f"\n{direction}: N={len(subset)}")
        for stage in ("WARNING","CHARACTER_CHANGE","CONFIRMED_TRANSITION"):
            vals=[]
            for x in subset:
                z=next((q for q in x["timeline"] if q["stage"]==stage),None)
                if z:vals.append(z["minutes_to_t0"])
            if vals:
                vals.sort();print(f"  {stage:<21} N={len(vals):>2}  mean={sum(vals)/len(vals):.1f}m  median={vals[len(vals)//2]:.1f}m  earliest={max(vals):.1f}m")
            else:print(f"  {stage:<21} N=0")
    print("\nV5.5 is a causal research timeline, not a trading rule.")

if __name__=="__main__":
    ap=argparse.ArgumentParser(description="KISS V5.5 causal transition timeline")
    ap.add_argument("--symbols",nargs="+",default=DEFAULT_SYMBOLS)
    ap.add_argument("--limit30",type=int,default=10000)
    ap.add_argument("--limit5",type=int,default=50000)
    args=ap.parse_args();run(args.symbols,args.limit30,args.limit5)
