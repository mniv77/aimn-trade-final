#!/usr/bin/env python3
"""EXP110 — V16 SHORT losing-trade path audit, research only.

Replay unchanged V16. Distinguish no-profit-opportunity from profit giveback
using completed CLOSES (not intrabar lows). Classify with a stated 0.20%
round-trip commission threshold, not an optimized trading rule. Export full
same-session trade paths and causal warning snapshots; no orders or edits.
"""
import csv,json
from pathlib import Path
from collections import Counter
import aimn_exp83_v16_structural_exit as base
import aimn_exp93_sideways_research as exp93
import aimn_exp100_confirmed_swing_structure as exp100
import aimn_exp79_v16_early_exit as exp79

OUT=Path(__file__).resolve().parent/"kiss/results/exp110_losing_trade_paths"
ROUND_TRIP_FEE_PCT=2*exp79.FEE

def write(path,records):
    if not records:return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader();w.writerows(records)

def short_gross(entry,price):
    return 100*(entry/price-1)

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(set(times))!=len(times):raise AssertionError("Duplicate timestamps")
    index={t:i for i,t in enumerate(times)}
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    trades,_,_,_,_,_=exp93.simulate(rows,st,rsi,market,"BASELINE")
    original,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    if trades!=original:raise AssertionError(symbol+": baseline drift")
    starts=exp100.get_session_starts(times)
    pivh,pivl,counts=exp100.confirmed_pivots(rows,times,starts)
    paths=[]
    summary=[]
    for t in trades:
        if t["net_pnl_pct"]>0:continue
        entry_i=index[t["entry_time"]]
        exit_i=index[t["exit_time"]]
        entry=float(t["entry_price"])
        if exit_i<entry_i:raise AssertionError("Bad trade chronology")
        same_day=times[entry_i][:10]
        if times[exit_i][:10]!=same_day:raise AssertionError("Trade spans sessions")
        # completed closes available before actual exit; if exit fills at open
        # or intrabar stop, the exit bar close was NOT available.
        if t["exit_reason"] in ("STOP_LOSS","ST_REVERSE","RSI_RESCUE",
                                "EARLY_REBOUND","EARLY_REBOUND_BREAK"):
            last_observable=exit_i-1
        elif t["exit_reason"] in ("SESSION_END","DATA_END"):
            last_observable=exit_i
        else:
            # Conservative: unknown exit type does not observe exit-bar close
            last_observable=exit_i-1
        observed=list(range(entry_i,max(entry_i,last_observable+1)))
        # Include the actual entry open as a starting benchmark, not a close.
        best_close=min([entry]+[closes[i] for i in observed])
        best_close_gross=short_gross(entry,best_close)
        best_close_net=best_close_gross-ROUND_TRIP_FEE_PCT
        best_intrabar_low=min(lows[entry_i:exit_i+1])
        best_intrabar_gross=short_gross(entry,best_intrabar_low)
        classification=("PROFIT_GIVEBACK" if best_close_gross>ROUND_TRIP_FEE_PCT
                        else "FAILED_TO_COVER_FEES")
        best_close_i=min(observed,key=lambda i:closes[i]) if observed and min(closes[i] for i in observed)<entry else None
        first_fee_i=next((i for i in observed if short_gross(entry,closes[i])>ROUND_TRIP_FEE_PCT),None)
        # Hindsight summaries are separate from the per-candle causal features.
        row={
            "symbol":symbol,"entry_time":t["entry_time"],"exit_time":t["exit_time"],
            "exit_reason":t["exit_reason"],"entry_price":entry,
            "exit_price":t["exit_price"],"actual_net_pct":t["net_pnl_pct"],
            "bars_held":t["bars_held"],"classification_hindsight":classification,
            "best_observable_completed_close_gross_pct_hindsight":round(best_close_gross,6),
            "best_observable_completed_close_net_pct_hindsight":round(best_close_net,6),
            "best_observable_close_time_hindsight":times[best_close_i] if best_close_i is not None else None,
            "first_completed_close_above_fees_time_hindsight":times[first_fee_i] if first_fee_i is not None else None,
            "intrabar_best_low_pct_hindsight":round(best_intrabar_gross,6),
            "gross_giveback_from_best_close_to_exit_pp_hindsight":round(best_close_gross-t["gross_pnl_pct"],6),
            "exit_bar_close_excluded":last_observable<exit_i,
            "round_trip_commission_pct":ROUND_TRIP_FEE_PCT,
        }
        summary.append(row)
        lowest_close_so_far=entry
        for i in observed:
            lowest_close_so_far=min(lowest_close_so_far,closes[i])
            state=exp100.structure(rows,times,starts,i,pivh,pivl,counts)
            gross=short_gross(entry,closes[i])
            rebound=100*(closes[i]/lowest_close_so_far-1)
            st_flip=st[i-1]=="SHORT" and st[i]=="LONG" if i>entry_i else False
            rsi_rescue=rsi[i] is not None and rsi[i]>=exp79.RSI_LIMIT
            next_same=i+1<len(rows) and times[i+1][:10]==same_day
            paths.append({
                "symbol":symbol,"entry_time":t["entry_time"],
                "timestamp":times[i],"bars_since_entry":i-entry_i,
                "open":float(rows[i]["open"]),"high":highs[i],
                "low":lows[i],"close":closes[i],
                "short_gross_at_close_pct":round(gross,6),
                "short_net_if_close_fill_pct":round(gross-ROUND_TRIP_FEE_PCT,6),
                "best_close_gross_so_far_pct":round(short_gross(entry,lowest_close_so_far),6),
                "rebound_from_best_close_pct":round(rebound,6),
                "gross_above_round_trip_fee":gross>ROUND_TRIP_FEE_PCT,
                "st":st[i],"st_reversal_at_close":st_flip,
                "rsi":rsi[i],"rsi_rescue_at_close":rsi_rescue,
                "confirmed_swing_state":state["structure_state"],
                "close_above_confirmed_high":state["close_above_last_confirmed_high"],
                "close_below_confirmed_low":state["close_below_last_confirmed_low"],
                "next_same_session_bar_exists":next_same,
                "actual_exit_time_hindsight":t["exit_time"],
                "actual_exit_reason_hindsight":t["exit_reason"],
                "actual_net_pct_hindsight":t["net_pnl_pct"],
                "classification_hindsight":classification,
            })
    write(OUT/(symbol.lower()+"_losing_trades.csv"),summary)
    write(OUT/(symbol.lower()+"_losing_trade_candle_paths.csv"),paths)
    counts=Counter(r["classification_hindsight"] for r in summary)
    return {"total_trades":len(trades),"losing_trades":len(summary),
            "baseline_net_sum_pct":round(sum(t["net_pnl_pct"] for t in trades),6),
            "classification_counts":dict(counts),
            "exit_reasons":dict(Counter(r["exit_reason"] for r in summary)),
            "losers":summary}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"experiment":"EXP110","research_only":True,
            "classification_threshold_pct":ROUND_TRIP_FEE_PCT,
            "definitions":{
                "FAILED_TO_COVER_FEES":"No observable completed close during the actual holding interval had SHORT gross profit exceeding round-trip commissions.",
                "PROFIT_GIVEBACK":"At least one observable completed close exceeded round-trip commissions, but the trade eventually exited at a net loss.",
                "intrabar_low":"Diagnostic hindsight only; never used to classify a trade.",
            },
            "limitations":[
                "Close-based potential is not a guaranteed executable fill; next-open price can differ.",
                "Stop-loss and pending next-open exit bars are excluded from completed-close signals.",
                "Intrabar ordering and spread/slippage are unknown.",
                "Same previously studied NVDA/AAPL dataset; no holdout.",
                "This is a diagnostic classification, not an exit rule or a profit forecast.",
            ],"symbols":{}}
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP110 — V16 LOSING TRADE PATH FORENSICS — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"baseline trades:",s["total_trades"],
              "losers:",s["losing_trades"],"net sum:",s["baseline_net_sum_pct"])
        print(" CLASSIFICATION",s["classification_counts"])
        print(" EXIT REASONS",s["exit_reasons"])
        for t in s["losers"]:
            print(" LOSS",t["entry_time"],t["classification_hindsight"],
                  "net:",t["actual_net_pct"],
                  "best_completed_close_gross:",t["best_observable_completed_close_gross_pct_hindsight"],
                  "best_intrabar_gross:",t["intrabar_best_low_pct_hindsight"],
                  "exit:",t["exit_reason"],t["exit_time"])
    print("\nCSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
