#!/usr/bin/env python3
"""EXP78: diagnostic audit of EXP77 V16 trades and rejected signals.
No trading or strategy changes. Future-price observations are hindsight only.
"""
import csv,json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"kiss/visual_research/aimn_nvda_candles.json"
BASE=ROOT/"kiss/results/exp77_early_entry_st_exit"
OUT=ROOT/"kiss/results/exp78_v16_audit"

def load_csv(p):
    with p.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def save_csv(p,rows,cols):
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
def pct(a,b):return (a/b-1)*100
def main():
    candles=json.loads(DATA.read_text(encoding="utf-8"))
    candles.sort(key=lambda x:str(x["timestamp"]))
    times=[str(c["timestamp"]) for c in candles]
    by_time={t:i for i,t in enumerate(times)}
    trades=load_csv(BASE/"v16_trades.csv")
    rejects=load_csv(BASE/"v16_missed_signals.csv")
    OUT.mkdir(parents=True,exist_ok=True)
    trade_audit=[]
    for n,t in enumerate(trades,1):
        a=by_time.get(t["entry_time"]);b=by_time.get(t["exit_time"])
        if a is None or b is None or b<a:raise ValueError("Trade timestamps missing/out of order")
        entry=float(t["entry_price"]);exitp=float(t["exit_price"])
        window=candles[a:b+1]
        lowest=min(float(x["low"]) for x in window)
        highest=max(float(x["high"]) for x in window)
        low_i=a+next(j for j,x in enumerate(window) if float(x["low"])==lowest)
        # Potential at the lowest low is NOT an executable fill.
        best_potential=pct(entry,lowest)
        realized=pct(entry,exitp)
        trade_audit.append(dict(trade_id=n,entry_time=t["entry_time"],
            exit_time=t["exit_time"],exit_reason=t["exit_reason"],
            entry_price=entry,exit_price=exitp,
            net_pct=float(t["net_pnl_pct"]),
            candles_held=b-a+1,lowest_low=lowest,
            lowest_time=times[low_i],
            best_intratrade_gross_pct=round(best_potential,4),
            actual_gross_pct=round(realized,4),
            potential_giveback_pp=round(best_potential-realized,4),
            worst_intratrade_adverse_pct=round(pct(highest,entry),4)))
    save_csv(OUT/"v16_trade_audit.csv",trade_audit,list(trade_audit[0]) if trade_audit else
             ["trade_id","entry_time","exit_time","exit_reason","entry_price",
              "exit_price","net_pct","candles_held","lowest_low","lowest_time",
              "best_intratrade_gross_pct","actual_gross_pct","potential_giveback_pp",
              "worst_intratrade_adverse_pct"])
    missed_audit=[]
    for r in rejects:
        i=by_time.get(r["time"])
        if i is None:continue
        close=float(candles[i]["close"])
        # Evaluate next 3, 6 and 12 available 5m candles, same date only.
        row=dict(signal_time=r["time"],reason=r["reason"],st_state=r["st_state"],
                 signal_close=close)
        for horizon in (3,6,12):
            future=[x for x in candles[i+1:i+1+horizon] if
                    str(x["timestamp"])[:10]==r["time"][:10]]
            if not future:
                row[f"future_{horizon}_bars"]=0
                row[f"close_move_{horizon}_pct"]=None
                row[f"best_short_move_{horizon}_pct"]=None
                row[f"worst_short_move_{horizon}_pct"]=None
            else:
                last=float(future[-1]["close"])
                lo=min(float(x["low"]) for x in future)
                hi=max(float(x["high"]) for x in future)
                row[f"future_{horizon}_bars"]=len(future)
                row[f"close_move_{horizon}_pct"]=round(pct(close,last),4)
                row[f"best_short_move_{horizon}_pct"]=round(pct(close,lo),4)
                row[f"worst_short_move_{horizon}_pct"]=round(pct(hi,close),4)
        missed_audit.append(row)
    cols=["signal_time","reason","st_state","signal_close"]
    for horizon in (3,6,12):
        cols += [f"future_{horizon}_bars",f"close_move_{horizon}_pct",
                 f"best_short_move_{horizon}_pct",f"worst_short_move_{horizon}_pct"]
    save_csv(OUT/"v16_rejected_signal_audit.csv",missed_audit,cols)
    reason_counts=dict(Counter(x["exit_reason"] for x in trade_audit))
    summary=dict(experiment="EXP78",data_candles=len(candles),
        trades_audited=len(trade_audit),rejected_signals_audited=len(missed_audit),
        net_pct_sum=round(sum(x["net_pct"] for x in trade_audit),4),
        exit_reasons=reason_counts,
        potential_giveback_pp_sum=round(sum(x["potential_giveback_pp"] for x in trade_audit),4),
        avg_potential_giveback_pp=round(sum(x["potential_giveback_pp"] for x in trade_audit)/len(trade_audit),4) if trade_audit else None,
        rejected_reasons=dict(Counter(x["reason"] for x in missed_audit)),
        important="Intratrade lows and future signal outcomes are hindsight diagnostics, NOT executable prices or backtested trade returns.")
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print("EXP78 — V16 ENTRY / ST EXIT AUDIT — RESEARCH ONLY")
    print(json.dumps(summary,indent=2))
    print("Detailed CSV files:",OUT)
if __name__=="__main__":main()
