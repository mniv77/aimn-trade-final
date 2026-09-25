"""KISS V5.2 — Structure Anatomy / Truth Test.

RESEARCH ONLY. No orders. No DB writes. No engine changes.

Purpose: stop trying to detect the transition and first inspect what the
raw 5m price structure actually looks like around known 30m transitions.
This is a truth/measurement tool, not a trading detector.

For each known LONG->SHORT or SHORT->LONG transition it prints:
- the official 30m transition time
- a compact 5m OHLC path around the event
- confirmed swing highs/lows available causally at each observation
- simple structural landmarks (old extreme, first adverse move, first
  opposite swing, break of prior swing)
- whether the intuitive sequence actually exists and its timestamps

The critical rule: a swing is only known after SWING_LOOKBACK bars to its
right have completed. No future-complete hindsight labels are used.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence
from db import get_db_connection

TREND_WINDOW=20
TREND_BAND=0.002
SWING_LOOKBACK=3
WINDOW_BEFORE=120
WINDOW_AFTER=180
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
    c=[r["close"] for r in rows]; s=[state(c,i) for i in range(len(rows))]; out=[]
    for i in range(TREND_WINDOW+1,len(rows)):
        if s[i-1] in ("LONG","SHORT") and s[i] in ("LONG","SHORT") and s[i]!=s[i-1]:
            out.append({"i":i,"from":s[i-1],"to":s[i],"time":rows[i]["timestamp"]+timedelta(minutes=30),"price":rows[i]["close"]})
    return out

def local_high(rows:Sequence[Dict[str,Any]],i:int)->bool:
    if i<SWING_LOOKBACK or i+SWING_LOOKBACK>=len(rows):return False
    x=rows[i]["high"]
    return x>=max(r["high"] for r in rows[i-SWING_LOOKBACK:i]) and x>=max(r["high"] for r in rows[i+1:i+SWING_LOOKBACK+1])

def local_low(rows:Sequence[Dict[str,Any]],i:int)->bool:
    if i<SWING_LOOKBACK or i+SWING_LOOKBACK>=len(rows):return False
    x=rows[i]["low"]
    return x<=min(r["low"] for r in rows[i-SWING_LOOKBACK:i]) and x<=min(r["low"] for r in rows[i+1:i+SWING_LOOKBACK+1])

def causal_swings(rows:Sequence[Dict[str,Any]],obs:datetime):
    # A swing at i is observable at start(i)+5m only after its right bars close.
    hs=[];ls=[]
    for i,r in enumerate(rows):
        if r["timestamp"]+timedelta(minutes=5+5*SWING_LOOKBACK)>obs: continue
        if local_high(rows,i):hs.append(i)
        if local_low(rows,i):ls.append(i)
    return hs,ls

def pct(a,b):
    return (b/a-1)*100 if a and a==a else float("nan")

def anatomy(rows:Sequence[Dict[str,Any]],event:Dict[str,Any])->Dict[str,Any]:
    t=event["time"]; prior=event["from"]
    w=[r for r in rows if t-timedelta(minutes=WINDOW_BEFORE)<=r["timestamp"]+timedelta(minutes=5)<=t+timedelta(minutes=WINDOW_AFTER)]
    if not w:return {}
    hs,ls=causal_swings(w,t)
    c=[r["close"] for r in w];h=[r["high"] for r in w];l=[r["low"] for r in w]
    # These are descriptive landmarks, deliberately not a prediction score.
    if prior=="LONG":
        ext=max(range(len(w)),key=lambda i:h[i])
        adverse=next((i for i in range(ext+1,len(w)) if c[i]<h[ext]),None)
        opp=[i for i in hs if i>(adverse if adverse is not None else -1) and h[i]<h[ext]]
        opps=opp[0] if opp else None
        old_lows=[i for i in ls if i<ext]
        old_low=old_lows[-1] if old_lows else None
        br=next((i for i in range((opps+1 if opps is not None else 0),len(w)) if old_low is not None and c[i]<l[old_low]),None)
        return {"ext":ext,"adverse":adverse,"opposite_swing":opps,"old_structure":old_low,"break":br,"highs":hs,"lows":ls}
    ext=min(range(len(w)),key=lambda i:l[i])
    adverse=next((i for i in range(ext+1,len(w)) if c[i]>l[ext]),None)
    opp=[i for i in ls if i>(adverse if adverse is not None else -1) and l[i]>l[ext]]
    opps=opp[0] if opp else None
    old_highs=[i for i in hs if i<ext]
    old_high=old_highs[-1] if old_highs else None
    br=next((i for i in range((opps+1 if opps is not None else 0),len(w)) if old_high is not None and c[i]>h[old_high]),None)
    return {"ext":ext,"adverse":adverse,"opposite_swing":opps,"old_structure":old_high,"break":br,"highs":hs,"lows":ls}

def fmt_time(rows,i): return rows[i]["timestamp"].strftime("%m-%d %H:%M") if i is not None else "--"

def dump_case(symbol,rows5,event,n):
    a=anatomy(rows5,event)
    if not a:return
    t=event["time"]
    print(f"\nCASE {n} {symbol} {event['from']}->{event['to']} official={t} price={event['price']:.2f}")
    print("LANDMARKS (causal, descriptive only)")
    for k in ("ext","adverse","opposite_swing","old_structure","break"):
        i=a.get(k); label={"ext":"extreme","adverse":"first adverse close","opposite_swing":"first opposite confirmed swing","old_structure":"prior structure","break":"break of prior structure"}[k]
        print(f"  {label:31s}: {fmt_time(rows5,i)}" + (f" close={rows5[i]['close']:.2f}" if i is not None else ""))
    print(f"  confirmed highs before event: {len([i for i in a['highs'] if rows5[i]['timestamp']+timedelta(minutes=5)<=t])}")
    print(f"  confirmed lows  before event: {len([i for i in a['lows'] if rows5[i]['timestamp']+timedelta(minutes=5)<=t])}")
    start=max(0,next((i for i,r in enumerate(rows5) if r["timestamp"]+timedelta(minutes=5)>=t-timedelta(minutes=30)),0))
    end=min(len(rows5),next((i for i,r in enumerate(rows5) if r["timestamp"]+timedelta(minutes=5)>t+timedelta(minutes=30)),len(rows5)))
    print("5M PATH ±30M")
    for i in range(start,end):
        r=rows5[i]; mark=[]
        for k in ("ext","adverse","opposite_swing","old_structure","break"):
            if a.get(k)==i:mark.append(k.upper())
        print(f"  {r['timestamp'].strftime('%m-%d %H:%M')} O={r['open']:.2f} H={r['high']:.2f} L={r['low']:.2f} C={r['close']:.2f} {' '.join(mark)}")

def run(symbols,limit30=10000,limit5=50000):
    print("KISS V5.2 STRUCTURE ANATOMY / TRUTH TEST — RESEARCH ONLY")
    print("No orders. No DB writes. No engine changes.")
    print("Purpose: observe real 5m structure around known 30m transitions before designing another detector.\n")
    total=0
    for symbol in symbols:
        r30=load(symbol,"30m",limit30); r5=load(symbol,"5m",limit5); ev=transitions(r30)
        print(f"{symbol}: 30m={len(r30)} 5m={len(r5)} transitions={len(ev)}")
        # Show every transition if small; otherwise first 10 for tractable output.
        for n,e in enumerate(ev[:10],1): dump_case(symbol,r5,e,n)
        total+=len(ev)
    print(f"\nTOTAL KNOWN TRANSITIONS: {total}")
    print("This run intentionally does NOT score accuracy or create a trading rule.")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--symbols",nargs="+",default=DEFAULT_SYMBOLS)
    p.add_argument("--limit30",type=int,default=10000)
    p.add_argument("--limit5",type=int,default=50000)
    a=p.parse_args(); run(a.symbols,a.limit30,a.limit5)
