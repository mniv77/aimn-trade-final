#!/usr/bin/env python3
"""EXP84: NVDA vs AAPL V16 SHORT entry-quality audit.

Research-only. Replays the unchanged EXP83 Supertrend baseline for both
symbols and audits what price did after each entry. Forward paths are
hindsight diagnostics, not causal entry criteria or executable trade returns.
No live trading or production modifications.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import aimn_exp83_v16_structural_exit as exp83

OUT=ROOT/"kiss/results/exp84_v16_cross_symbol_entry_audit"
HORIZONS=(3,6,12)
def pchange(new,old):
    return (new/old-1)*100
def fmt(v):
    return round(v,5) if v is not None else None
def write_csv(path,rows,fields):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
def audit_symbol(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda x:str(x["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    indexes={t:i for i,t in enumerate(times)}
    if len(indexes)!=len(times):
        raise ValueError("Duplicate candle timestamps")
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    st=exp83.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=exp83.rsi_wilder(closes)
    market=[exp83.get_market_state(closes,i) for i in range(len(rows))]
    trades,candidates,rejected,blocked=exp83.simulate(rows,st,rsi,market,None,False)
    assert blocked==0
    detail=[]
    for trade in trades:
        start=indexes[trade["entry_time"]]
        end=indexes[trade["exit_time"]]
        entry=float(trade["entry_price"])
        exit_reason=trade["exit_reason"]
        # Entry bar is included, but opening execution precedes its high/low.
        # If exiting at next open, exclude exit bar's full high/low.
        # For an intrabar stop, the bar's full range is not a precise path.
        # For session end, include the final candle's full range.
        range_end=end if exit_reason in ("SESSION_END","DATA_END","STOP_LOSS") else end-1
        live_bars=rows[start:range_end+1] if range_end>=start else []
        best_low=min((float(x["low"]) for x in live_bars),default=None)
        worst_high=max((float(x["high"]) for x in live_bars),default=None)
        entry_context=rows[max(0,start-6):start]
        entry_context_high=max((float(x["high"]) for x in entry_context),default=None)
        entry_context_low=min((float(x["low"]) for x in entry_context),default=None)
        record={
            "symbol":symbol,
            "entry_time":trade["entry_time"],
            "exit_time":trade["exit_time"],
            "exit_reason":exit_reason,
            "entry_price":entry,
            "exit_price":float(trade["exit_price"]),
            "net_pct":float(trade["net_pnl_pct"]),
            "gross_pct":float(trade["gross_pnl_pct"]),
            "bars_held":int(trade["bars_held"]),
            "entry_ST_state":st[start],
            "entry_RSI":fmt(rsi[start]) if rsi[start] is not None else None,
            "entry_vs_prior_6bar_high_pct":fmt(pchange(entry,entry_context_high)) if entry_context_high else None,
            "entry_vs_prior_6bar_low_pct":fmt(pchange(entry,entry_context_low)) if entry_context_low else None,
            "best_intratrade_low_pct":fmt(pchange(entry,best_low)) if best_low else None,
            "worst_intratrade_high_pct":fmt(pchange(worst_high,entry)) if worst_high else None,
            "best_low_is_hindsight":True,
        }
        for h in HORIZONS:
            # Horizon close is from an actual candle close, after entry.
            # Only include full horizons inside the same session.
            j=start+h-1
            valid=(j<len(rows) and times[j][:10]==times[start][:10])
            record[f"close_after_{h}_bars_short_gross_pct"]=(
                fmt(pchange(entry,closes[j])) if valid else None)
            record[f"after_{h}_bars_available"]=valid
        detail.append(record)
    columns=[
        "symbol","entry_time","exit_time","exit_reason","entry_price","exit_price",
        "net_pct","gross_pct","bars_held","entry_ST_state","entry_RSI",
        "entry_vs_prior_6bar_high_pct","entry_vs_prior_6bar_low_pct",
        "best_intratrade_low_pct","worst_intratrade_high_pct","best_low_is_hindsight",
    ]
    for h in HORIZONS:
        columns.extend([f"close_after_{h}_bars_short_gross_pct",f"after_{h}_bars_available"])
    write_csv(OUT/(symbol.lower()+"_trade_audit.csv"),detail,columns)
    def mean(values):
        return fmt(sum(values)/len(values)) if values else None
    def summarize(trades):
        return {
            "count":len(trades),
            "mean_entry_RSI":mean([r["entry_RSI"] for r in trades if r["entry_RSI"] is not None]),
            "mean_bars_held":mean([r["bars_held"] for r in trades]),
            "mean_net_pct":mean([r["net_pct"] for r in trades]),
            "mean_best_intratrade_low_pct":mean([r["best_intratrade_low_pct"] for r in trades if r["best_intratrade_low_pct"] is not None]),
            "mean_worst_intratrade_high_pct":mean([r["worst_intratrade_high_pct"] for r in trades if r["worst_intratrade_high_pct"] is not None]),
            "forward_closes":{
                str(h):{
                    "complete":len([r for r in trades if r[f"after_{h}_bars_available"]]),
                    "mean_short_gross_pct":mean([r[f"close_after_{h}_bars_short_gross_pct"] for r in trades if r[f"after_{h}_bars_available"]]),
                    "short_favorable":sum(r[f"close_after_{h}_bars_short_gross_pct"]>0 for r in trades if r[f"after_{h}_bars_available"]),
                } for h in HORIZONS
            },
        }
    # Analyze V16 candidates rejected for ST state separately; no
    # hypothetical executions or overlapping trade claims.
    candidate_rows=[]
    active_entries={r["entry_time"] for r in detail}
    for i in range(35,len(rows)):
        signal=exp83.is_major_long_to_short_reversal(highs,lows,closes,market,i) is not None
        if not signal:
            continue
        today=times[i][:10]
        next_open_time=times[i+1] if i+1<len(rows) else None
        row={
            "symbol":symbol,"signal_time":times[i],
            "ST_state_at_signal":st[i],
            "next_open_same_session":next_open_time is not None and next_open_time[:10]==today,
            "next_open_was_accepted_entry":next_open_time in active_entries,
            "signal_close":closes[i],
        }
        for h in HORIZONS:
            j=i+h
            valid=j<len(rows) and times[j][:10]==today
            row[f"signal_close_to_{h}_bars_short_pct"]=fmt(pchange(closes[i],closes[j])) if valid else None
        candidate_rows.append(row)
    candfields=[
        "symbol","signal_time","ST_state_at_signal",
        "next_open_same_session","next_open_was_accepted_entry","signal_close",
    ]+[f"signal_close_to_{h}_bars_short_pct" for h in HORIZONS]
    write_csv(OUT/(symbol.lower()+"_v16_candidates.csv"),candidate_rows,candfields)
    return {
        "candles":len(rows),"V16_candidates":candidates,
        "accepted_trades":len(trades),"winners":sum(r["net_pct"]>0 for r in detail),
        "losers":sum(r["net_pct"]<=0 for r in detail),
        "net_pct_sum":fmt(sum(r["net_pct"] for r in detail)),
        "exits":dict(Counter(r["exit_reason"] for r in detail)),
        "rejected":rejected,
        "all_trades":summarize(detail),
        "winners_only":summarize([r for r in detail if r["net_pct"]>0]),
        "losers_only":summarize([r for r in detail if r["net_pct"]<=0]),
        "ST_not_long_candidate_count":sum(r["ST_state_at_signal"]!="LONG" for r in candidate_rows),
    }
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    summary={
        "experiment":"EXP84",
        "research_only":True,
        "assumptions":"Reuses EXP83 baseline with unchanged V16/ST rules, 0.10% per side commission and 1.5% stop.",
        "warning":"All intratrade lows/highs and forward price paths are hindsight diagnostics; entry-bar full ranges may overstate available extrema. Data is small and previously studied.",
        "symbols":{},
    }
    for symbol,path in exp83.DATA.items():
        summary["symbols"][symbol]=audit_symbol(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print("EXP84 — V16 CROSS-SYMBOL ENTRY QUALITY — RESEARCH ONLY")
    print(json.dumps(summary,indent=2))
    print("Detailed CSV files:",OUT)
if __name__=="__main__":
    main()
