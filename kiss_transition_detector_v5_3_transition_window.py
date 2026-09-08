"""KISS V5.3 — Transition Window / Causal Truth Test.

RESEARCH ONLY. No orders. No DB writes. No engine changes.

Purpose: inspect the actual causal 5m behavior immediately around each known
30m LONG<->SHORT transition. V5.2 showed that unconstrained structure searches
could reach unrelated older price structure. V5.3 fixes that by using only a
small event-relative window and recording what was knowable at each completed
5m observation.

For each known official transition T0, examine:
T-60, T-45, T-30, T-15, T0, T+15, T+30 minutes.

At each observation the report records:
- whether the old trend was still progressing
- continuation failure / adverse move
- confirmed opposite swing available causally
- break of the most recent confirmed prior swing structure
- whether price has made an opposite-direction structure change

Important timing rule:
30m timestamps are candle START times; the official state becomes known at
that candle close (+30m). 5m evidence is available only after its candle
closes (+5m). No future bars are used to label an observation.

This is a truth test, not a prediction score and not a trading rule.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple
from db import get_db_connection

TREND_WINDOW=20
TREND_BAND=0.002
SWING_LOOKBACK=3
WINDOW_BEFORE=60
WINDOW_AFTER=30
OBS_STEP=15
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


def causal_swing_indices(rows:Sequence[Dict[str,Any]],obs_close:datetime)->Tuple[List[int],List[int]]:
    hs=[];ls=[]
    for i in range(SWING_LOOKBACK,len(rows)-SWING_LOOKBACK):
        # Swing at i is known only after its 3 right bars have closed.
        known_at=rows[i]["timestamp"]+timedelta(minutes=5*(SWING_LOOKBACK+1))
        if known_at>obs_close: continue
        h=rows[i]["high"]; l=rows[i]["low"]
        if h>=max(r["high"] for r in rows[i-SWING_LOOKBACK:i]) and h>=max(r["high"] for r in rows[i+1:i+SWING_LOOKBACK+1]): hs.append(i)
        if l<=min(r["low"] for r in rows[i-SWING_LOOKBACK:i]) and l<=min(r["low"] for r in rows[i+1:i+SWING_LOOKBACK+1]): ls.append(i)
    return hs,ls


def nearest_5m_close(rows:Sequence[Dict[str,Any]],target:datetime)->Optional[int]:
    best=None; bestdiff=None
    for i,r in enumerate(rows):
        close_at=r["timestamp"]+timedelta(minutes=5)
        if close_at<=target:
            d=target-close_at
            if bestdiff is None or d<bestdiff: best=i; bestdiff=d
    return best


def observation(rows:Sequence[Dict[str,Any]],obs_close:datetime,prior:str)->Dict[str,Any]:
    idx=nearest_5m_close(rows,obs_close)
    if idx is None:return {}
    hs,ls=causal_swing_indices(rows,obs_close)
    hs=[i for i in hs if i<=idx]; ls=[i for i in ls if i<=idx]
    r=rows[idx]
    # Work only from the immediately preceding 60 minutes, preventing V5.2's old-history leakage.
    start=max(0,idx-12)
    recent=rows[start:idx+1]
    if not recent:return {}
    if prior=="LONG":
        prog=recent[-1]["high"]>max(x["high"] for x in recent[:-1]) if len(recent)>1 else False
        adverse=recent[-1]["close"]<recent[0]["close"]
        opp=[i for i in hs if i>=start and rows[i]["high"]<max(x["high"] for x in recent)]
        prior_low=ls[-1] if ls else None
        structure_break=prior_low is not None and r["close"]<rows[prior_low]["low"]
        opposite_structure=structure_break or (bool(opp) and rows[opp[-1]]["high"]<max(x["high"] for x in recent))
    else:
        prog=recent[-1]["low"]<min(x["low"] for x in recent[:-1]) if len(recent)>1 else False
        adverse=recent[-1]["close"]>recent[0]["close"]
        opp=[i for i in ls if i>=start and rows[i]["low"]>min(x["low"] for x in recent)]
        prior_high=hs[-1] if hs else None
        structure_break=prior_high is not None and r["close"]>rows[prior_high]["high"]
        opposite_structure=structure_break or (bool(opp) and rows[opp[-1]]["low"]>min(x["low"] for x in recent))
    return {"idx":idx,"time":r["timestamp"]+timedelta(minutes=5),"close":r["close"],"progress":prog,"adverse":adverse,"confirmed_opposite_swing":bool(opp),"structure_break":structure_break,"opposite_structure":opposite_structure,"highs":hs,"lows":ls}


def fmt_bool(v:bool)->str:return "YES" if v else "NO"


def print_case(symbol:str,rows5:Sequence[Dict[str,Any]],event:Dict[str,Any],n:int)->None:
    t=event["time"]; prior=event["from"]; target_offsets=[-60,-45,-30,-15,0,15,30]
    print(f"\nCASE {n} {symbol} {prior}->{event['to']} T0={t.strftime('%Y-%m-%d %H:%M')} official_price={event['price']:.2f}")
    print("CAUSAL TRANSITION WINDOW (all evidence is known only after the listed observation closes)")
    print("offset | observation | price | progress | adverse | opp_swing | structure_break | opposite_structure")
    print("-------|-------------|-------|----------|---------|-----------|-----------------|-------------------")
    for off in target_offsets:
        o=observation(rows5,t+timedelta(minutes=off),prior)
        if not o:
            print(f"{off:>+5} | -- | -- | -- | -- | -- | -- | --")
            continue
        print(f"{off:>+5} | {o['time'].strftime('%H:%M')} | {o['close']:.2f} | {fmt_bool(o['progress']):>8} | {fmt_bool(o['adverse']):>7} | {fmt_bool(o['confirmed_opposite_swing']):>9} | {fmt_bool(o['structure_break']):>15} | {fmt_bool(o['opposite_structure']):>18}")
    # Exact ±60m path, compact, to inspect the causal tape without dumping unrelated history.
    lo=t-timedelta(minutes=60); hi=t+timedelta(minutes=30)
    print("5M CAUSAL PATH T-60..T+30")
    for r in rows5:
        close_at=r["timestamp"]+timedelta(minutes=5)
        if lo<=close_at<=hi:
            print(f"  {close_at.strftime('%H:%M')} O={r['open']:.2f} H={r['high']:.2f} L={r['low']:.2f} C={r['close']:.2f}")


def run(symbols,limit30=10000,limit5=50000,max_cases=10):
    print("KISS V5.3 TRANSITION WINDOW / CAUSAL TRUTH TEST — RESEARCH ONLY")
    print("No orders. No DB writes. No engine changes.")
    print("Window: T-60, T-45, T-30, T-15, T0, T+15, T+30. Completed 5m candles only.\n")
    total=0
    for symbol in symbols:
        r30=load(symbol,"30m",limit30); r5=load(symbol,"5m",limit5); ev=transitions(r30)
        print(f"{symbol}: 30m={len(r30)} 5m={len(r5)} transitions={len(ev)}")
        for n,e in enumerate(ev[:max_cases],1): print_case(symbol,r5,e,n)
        total+=len(ev)
    print(f"\nTOTAL KNOWN TRANSITIONS: {total}")
    print("V5.3 intentionally does not score predictions or change the trading engine.")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--symbols",nargs="+",default=DEFAULT_SYMBOLS)
    p.add_argument("--limit30",type=int,default=10000)
    p.add_argument("--limit5",type=int,default=50000)
    p.add_argument("--max-cases",type=int,default=10)
    a=p.parse_args(); run(a.symbols,a.limit30,a.limit5,a.max_cases)
