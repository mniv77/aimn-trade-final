#!/usr/bin/env python3
"""EXP89 — ADX noise-filter diagnostic for V16 SHORT signals.

Research-only retrospective audit. Existing EXP83 V16/ST baseline remains
unchanged. ADX(14), +DI and -DI are calculated from completed OHLC bars.
Report fixed descriptive ADX bands and a prespecified >=20 / -DI>+DI
gate, but DO NOT interpret retained original trade returns as a filtered
engine backtest: skipped trades could permit different later entries.
No orders, no production changes, no threshold search.
"""
import csv
import json
from pathlib import Path
import aimn_exp83_v16_structural_exit as exp83

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp89_adx_noise_audit"
PERIOD=14

def wilder(values,n):
    out=[None]*len(values)
    if len(values)<n:return out
    if any(v is None for v in values[:n]):return out
    value=sum(values[:n])
    out[n-1]=value
    for i in range(n,len(values)):
        if values[i] is None:continue
        value=value-value/n+values[i]
        out[i]=value
    return out

def adx_series(rows,n=PERIOD):
    length=len(rows)
    tr=[None]*length; plus=[None]*length; minus=[None]*length
    for i in range(1,length):
        h=float(rows[i]["high"]);l=float(rows[i]["low"])
        ph=float(rows[i-1]["high"]);pl=float(rows[i-1]["low"])
        pc=float(rows[i-1]["close"])
        tr[i]=max(h-l,abs(h-pc),abs(l-pc))
        up=h-ph; down=pl-l
        plus[i]=up if up>down and up>0 else 0.0
        minus[i]=down if down>up and down>0 else 0.0
    # Initial Wilder smoothing from bars 1..n, not from missing bar zero.
    def smooth(seq):
        out=[None]*length
        if length<=n:return out
        total=sum(seq[1:n+1])
        out[n]=total
        for i in range(n+1,length):
            total=total-total/n+seq[i]
            out[i]=total
        return out
    t=smooth(tr);p=smooth(plus);m=smooth(minus)
    pd=[None]*length;md=[None]*length;dx=[None]*length
    for i in range(n,length):
        if t[i] is None or t[i]<=0:continue
        pd[i]=100*p[i]/t[i];md[i]=100*m[i]/t[i]
        denominator=pd[i]+md[i]
        dx[i]=100*abs(pd[i]-md[i])/denominator if denominator else 0.0
    a=[None]*length
    if length>2*n-1 and all(v is not None for v in dx[n:2*n]):
        val=sum(dx[n:2*n])/n
        a[2*n-1]=val
        for i in range(2*n,length):
            if dx[i] is None:continue
            val=((n-1)*val+dx[i])/n
            a[i]=val
    return a,pd,md

def summary(rows):
    return {"count":len(rows),"winners":sum(r["winner"] for r in rows),
        "losers":sum(not r["winner"] for r in rows),
        "sum_original_net_trade_pct":round(sum(r["net_trade_pct"] for r in rows),5)}

def write_csv(path,records):
    if not records:return
    fields=list(records[0])
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader();writer.writerows(records)

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(set(times))!=len(times):raise ValueError("Duplicate timestamps")
    close=[float(r["close"]) for r in rows]
    high=[float(r["high"]) for r in rows]
    low=[float(r["low"]) for r in rows]
    st=exp83.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=exp83.rsi_wilder(close)
    market=[exp83.get_market_state(close,i) for i in range(len(rows))]
    trades,candidates,rejected,blocked=exp83.simulate(rows,st,rsi,market,None,False)
    if blocked:raise ValueError("Unexpected baseline structure gate")
    a,pd,md=adx_series(rows)
    trade_by_entry={t["entry_time"]:t for t in trades}
    records=[]
    for i in range(35,len(rows)):
        if exp83.is_major_long_to_short_reversal(high,low,close,market,i) is None:continue
        next_time=times[i+1] if i+1<len(rows) else None
        t=trade_by_entry.get(next_time) if next_time and next_time[:10]==times[i][:10] else None
        av=a[i];pv=pd[i];mv=md[i]
        record={
          "symbol":symbol,"signal_time":times[i],"entry_time":t["entry_time"] if t else "",
          "accepted_baseline":t is not None,
          "baseline_winner":t["net_pnl_pct"]>0 if t else "",
          "baseline_net_pct":float(t["net_pnl_pct"]) if t else "",
          "ST_at_signal":st[i],
          "ADX14":round(av,5) if av is not None else "",
          "plus_DI14":round(pv,5) if pv is not None else "",
          "minus_DI14":round(mv,5) if mv is not None else "",
          "ADX_band":("LOW_LT20" if av<20 else "MID_20_TO_25" if av<25 else "HIGH_GE25") if av is not None else "UNAVAILABLE",
          "passes_ADX20":av>=20 if av is not None else False,
          "passes_ADX20_minusDI":av>=20 and mv>pv if av is not None and mv is not None and pv is not None else False,
        }
        records.append(record)
    accepted=[r for r in records if r["accepted_baseline"]]
    if len(records)!=candidates or len(accepted)!=len(trades):
        raise ValueError(f"{symbol}: signal/entry mismatch: {len(records)}/{candidates}, {len(accepted)}/{len(trades)}")
    for r in accepted:
        r["winner"]=bool(r["baseline_winner"])
        r["net_trade_pct"]=r["baseline_net_pct"]
    groups={}
    for band in ("LOW_LT20","MID_20_TO_25","HIGH_GE25"):
        groups[band]=summary([r for r in accepted if r["ADX_band"]==band])
    gates={}
    for key in ("passes_ADX20","passes_ADX20_minusDI"):
        kept=[r for r in accepted if r[key]]
        skipped=[r for r in accepted if not r[key]]
        gates[key]={"retained_original":summary(kept),"skipped_original":summary(skipped)}
    write_csv(OUT/(symbol.lower()+"_signals.csv"),records)
    return {"V16_candidates":candidates,"baseline":summary(accepted),
            "rejected":rejected,"ADX_bands":groups,"fixed_gates":gates}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"experiment":"EXP89","research_only":True,
      "indicator":"ADX(14), +DI(14), -DI(14), Wilder smoothing; values at completed signal candle",
      "warning":"Historical same-sample diagnostic only; conditional retained-trade sums are NOT new-strategy backtest returns. No tuning or production changes.",
      "symbols":{}}
    for symbol,path in exp83.DATA.items():report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP89 — ADX NOISE FILTER DIAGNOSTIC — RESEARCH ONLY")
    print(json.dumps(report,indent=2))
    print("Detailed CSV:",OUT)
if __name__=="__main__":main()
