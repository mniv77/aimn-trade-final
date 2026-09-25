"""KISS Transition Detector V3 — Character Change, research only."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any, Dict, List, Optional, Sequence, Tuple
from db import get_db_connection

TREND_WINDOW=20
TREND_BAND=0.002
MIN_5M_HISTORY=20
LOOKBACK_MINUTES=90
NEGATIVE_HORIZON_MINUTES=60
DEFAULT_SYMBOLS=["NVDA","AAPL","MSFT","AMZN","TSLA","SPY","QQQ"]

def num(v:Any)->float:
    try:return float(v)
    except (TypeError,ValueError):return float("nan")

def ts(v:Any)->datetime:
    if isinstance(v,datetime):return v.replace(tzinfo=None)
    return datetime.fromisoformat(str(v).replace("Z","+").replace("+00:00","")).replace(tzinfo=None)

def load(symbol:str,timeframe:str,limit:int)->List[Dict[str,Any]]:
    conn,cur=get_db_connection()
    if not conn: raise RuntimeError("Database connection failed")
    try:
        cur.execute("""SELECT timestamp, open, high, low, close, volume FROM candles WHERE symbol=%s AND timeframe=%s ORDER BY timestamp ASC LIMIT %s""",(symbol,timeframe,int(limit)))
        rows=cur.fetchall() or []; out=[]
        for r in rows:
            d=dict(r) if isinstance(r,dict) else {"timestamp":r[0],"open":r[1],"high":r[2],"low":r[3],"close":r[4],"volume":r[5]}
            d["timestamp"]=ts(d["timestamp"])
            for k in ("open","high","low","close","volume"): d[k]=num(d[k])
            out.append(d)
        return out
    finally:
        try:cur.close()
        except Exception:pass
        conn.close()

def market_state(closes:Sequence[float],idx:int)->str:
    if idx<TREND_WINDOW or idx>=len(closes):return "FLAT"
    ma=sum(closes[idx-TREND_WINDOW:idx])/TREND_WINDOW
    if closes[idx]>ma*(1+TREND_BAND):return "LONG"
    if closes[idx]<ma*(1-TREND_BAND):return "SHORT"
    return "FLAT"

def opposite(s:str)->str:return "SHORT" if s=="LONG" else "LONG"

def direct_transitions(rows30:Sequence[Dict[str,Any]])->List[Dict[str,Any]]:
    closes=[r["close"] for r in rows30]; states=[market_state(closes,i) for i in range(len(rows30))]; out=[]
    for i in range(TREND_WINDOW+1,len(rows30)):
        a,b=states[i-1],states[i]
        if a in ("LONG","SHORT") and b==opposite(a):
            out.append({"index":i,"known_time":rows30[i]["timestamp"]+timedelta(minutes=30),"from":a,"to":b,"price":rows30[i]["close"]})
    return out

def hist5_until(rows5:Sequence[Dict[str,Any]],obs:datetime)->List[Dict[str,Any]]:
    return [r for r in rows5 if r["timestamp"]+timedelta(minutes=5)<=obs]

def character_stage(bars:Sequence[Dict[str,Any]],prior:str)->Tuple[int,Dict[str,bool],List[str]]:
    """Character sequence: warning -> structure break -> recovery -> failed recovery -> second break.
    Only completed 5m bars are used. Stage 4 requires a later bar than stage 3.
    """
    if len(bars)<MIN_5M_HISTORY:return 0,{},[]
    c=[b["close"] for b in bars]; h=[b["high"] for b in bars]; l=[b["low"] for b in bars]
    adverse=lambda a,b:(b<a if prior=="LONG" else b>a)
    warning=adverse(c[-2],c[-1])
    if not warning:return 0,{"warning":False},[]
    # Search for a completed earlier structure break. The latest bar may be the warning, but cannot be both the later confirmation.
    break_idx=None
    for i in range(max(3,len(c)-12),len(c)-1):
        if prior=="LONG" and c[i]<min(l[i-3:i]): break_idx=i
        if prior=="SHORT" and c[i]>max(h[i-3:i]): break_idx=i
    if break_idx is None:
        return 1,{"warning":True,"structure":False},["warning"]
    # There must be a recovery after the break, followed by a failed recovery on a later bar.
    after=c[break_idx+1:-1]
    if not after:return 2,{"warning":True,"structure":True,"failed_recovery":False},["warning","structure"]
    if prior=="LONG":
        recovery_peak=max(after); recovery=recovery_peak>c[break_idx]; failed=recovery and c[-1]<recovery_peak
        second=failed and c[-1]<c[break_idx]
    else:
        recovery_trough=min(after); recovery=recovery_trough<c[break_idx]; failed=recovery and c[-1]>recovery_trough
        second=failed and c[-1]>c[break_idx]
    flags={"warning":True,"structure":True,"failed_recovery":failed,"second_break":second}
    stage=4 if second else 3 if failed else 2
    return stage,flags,[k for k,v in flags.items() if v]

def sequence_history(rows5,event_time,prior)->List[Dict[str,Any]]:
    start=event_time-timedelta(minutes=LOOKBACK_MINUTES); out=[]
    for bar in rows5:
        obs=bar["timestamp"]+timedelta(minutes=5)
        if start<=obs<=event_time:
            hist=hist5_until(rows5,obs); stage,flags,reasons=character_stage(hist[-24:],prior)
            out.append({"time":obs,"stage":stage,"flags":flags,"reasons":reasons})
    return out

def has_opposite(events,anchor,prior):
    end=anchor+timedelta(minutes=NEGATIVE_HORIZON_MINUTES); target=opposite(prior)
    return any(anchor<e["known_time"]<=end and e["to"]==target for e in events)

def build_cases(rows30,rows5,symbol):
    closes=[r["close"] for r in rows30]; states=[market_state(closes,i) for i in range(len(rows30))]; events=direct_transitions(rows30); out=[]
    for e in events:
        seq=sequence_history(rows5,e["known_time"],e["from"])
        if seq:out.append({"kind":"REAL","symbol":symbol,"event_time":e["known_time"],"from":e["from"],"to":e["to"],"sequence":seq})
    for i in range(TREND_WINDOW+1,len(rows30)-2):
        prior=states[i-1]
        if prior not in ("LONG","SHORT"):continue
        anchor=rows30[i]["timestamp"]+timedelta(minutes=30)
        if has_opposite(events,anchor,prior):continue
        start=rows30[i]["timestamp"]; end=start+timedelta(minutes=30); seq=[]
        for bar in rows5:
            obs=bar["timestamp"]+timedelta(minutes=5)
            if start<obs<=end:
                hist=hist5_until(rows5,obs); stage,flags,reasons=character_stage(hist[-24:],prior)
                seq.append({"time":obs,"stage":stage,"flags":flags,"reasons":reasons})
        if seq:out.append({"kind":"NEGATIVE","symbol":symbol,"event_time":anchor,"from":prior,"to":opposite(prior),"sequence":seq})
    return out

def split_cases(cases):
    by=defaultdict(list)
    for c in cases:by[c["symbol"]].append(c)
    d=[];h=[]
    for rows in by.values():
        rows.sort(key=lambda x:x["event_time"]); cut=int(len(rows)*.70); d+=rows[:cut]; h+=rows[cut:]
    return d,h

def first_fire(c,required)->Optional[Dict[str,Any]]:
    for x in c["sequence"]:
        if x["stage"]>=required:return x
    return None

def evaluate(cases,required,label):
    real=[c for c in cases if c["kind"]=="REAL"]; neg=[c for c in cases if c["kind"]=="NEGATIVE"]; rec=[];late=miss=false=0
    for c in real:
        f=first_fire(c,required)
        if f is None:miss+=1
        elif f["time"]<=c["event_time"]:rec.append((c,f))
        else:late+=1
    false=sum(first_fire(c,required) is not None for c in neg); leads=[(c["event_time"]-f["time"]).total_seconds()/60 for c,f in rec]
    before=100*len(rec)/len(real) if real else 0; latep=100*late/len(real) if real else 0; missp=100*miss/len(real) if real else 0; fp=100*false/len(neg) if neg else 0; detected=len(rec)+late; precision=100*detected/(detected+false) if detected+false else 0
    w5=100*sum(x<=5 for x in leads)/len(leads) if leads else 0; w15=100*sum(x<=15 for x in leads)/len(leads) if leads else 0
    print(f"{label} stage={required} REAL={len(real)} NEG={len(neg)}"); print(f"  recognized_before={before:.1f}% late={latep:.1f}% missed={missp:.1f}%"); print(f"  false_alarm={fp:.1f}% precision={precision:.1f}%"); print(f"  lead_mean={mean(leads):.1f}m lead_median={median(leads):.1f}m within5={w5:.1f}% within15={w15:.1f}%" if leads else "  lead_mean=n/a lead_median=n/a within5=0.0% within15=0.0%")

def stage_reach(cases,label):
    real=[c for c in cases if c["kind"]=="REAL"]; print(f"{label} REAL character reach")
    for s in range(1,5):
        n=sum(any(x["stage"]>=s for x in c["sequence"]) for c in real); print(f"  stage{s}={n}/{len(real)} ({100*n/len(real) if real else 0:.1f}%)")

def run(symbols):
    all_cases=[]
    for symbol in symbols:
        rows30=load(symbol,"30m",6000); rows5=load(symbol,"5m",20000); cases=build_cases(rows30,rows5,symbol); all_cases+=cases
        print(f"{symbol}: 30m={len(rows30)} 5m={len(rows5)} cases={len(cases)} real={sum(c['kind']=='REAL' for c in cases)} neg={sum(c['kind']=='NEGATIVE' for c in cases)}")
    d,h=split_cases(all_cases); print(f"TOTAL cases={len(all_cases)} discovery={len(d)} holdout={len(h)}")
    for label,cases in (("FULL",all_cases),("DISCOVERY 70%",d),("HOLDOUT 30%",h)):
        print(label); stage_reach(cases,label); evaluate(cases,2,"CHARACTER_2"); evaluate(cases,4,"CHARACTER_4")

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("symbols",nargs="*",default=DEFAULT_SYMBOLS); run(p.parse_args().symbols)
