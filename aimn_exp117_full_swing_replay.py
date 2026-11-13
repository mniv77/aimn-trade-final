#!/usr/bin/env python3
"""EXP117 — full chronological V16 SHORT replay of EXP116 joint swing rule.

Research only. Same entries, stop, ST, RSI, and session close as EXP83.
Candidate: after the first completed close covering commissions, a confirmed
higher low AND close above the last confirmed swing high, next-open exit.
Replays signal eligibility after early exits; no live orders or production edits.
"""
import csv,json
from collections import Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as swing

OUT=Path(__file__).resolve().parent/"kiss/results/exp117_full_replay"
FIELDS=("entry_time","exit_time","entry_price","exit_price","exit_reason",
        "gross_pnl_pct","net_pnl_pct","best_close_short_pct","bars_held")

def write(path,items):
    if not items:return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(items[0]))
        writer.writeheader();writer.writerows(items)

def simulate(rows,st,rsi,market,states,variant):
    closes=[float(r["close"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    times=[str(r["timestamp"]) for r in rows]
    n=len(rows)
    pos=None;pending=None;trades=[];events=[];candidates=0
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
            action=pending;pending=None
            if action=="ENTER" and pos is None:
                pos={"entry_time":times[i],"entry_price":opens[i],
                     "entry_index":i,"lowest_close":opens[i],
                     "fee_cover_seen":False}
            elif action!="ENTER" and pos is not None:
                trades.append(exp79.finish(pos,i,opens[i],action,times))
                pos=None
                exited_at_open=True
        if pos is not None:
            stop=pos["entry_price"]*(1+exp79.STOP_PCT/100)
            if highs[i]>=stop:
                trades.append(exp79.finish(pos,i,max(stop,opens[i]),"STOP_LOSS",times))
                pos=None;pending=None
            else:
                pos["lowest_close"]=min(pos["lowest_close"],closes[i])
                # Arming is based on an actually observed completed close,
                # never on the intrabar low or a future best close.
                if (pos["entry_price"]/closes[i]-1)*100>2*exp79.FEE:
                    pos["fee_cover_seen"]=True
                if i+1<n and times[i+1][:10]==day:
                    if st[i-1]=="SHORT" and st[i]=="LONG":
                        pending="ST_REVERSE"
                    elif rsi[i] is not None and rsi[i]>=exp79.RSI_LIMIT:
                        pending="RSI_RESCUE"
                    elif variant=="JOINT_SWING" and pos["fee_cover_seen"]:
                        state=states[i]
                        if (state["low_sequence"]=="HIGHER_LOW" and
                            state["close_above_last_confirmed_high"]==1):
                            pending="CONFIRMED_SWING_REVERSE"
                            events.append({
                                "entry_time":pos["entry_time"],
                                "signal_time":times[i],
                                "planned_exit_time":times[i+1],
                                "gross_at_signal_close_pct":
                                    round((pos["entry_price"]/closes[i]-1)*100,6),
                                "low_sequence":state["low_sequence"],
                                "high_sequence":state["high_sequence"],
                                "latest_low_confirmed_time":state["latest_low_confirmed_time"],
                                "latest_high_confirmed_time":state["latest_high_confirmed_time"],
                            })
        candidate=base.is_major_long_to_short_reversal(highs,lows,closes,market,i) is not None
        if candidate:
            candidates+=1
            if pos is not None or exited_at_open or pending in (
                "ST_REVERSE","RSI_RESCUE","CONFIRMED_SWING_REVERSE"):
                reason="IN_TRADE_OR_EXITING"
            elif pending=="ENTER":
                reason="ALREADY_QUEUED"
            elif st[i]!="LONG":
                reason="ST_NOT_LONG"
            elif i+1>=n or times[i+1][:10]!=day:
                reason="SESSION_BOUNDARY"
            else:
                reason=None;pending="ENTER"
            if reason is not None:rejected[reason]+=1
    if pos is not None:
        trades.append(exp79.finish(pos,n-1,closes[-1],"DATA_END",times))
    return trades,events,candidates,dict(rejected)

def summarize(trades,baseline_net):
    net=sum(t["net_pnl_pct"] for t in trades)
    return {
        "trades":len(trades),"winners":sum(t["net_pnl_pct"]>0 for t in trades),
        "losers":sum(t["net_pnl_pct"]<=0 for t in trades),
        "gross_pct_sum":round(sum(t["gross_pnl_pct"] for t in trades),6),
        "commissions_pct_sum":round(2*exp79.FEE*len(trades),6),
        "net_pct_sum":round(net,6),
        "delta_vs_baseline_pp":round(net-baseline_net,6),
        "worst_trade_net_pct":round(min((t["net_pnl_pct"] for t in trades),default=0),6),
        "exit_reasons":dict(Counter(t["exit_reason"] for t in trades)),
    }

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    starts=swing.get_session_starts(times)
    ph,pl,counts=swing.confirmed_pivots(rows,times,starts)
    states=[swing.structure(rows,times,starts,i,ph,pl,counts)
            for i in range(len(rows))]
    original,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    baseline,_,bc,br=simulate(rows,st,rsi,market,states,"BASELINE")
    if baseline!=original:
        for j,(a,b) in enumerate(zip(original,baseline)):
            if a!=b:raise AssertionError(symbol+" baseline drift trade "+str(j)+": "+str(a)+" != "+str(b))
        raise AssertionError(symbol+" baseline trade count drift")
    candidate,events,cc,cr=simulate(rows,st,rsi,market,states,"JOINT_SWING")
    entry_original={t["entry_time"] for t in baseline}
    entry_candidate={t["entry_time"] for t in candidate}
    base_by_entry={t["entry_time"]:t for t in baseline}
    cand_by_entry={t["entry_time"]:t for t in candidate}
    comparisons=[]
    for entry in sorted(entry_original|entry_candidate):
        a=base_by_entry.get(entry);b=cand_by_entry.get(entry)
        comparisons.append({
            "entry_time":entry,
            "baseline_exit_time":a["exit_time"] if a else None,
            "baseline_exit_reason":a["exit_reason"] if a else None,
            "baseline_net_pct":a["net_pnl_pct"] if a else None,
            "candidate_exit_time":b["exit_time"] if b else None,
            "candidate_exit_reason":b["exit_reason"] if b else None,
            "candidate_net_pct":b["net_pnl_pct"] if b else None,
            "matched_entry":a is not None and b is not None,
            "matched_entry_delta_pp":round(b["net_pnl_pct"]-a["net_pnl_pct"],6)
                if a and b else None,
        })
    write(OUT/(symbol.lower()+"_baseline_trades.csv"),baseline)
    write(OUT/(symbol.lower()+"_joint_swing_trades.csv"),candidate)
    write(OUT/(symbol.lower()+"_joint_swing_signals.csv"),events)
    write(OUT/(symbol.lower()+"_entry_comparison.csv"),comparisons)
    baseline_net=sum(t["net_pnl_pct"] for t in baseline)
    return {
        "candles":len(rows),
        "baseline":summarize(baseline,baseline_net),
        "joint_swing":summarize(candidate,baseline_net),
        "baseline_candidate_signals":bc,"joint_candidate_signals":cc,
        "baseline_rejections":br,"joint_rejections":cr,
        "joint_swing_exit_signals":len(events),
        "entry_sets_match":entry_original==entry_candidate,
        "new_entries":sorted(entry_candidate-entry_original),
        "missing_entries":sorted(entry_original-entry_candidate),
        "matched_entries":len(entry_original&entry_candidate),
        "changed_exits_on_matched_entries":sum(
            (base_by_entry[e]["exit_time"],base_by_entry[e]["exit_reason"],
             base_by_entry[e]["exit_price"])!=
            (cand_by_entry[e]["exit_time"],cand_by_entry[e]["exit_reason"],
             cand_by_entry[e]["exit_price"])
            for e in entry_original&entry_candidate),
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP117","research_only":True,
        "candidate":"First fee-covering completed SHORT close observed, then confirmed higher swing low AND close above most recent confirmed swing high; next same-session open exit.",
        "pivot_confirmation":{"left":swing.LEFT,"right":swing.RIGHT},
        "baseline_safety":"EXP83 baseline equality asserted; 1.5% intrabar stop, ST reverse, RSI 80 rescue, session close, 0.10% each side retained.",
        "limitations":[
            "In-sample exploratory rule selected after EXP116; positive results do not validate predictive power.",
            "All V16 entry eligibility recalculated after earlier exits, not fixed-entry counterfactuals.",
            "Stops use high/stop-or-open assumptions; same-candle execution is not tick-level verified.",
            "End-of-session liquidation at last candle close is a backtest assumption.",
            "No slippage, borrowing fees, portfolio allocation, or compounding.",
            "No unseen dates, new symbols, LONG trades or paper trading.",
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP117 — FULL CHRONOLOGICAL JOINT SWING REPLAY — RESEARCH ONLY")
    for symbol,data in report["symbols"].items():
        a=data["baseline"];b=data["joint_swing"]
        print("\n",symbol,"candles:",data["candles"],
              "baseline trades:",a["trades"],"baseline net:",a["net_pct_sum"],
              "candidate trades:",b["trades"],"candidate net:",b["net_pct_sum"],
              "delta pp:",b["delta_vs_baseline_pp"])
        print(" winners:",a["winners"],"->",b["winners"],
              "losers:",a["losers"],"->",b["losers"],
              "exit reasons:",b["exit_reasons"])
        print(" changed matched exits:",data["changed_exits_on_matched_entries"],
              "new entries:",data["new_entries"],
              "missing entries:",data["missing_entries"],
              "baseline verified:",True)
    print("\nCSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
