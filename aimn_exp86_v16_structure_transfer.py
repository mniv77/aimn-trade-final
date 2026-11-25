#!/usr/bin/env python3
"""EXP86: Prespecified entry-structure threshold stress-test, research only.

Replays the unchanged EXP83 baseline and evaluates a diagnostic decision
at the completed V16 signal candle. A counterfactual 'kept trade' tally
is NOT a backtest of a new trading engine: skipping trades can free the
engine to take subsequent V16 signals. Reports retained baseline outcomes
only, and does not claim executable counterfactual P&L.
No production edits, no live orders, no model fitting or parameter search.
"""
import csv
import json
from pathlib import Path
import aimn_exp83_v16_structural_exit as exp83
import aimn_exp85_v16_entry_structure as exp85

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp86_v16_entry_structure_transfer"

# One rule derived from EXP85's AAPL observation; fixed prior to this test.
RULES={
    "AAPL_OBSERVATION_3_CONSECUTIVE_DOWN":lambda r: r["consecutive_lower_closes"]>=3,
    "ALTERNATE_4_OF_LAST_6_DOWN":lambda r: r["lower_closes_last_6"]>=4,
}
def report(group):
    wins=[r for r in group if r["net_trade_pct"]>0]
    return {"trades":len(group),"winners":len(wins),
            "losers":len(group)-len(wins),
            "sum_baseline_net_pct":round(sum(r["net_trade_pct"] for r in group),5)}
def symbol_run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(times)!=len(set(times)):raise ValueError("Duplicate timestamp")
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    st=exp83.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=exp83.rsi_wilder(closes)
    market=[exp83.get_market_state(closes,i) for i in range(len(rows))]
    trades,candidates,rejected,blocked=exp83.simulate(rows,st,rsi,market,None,False)
    if blocked:raise ValueError("Unexpected structure gate on ST baseline")
    trade_by_entry={r["entry_time"]:r for r in trades}
    joined=[]
    for i in range(35,len(rows)):
        if exp83.is_major_long_to_short_reversal(highs,lows,closes,market,i) is None:continue
        if i+1==len(rows) or times[i+1][:10]!=times[i][:10]:continue
        t=trade_by_entry.get(times[i+1])
        if t is None:continue
        feat=exp85.features(rows,i)
        joined.append({
          "symbol":symbol,"signal_time":times[i],
          "entry_time":t["entry_time"],"exit_time":t["exit_time"],
          "exit_reason":t["exit_reason"],"net_trade_pct":float(t["net_pnl_pct"]),
          "winner":t["net_pnl_pct"]>0,
          "consecutive_lower_closes":feat["consecutive_lower_closes"],
          "lower_closes_last_6":feat["lower_closes_last_6"],
          "three_bar_price_change_pct":feat["three_bar_price_change_pct"],
          "six_bar_price_change_pct":feat["six_bar_price_change_pct"],
          "signal_RSI":round(rsi[i],5) if rsi[i] is not None else None
        })
    if len(joined)!=len(trades):
        raise ValueError(f"{symbol}: only matched {len(joined)} of {len(trades)} trades")
    baseline=report(joined)
    rules={}
    for name,rule in RULES.items():
        kept=[r for r in joined if rule(r)]
        skipped=[r for r in joined if not rule(r)]
        for r in joined:r["pass_"+name]=rule(r)
        rules[name]={
          "retained_original_trades":report(kept),
          "skipped_original_trades":report(skipped),
          "would_skip_winners":sum(r["winner"] for r in skipped),
          "would_skip_losers":sum(not r["winner"] for r in skipped),
          "note":"Conditional audit of original trades only; do not interpret as new trading-system P&L"
        }
    fields=list(joined[0]) if joined else []
    with (OUT/(symbol.lower()+"_trade_rule_audit.csv")).open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(joined)
    return {"V16_candidates":candidates,"accepted_trades":len(trades),
            "rejected":rejected,"baseline":baseline,"rules":rules}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={"experiment":"EXP86","research_only":True,
      "aim":"Do prespecified entry-structure descriptors distinguish outcomes consistently across NVDA/AAPL?",
      "causal_features":"Only available at V16 signal close; entries/exits unchanged",
      "caution":"Same previously studied data and very small samples. This is a conditional retrospective audit, not a rerun of a filtered strategy. The branch and live strategy remain unchanged.",
      "symbols":{}}
    for sym,path in exp83.DATA.items():
        result["symbols"][sym]=symbol_run(sym,path)
    (OUT/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("EXP86 — V16 ENTRY-STRUCTURE RULE TRANSFER — RESEARCH ONLY")
    print(json.dumps(result,indent=2))
    print("Detailed rows:",OUT)
if __name__=="__main__":main()
