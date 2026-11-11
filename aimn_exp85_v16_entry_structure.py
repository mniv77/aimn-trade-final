#!/usr/bin/env python3
"""EXP85 — Causal entry-structure audit for NVDA/AAPL V16 SHORT.
Research only. No rule tuning, no live orders, no production changes.
Uses unchanged EXP83 baseline trades. Features at completed SIGNAL candle
(before next-open entry) are separate from hindsight trade outcomes.
"""
import csv
import json
from pathlib import Path
import aimn_exp83_v16_structural_exit as exp83

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp85_v16_entry_structure"
LOOKBACK=12
def pct(a,b):
    return round((a/b-1)*100,5) if b else None
def avg(v):
    return round(sum(v)/len(v),5) if v else None
def save(path,items,fields):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(items)
def features(rows,i):
    # At signal time i, only bars through i may be observed.
    c=[float(r["close"]) for r in rows]
    h=[float(r["high"]) for r in rows]
    l=[float(r["low"]) for r in rows]
    o=[float(r["open"]) for r in rows]
    window=rows[max(0,i-LOOKBACK+1):i+1]
    prior=rows[max(0,i-LOOKBACK):i]
    peak=max(float(r["high"]) for r in prior) if prior else None
    trough=min(float(r["low"]) for r in prior) if prior else None
    downs=0
    for j in range(i,max(0,i-6),-1):
        if c[j]<c[j-1]:downs+=1
        else:break
    prior_3=c[i-3] if i>=3 else None
    prior_6=c[i-6] if i>=6 else None
    return {
      "signal_close":c[i],
      "distance_below_prior_12bar_peak_pct":pct(peak,c[i]) if peak else None,
      "signal_close_vs_prior_12bar_low_pct":pct(c[i],trough) if trough else None,
      "consecutive_lower_closes":downs,
      "lower_closes_last_6":sum(c[j]<c[j-1] for j in range(max(1,i-5),i+1)),
      "three_bar_price_change_pct":pct(c[i],prior_3) if prior_3 else None,
      "six_bar_price_change_pct":pct(c[i],prior_6) if prior_6 else None,
      "signal_candle_body_pct":pct(c[i],o[i]),
      "signal_close_below_previous_low":c[i]<l[i-1] if i else None,
      "signal_close_below_prior_6bar_low":c[i]<min(l[max(0,i-6):i]) if i else None,
      "signal_range_pct":pct(h[i],l[i]),
    }
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
    trades,candidates,rejected,_=exp83.simulate(rows,st,rsi,market,None,False)
    trades_by_entry={t["entry_time"]:t for t in trades}
    entries=[]; signals=[]
    for i in range(35,len(rows)):
        if exp83.is_major_long_to_short_reversal(highs,lows,closes,market,i) is None:
            continue
        next_time=times[i+1] if i+1<len(rows) else ""
        same_session=bool(next_time and next_time[:10]==times[i][:10])
        trade=trades_by_entry.get(next_time) if same_session else None
        row={"symbol":symbol,"signal_time":times[i],"signal_ST":st[i],
             "signal_RSI":round(rsi[i],5) if rsi[i] is not None else None,
             "next_open_same_session":same_session,
             "accepted_trade":trade is not None,
             **features(rows,i)}
        if trade is not None:
            row.update({
                "entry_time":trade["entry_time"],
                "exit_time":trade["exit_time"],
                "exit_reason":trade["exit_reason"],
                "net_trade_pct":trade["net_pnl_pct"],
                "winner":trade["net_pnl_pct"]>0,
            })
            entries.append(row)
        signals.append(row)
    if len(entries)!=len(trades):
        raise ValueError(f"{symbol}: mapped {len(entries)} entries vs {len(trades)} trades")
    fields=list(signals[0].keys())
    outcome=["entry_time","exit_time","exit_reason","net_trade_pct","winner"]
    save(OUT/(symbol.lower()+"_all_v16_signals.csv"),signals,fields+outcome)
    save(OUT/(symbol.lower()+"_accepted_entry_features.csv"),entries,fields+outcome)
    numeric=["distance_below_prior_12bar_peak_pct",
       "signal_close_vs_prior_12bar_low_pct","consecutive_lower_closes",
       "lower_closes_last_6","three_bar_price_change_pct",
       "six_bar_price_change_pct","signal_candle_body_pct","signal_range_pct",
       "signal_RSI"]
    def group_report(group):
        return {"count":len(group),
            "mean_features":{k:avg([float(r[k]) for r in group if r.get(k) is not None]) for k in numeric}}
    return {
      "v16_candidates":candidates,"accepted_trades":len(trades),
      "winners":sum(t["net_pnl_pct"]>0 for t in trades),
      "losers":sum(t["net_pnl_pct"]<=0 for t in trades),
      "net_pct_sum":round(sum(t["net_pnl_pct"] for t in trades),5),
      "rejected_signals":rejected,
      "accepted_winners":group_report([r for r in entries if r["winner"]]),
      "accepted_losers":group_report([r for r in entries if not r["winner"]]),
      "rejected_ST_not_long":group_report([r for r in signals if r["signal_ST"]!="LONG"]),
    }
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"experiment":"EXP85","research_only":True,
      "baseline":"Unmodified EXP83 V16+ST replay; 0.10% commission per side",
      "features_available":"Only completed candles at V16 signal close",
      "warning":"Winning/losing labels are hindsight; feature contrasts are descriptive and not validated trading rules. Rejected signals are not hypothetical trades.",
      "symbols":{}}
    for symbol,path in exp83.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP85 — CAUSAL V16 ENTRY STRUCTURE — RESEARCH ONLY")
    print(json.dumps(report,indent=2))
    print("Detailed reports:",OUT)
if __name__=="__main__":main()
