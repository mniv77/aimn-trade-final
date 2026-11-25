#!/usr/bin/env python3
"""EXP105 — Causal confirmed-structure exit strategy test.

Exploratory, in-sample, research only. Full V16 SHORT reruns with
unchanged entry logic, stop, RSI rescue, ST reverse, commissions and
session-end liquidation. Two explicitly exploratory exit variants:
- PHASE_ASCENDING: EXP93 armed/stalled/two-sideways warning AND two
  confirmed higher swing highs and higher swing lows.
- PHASE_ASCENDING_OR_BREAK: same warning AND either ascending swings
  OR a close above the latest confirmed swing high.

All pivot confirmations require two subsequent completed candles and
are only usable at their confirmation close. Exits fill at next same-
session open. No tuning based on future returns. Results are not OOS.
"""
import csv
import json
from collections import Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp93_sideways_research as exp93
import aimn_exp97_mountain_exit_test as exp97
import aimn_exp100_confirmed_swing_structure as exp100

OUT=Path(__file__).resolve().parent/"kiss/results/exp105_phase_exit_backtest"
VARIANTS=("PHASE_ASCENDING","PHASE_ASCENDING_OR_BREAK")

def simulate(rows,st,rsi,market,variant,states):
    if variant=="BASELINE":
        trades,_,_,_,_,_=exp93.simulate(rows,st,rsi,market,"BASELINE")
        return trades,[],Counter()
    if variant=="SIDEWAYS_EXIT":
        trades,_,_,_,events,_=exp93.simulate(rows,st,rsi,market,"SIDEWAYS_EXIT")
        return trades,events,Counter()
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    closes=[float(r["close"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    times=[str(r["timestamp"]) for r in rows]
    n=len(rows)
    sideways=[exp93.is_sideways(exp93.metrics(rows,i)) for i in range(n)]
    # Candidate phase confirmation is computed causally at each candle close.
    # Existing sideways / stall / profit conditions remain unchanged.
    pos=None
    pending=None
    trades=[]
    events=[]
    rejected=Counter()
    for i in range(35,n):
        day=times[i][:10]
        if day!=times[i-1][:10]:
            if pos is not None:
                trades.append(exp79.finish(pos,i-1,closes[i-1],"SESSION_END",times))
                pos=None
            pending=None
        exited_at_open=False
        if pending is not None:
            action=pending
            pending=None
            if action=="ENTER" and pos is None:
                pos={"entry_time":times[i],"entry_price":opens[i],
                     "entry_index":i,"lowest_close":opens[i],"last_new_low_i":i}
            elif action!="ENTER" and pos is not None:
                trades.append(exp79.finish(pos,i,opens[i],action,times))
                pos=None
                exited_at_open=True
        if pos is not None:
            stop_price=pos["entry_price"]*(1+exp79.STOP_PCT/100)
            if highs[i]>=stop_price:
                trades.append(exp79.finish(pos,i,max(stop_price,opens[i]),"STOP_LOSS",times))
                pos=None
                pending=None
            else:
                if closes[i]<pos["lowest_close"]:
                    pos["lowest_close"]=closes[i]
                    pos["last_new_low_i"]=i
                if i+1<n and times[i+1][:10]==day:
                    if st[i-1]=="SHORT" and st[i]=="LONG":
                        pending="ST_REVERSE"
                    elif rsi[i] is not None and rsi[i]>=exp79.RSI_LIMIT:
                        pending="RSI_RESCUE"
                    else:
                        armed=(pos["entry_price"]/pos["lowest_close"]-1)*100>exp93.PROFIT_ARM
                        stalled=i-pos["last_new_low_i"]>=exp93.MIN_STALL_BARS
                        two=i>0 and sideways[i] and sideways[i-1]
                        if armed and stalled and two:
                            state=states[i]
                            confirmed=(state["structure_state"]=="ASCENDING_SWINGS")
                            if variant=="PHASE_ASCENDING_OR_BREAK":
                                confirmed=confirmed or state["close_above_last_confirmed_high"]==1
                            if confirmed:
                                pending="PHASE_EXIT"
                                events.append({"entry_time":pos["entry_time"],
                                               "signal_time":times[i],
                                               "structure_state":state["structure_state"],
                                               "high_sequence":state["high_sequence"],
                                               "low_sequence":state["low_sequence"],
                                               "break_confirmed_high":state["close_above_last_confirmed_high"],
                                               "variant":variant})
                            else:
                                rejected["SIDEWAYS_WITHOUT_CONFIRMED_PHASE"]+=1
        signal=base.is_major_long_to_short_reversal(highs,lows,closes,market,i) is not None
        if signal:
            if pos is not None or exited_at_open or pending in ("ST_REVERSE","RSI_RESCUE","PHASE_EXIT"):
                pass
            elif pending=="ENTER":
                pass
            elif st[i]!="LONG":
                pass
            elif i+1>=n or times[i+1][:10]!=day:
                pass
            else:
                pending="ENTER"
    if pos is not None:
        trades.append(exp79.finish(pos,n-1,closes[-1],"DATA_END",times))
    return trades,events,rejected


def save(path,records):
    if not records:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

def summarize(trades):
    return exp97.summary(trades)

def compare(original,candidate):
    a={t["entry_time"]:t for t in original}
    b={t["entry_time"]:t for t in candidate}
    matched=sorted(set(a)&set(b))
    only_a=sorted(set(a)-set(b))
    only_b=sorted(set(b)-set(a))
    paired=[]
    for entry in matched:
        x,y=a[entry],b[entry]
        delta=round(y["net_pnl_pct"]-x["net_pnl_pct"],6)
        paired.append({"entry_time":entry,
                       "baseline_exit_time":x["exit_time"],
                       "candidate_exit_time":y["exit_time"],
                       "baseline_exit_reason":x["exit_reason"],
                       "candidate_exit_reason":y["exit_reason"],
                       "baseline_net_pct":x["net_pnl_pct"],
                       "candidate_net_pct":y["net_pnl_pct"],
                       "delta_pp":delta,
                       "changed":int((x["exit_time"],x["exit_price"],x["exit_reason"])!=
                                     (y["exit_time"],y["exit_price"],y["exit_reason"]))})
    changed=[r for r in paired if r["changed"]]
    unpaired_delta=sum(b[t]["net_pnl_pct"] for t in only_b)-sum(a[t]["net_pnl_pct"] for t in only_a)
    paired_delta=sum(r["delta_pp"] for r in paired)
    full_delta=sum(t["net_pnl_pct"] for t in candidate)-sum(t["net_pnl_pct"] for t in original)
    if abs(full_delta-paired_delta-unpaired_delta)>0.00002:
        raise AssertionError("Paired P&L reconciliation failed")
    return {"matched_entries":len(matched),"baseline_only_entries":len(only_a),
            "candidate_only_entries":len(only_b),
            "changed_exits":len(changed),
            "helped_changed_exits":sum(r["delta_pp"]>0 for r in changed),
            "hurt_changed_exits":sum(r["delta_pp"]<0 for r in changed),
            "paired_delta_pp":round(paired_delta,6),
            "unpaired_delta_pp":round(unpaired_delta,6),
            "entry_sets_identical":not only_a and not only_b},paired

def run_symbol(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    closes=[float(r["close"]) for r in rows]
    times=[str(r["timestamp"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    highs,lows,counts=exp100.confirmed_pivots(rows,times,exp100.get_session_starts(times))
    starts=exp100.get_session_starts(times)
    states=[exp100.structure(rows,times,starts,i,highs,lows,counts)
            for i in range(len(rows))]
    baseline,_,_=exp97.simulate(rows,st,rsi,market,"BASELINE")
    expected,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    if baseline!=expected:
        raise AssertionError(symbol+": baseline differs from EXP83")
    save(OUT/(symbol.lower()+"_baseline_trades.csv"),baseline)
    results={"BASELINE":{"summary":summarize(baseline)}}
    for variant in VARIANTS:
        trades,events,rejected=simulate(rows,st,rsi,market,variant,states)
        comparison,paired=compare(baseline,trades)
        save(OUT/(symbol.lower()+"_"+variant.lower()+"_trades.csv"),trades)
        save(OUT/(symbol.lower()+"_"+variant.lower()+"_paired.csv"),paired)
        save(OUT/(symbol.lower()+"_"+variant.lower()+"_signals.csv"),events)
        info={"summary":summarize(trades),
              "delta_vs_baseline_pp":round(sum(t["net_pnl_pct"] for t in trades)-
                                           sum(t["net_pnl_pct"] for t in baseline),6),
              "comparison":comparison,"signals":len(events),
              "rejected_warning_evaluations":rejected["SIDEWAYS_WITHOUT_CONFIRMED_PHASE"]}
        results[variant]=info
    return {"candles":len(rows),"variants":results}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"experiment":"EXP105","research_only":True,
            "methods":"Full V16 SHORT causal reruns. EXP93 warning plus confirmed swing phase. Next-open fills.",
            "pivot_confirmation_bars":exp100.RIGHT,
            "assumptions":"Same-session next-open exits, existing intrabar stop, RSI/ST exits, 0.10% per-side fee, no slippage.",
            "limitations":[
                "Only June-August 2026 NVDA/AAPL, already inspected; no independent holdout.",
                "The variants are exploratory and can be overfit to known failures.",
                "Swing confirmation necessarily lags the true pivot by two completed bars.",
                "An unchanged entry set is checked and reported, not assumed.",
                "P&L is sum of individual net trade percentages, not portfolio return.",
                "No LONG, TSLA, new dates, realistic liquidity or live deployment."
            ],"symbols":{}}
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run_symbol(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP105 — CONFIRMED PHASE EXIT — FULL STRATEGY BACKTEST — RESEARCH ONLY")
    for symbol,data in report["symbols"].items():
        print("\n"+symbol,"candles:",data["candles"])
        for name,v in data["variants"].items():
            s=v["summary"]
            print(" ",name,"trades:",s["trades"],"wins:",s["winners"],
                  "losses:",s["losers"],"net:",s["net_pct_sum"],
                  "reasons:",s["exit_reasons"])
            if name!="BASELINE":
                c=v["comparison"]
                print("   delta pp:",v["delta_vs_baseline_pp"],
                      "changed exits:",c["changed_exits"],
                      "helped:",c["helped_changed_exits"],
                      "hurt:",c["hurt_changed_exits"],
                      "entries match:",c["entry_sets_identical"],
                      "signals:",v["signals"],
                      "rejected warning evaluations:",v["rejected_warning_evaluations"])
    print("\nFiles:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
