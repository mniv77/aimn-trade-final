#!/usr/bin/env python3
"""EXP90: Choppiness Index noise audit for original V16 SHORT signals.

Research-only, no live orders, no production modifications. Uses EXP83 baseline
trades unchanged. CHOP(14) is computed on completed OHLC candles only; rolling
windows must remain within a single trading session. The classical indicator:
100*log10(sum(TR)/[max(high)-min(low)])/log10(14).
Evaluates prespecified CHOP bands <38.2, 38.2..61.8, >=61.8, plus a
CHOP <61.8 descriptive gate. Not a filtered-engine backtest.
"""
import csv
import json
import math
from pathlib import Path
import aimn_exp83_v16_structural_exit as exp83

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp90_choppiness_noise_audit"
PERIOD=14

def choppiness(rows, period=PERIOD):
    n=len(rows)
    values=[None]*n
    for i in range(period-1,n):
        start=i-period+1
        day=str(rows[i]["timestamp"])[:10]
        if str(rows[start]["timestamp"])[:10]!=day:continue
        tr_sum=0.0
        hi=float("-inf")
        lo=float("inf")
        for j in range(start,i+1):
            high=float(rows[j]["high"]);low=float(rows[j]["low"])
            # At the start of each session avoid prior-day close.
            pc=float(rows[j-1]["close"]) if j>0 and str(rows[j-1]["timestamp"])[:10]==day else None
            tr=max(high-low,abs(high-pc),abs(low-pc)) if pc is not None else high-low
            tr_sum+=tr
            hi=max(hi,high);lo=min(lo,low)
        span=hi-lo
        if span<=0 or tr_sum<=0:continue
        ratio=max(1.0,tr_sum/span) # floating-point safeguard
        values[i]=100*math.log10(ratio)/math.log10(period)
    return values

def describe(records):
    return {"trades":len(records),
      "winners":sum(r["winner"] for r in records),
      "losers":sum(not r["winner"] for r in records),
      "sum_original_net_trade_pct":round(sum(r["net_trade_pct"] for r in records),5)}

def write_csv(path,records):
    if not records:return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(times)!=len(set(times)):raise ValueError("Duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    st=exp83.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=exp83.rsi_wilder(closes)
    market=[exp83.get_market_state(closes,i) for i in range(len(rows))]
    trades,candidates,rejected,blocked=exp83.simulate(rows,st,rsi,market,None,False)
    if blocked:raise ValueError("Unexpected baseline structure filter")
    chop=choppiness(rows)
    by_entry={t["entry_time"]:t for t in trades}
    records=[]
    for i in range(35,len(rows)):
        if exp83.is_major_long_to_short_reversal(highs,lows,closes,market,i) is None:continue
        next_time=times[i+1] if i+1<len(rows) else None
        t=by_entry.get(next_time) if next_time and next_time[:10]==times[i][:10] else None
        v=chop[i]
        band="UNAVAILABLE" if v is None else (
          "TRENDING_LT38_2" if v<38.2 else
          "MIDDLE_38_2_TO_61_8" if v<61.8 else
          "CHOPPY_GE61_8")
        records.append({
          "symbol":symbol,"signal_time":times[i],
          "baseline_accepted":t is not None,
          "entry_time":t["entry_time"] if t else "",
          "baseline_winner":t["net_pnl_pct"]>0 if t else "",
          "baseline_net_trade_pct":float(t["net_pnl_pct"]) if t else "",
          "CHOP14":round(v,5) if v is not None else "",
          "CHOP_band":band,
          "passes_CHOP_lt61_8":v is not None and v<61.8,
          "passes_CHOP_lt38_2":v is not None and v<38.2,
          "session_history_available":v is not None,
        })
    accepted=[r for r in records if r["baseline_accepted"]]
    if len(records)!=candidates or len(accepted)!=len(trades):
        raise ValueError(f"{symbol}: mapping mismatch ({len(records)}/{candidates}, {len(accepted)}/{len(trades)})")
    for r in accepted:
        r["winner"]=bool(r["baseline_winner"])
        r["net_trade_pct"]=r["baseline_net_trade_pct"]
    bands={}
    for band in ("TRENDING_LT38_2","MIDDLE_38_2_TO_61_8","CHOPPY_GE61_8","UNAVAILABLE"):
        bands[band]=describe([r for r in accepted if r["CHOP_band"]==band])
    gates={}
    for name in ("passes_CHOP_lt61_8","passes_CHOP_lt38_2"):
        kept=[r for r in accepted if r[name]]
        skipped=[r for r in accepted if not r[name]]
        gates[name]={"retained_original":describe(kept),"skipped_original":describe(skipped)}
    write_csv(OUT/(symbol.lower()+"_signals.csv"),records)
    return {
      "V16_candidates":candidates,
      "baseline":describe(accepted),
      "rejected":rejected,
      "candidates_without_session_history":sum(not r["session_history_available"] for r in records),
      "baseline_trades_without_session_history":sum(not r["session_history_available"] for r in accepted),
      "CHOP_bands":bands,"fixed_gates":gates,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
      "experiment":"EXP90","research_only":True,
      "indicator":"CHOP(14), OHLC-based true range; complete current-session windows only",
      "caution":"Same previously inspected trade sample; fixed gate subsets of baseline trades are NOT executable strategy P&L. Insufficient same-day history is reported separately.",
      "symbols":{},
    }
    for sym,path in exp83.DATA.items():
        report["symbols"][sym]=run(sym,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP90 — CHOPPINESS INDEX NOISE AUDIT — RESEARCH ONLY")
    print(json.dumps(report,indent=2))
    print("Detailed CSV:",OUT)

if __name__=="__main__":
    main()
