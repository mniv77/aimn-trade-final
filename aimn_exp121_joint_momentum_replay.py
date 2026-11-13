#!/usr/bin/env python3
"""EXP121 — full chronological joint-swing plus positive W12 momentum replay.

Research only. Compare EXP83 baseline, EXP117 joint swing, and one predeclared
candidate: joint swing AND positive 12-completed-candle same-session close
movement. No threshold optimization. Existing stops, RSI, ST, session end,
fees and V16 entry logic unchanged. Signal close -> next same-session open.
"""
import csv,json
from collections import Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp117_full_swing_replay as exp117

OUT=Path(__file__).resolve().parent/"kiss/results/exp121_joint_momentum_replay"
TRADES=("entry_time","exit_time","entry_price","exit_price","exit_reason",
        "gross_pnl_pct","net_pnl_pct","best_close_short_pct","bars_held")

def write(path,items,fields):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader();w.writerows(items)

def momentum(rows,closes,starts,i):
    if i-11<starts[i]:return None
    return 100*(closes[i]/closes[i-11]-1)

def replay(rows,st,rsi,market,states,starts):
    closes=[float(r["close"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    times=[str(r["timestamp"]) for r in rows]
    n=len(rows)
    pos=None;pending=None;trades=[];signals=[]
    candidates=0;rejected=Counter();joint_rejected=Counter()
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
                pos=None;exited_at_open=True
        if pos is not None:
            stop=pos["entry_price"]*(1+exp79.STOP_PCT/100)
            if highs[i]>=stop:
                trades.append(exp79.finish(pos,i,max(stop,opens[i]),"STOP_LOSS",times))
                pos=None;pending=None
            else:
                pos["lowest_close"]=min(pos["lowest_close"],closes[i])
                if (pos["entry_price"]/closes[i]-1)*100>2*exp79.FEE:
                    pos["fee_cover_seen"]=True
                if i+1<n and times[i+1][:10]==day:
                    if st[i-1]=="SHORT" and st[i]=="LONG":
                        pending="ST_REVERSE"
                    elif rsi[i] is not None and rsi[i]>=exp79.RSI_LIMIT:
                        pending="RSI_RESCUE"
                    elif pos["fee_cover_seen"]:
                        state=states[i]
                        if (state["low_sequence"]=="HIGHER_LOW" and
                            state["close_above_last_confirmed_high"]==1):
                            m=momentum(rows,closes,starts,i)
                            if m is None:
                                joint_rejected["W12_UNAVAILABLE_SAME_SESSION"]+=1
                            elif m<=0:
                                joint_rejected["W12_NOT_POSITIVE"]+=1
                            else:
                                pending="JOINT_SWING_POSITIVE_W12"
                                signals.append({
                                    "entry_time":pos["entry_time"],
                                    "signal_time":times[i],
                                    "planned_exit_time":times[i+1],
                                    "w12_close_move_pct":round(m,6),
                                    "signal_gross_pct":round(100*(pos["entry_price"]/closes[i]-1),6),
                                    "low_sequence":state["low_sequence"],
                                    "high_sequence":state["high_sequence"],
                                })
        candidate=base.is_major_long_to_short_reversal(highs,lows,closes,market,i) is not None
        if candidate:
            candidates+=1
            if pos is not None or exited_at_open or pending in (
                "ST_REVERSE","RSI_RESCUE","JOINT_SWING_POSITIVE_W12"):
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
    return trades,signals,candidates,dict(rejected),dict(joint_rejected)

def metrics(trades,baseline_net):
    net=sum(t["net_pnl_pct"] for t in trades)
    return {"trades":len(trades),
            "winners":sum(t["net_pnl_pct"]>0 for t in trades),
            "losers":sum(t["net_pnl_pct"]<=0 for t in trades),
            "net_pct_sum":round(net,6),
            "delta_vs_baseline_pp":round(net-baseline_net,6),
            "exit_reasons":dict(Counter(t["exit_reason"] for t in trades)),
            "worst_trade_net_pct":round(min((t["net_pnl_pct"] for t in trades),default=0),6)}

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    closes=[float(r["close"]) for r in rows]
    starts=swing.get_session_starts(times)
    ph,pl,counts=swing.confirmed_pivots(rows,times,starts)
    states=[swing.structure(rows,times,starts,i,ph,pl,counts)
            for i in range(len(rows))]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    original,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    baseline,_,_,_=exp117.simulate(rows,st,rsi,market,states,"BASELINE")
    if original!=baseline:raise AssertionError(symbol+" baseline parity failure")
    structural,_,_,_=exp117.simulate(rows,st,rsi,market,states,"JOINT_SWING")
    candidate,signals,cc,cr,blocks=replay(rows,st,rsi,market,states,starts)
    net=sum(t["net_pnl_pct"] for t in baseline)
    base_by={t["entry_time"]:t for t in baseline}
    structural_by={t["entry_time"]:t for t in structural}
    cand_by={t["entry_time"]:t for t in candidate}
    comparison=[]
    for entry in sorted(set(base_by)|set(structural_by)|set(cand_by)):
        a=base_by.get(entry);b=structural_by.get(entry);c=cand_by.get(entry)
        comparison.append({
            "entry_time":entry,
            "baseline_exit":a["exit_time"] if a else None,
            "baseline_reason":a["exit_reason"] if a else None,
            "baseline_net":a["net_pnl_pct"] if a else None,
            "exp117_exit":b["exit_time"] if b else None,
            "exp117_reason":b["exit_reason"] if b else None,
            "exp117_net":b["net_pnl_pct"] if b else None,
            "exp121_exit":c["exit_time"] if c else None,
            "exp121_reason":c["exit_reason"] if c else None,
            "exp121_net":c["net_pnl_pct"] if c else None,
            "exp121_delta_vs_baseline_pp":round(c["net_pnl_pct"]-a["net_pnl_pct"],6)
                if a and c else None,
        })
    write(OUT/(symbol.lower()+"_baseline.csv"),baseline,TRADES)
    write(OUT/(symbol.lower()+"_exp117.csv"),structural,TRADES)
    write(OUT/(symbol.lower()+"_exp121.csv"),candidate,TRADES)
    write(OUT/(symbol.lower()+"_signals.csv"),signals,
          ("entry_time","signal_time","planned_exit_time","w12_close_move_pct",
           "signal_gross_pct","low_sequence","high_sequence"))
    write(OUT/(symbol.lower()+"_trade_comparison.csv"),comparison,
          tuple(comparison[0]) if comparison else ("entry_time",))
    changed=sum(
        (base_by[e]["exit_time"],base_by[e]["exit_price"],base_by[e]["exit_reason"])!=
        (cand_by[e]["exit_time"],cand_by[e]["exit_price"],cand_by[e]["exit_reason"])
        for e in set(base_by)&set(cand_by))
    return {
        "candles":len(rows),"baseline":metrics(baseline,net),
        "exp117_structural":metrics(structural,net),
        "exp121_joint_positive_w12":metrics(candidate,net),
        "exp121_delta_vs_exp117_pp":round(
            sum(t["net_pnl_pct"] for t in candidate)-
            sum(t["net_pnl_pct"] for t in structural),6),
        "exp121_exit_signals":len(signals),
        "joint_signal_momentum_rejections":blocks,
        "candidate_count":cc,"candidate_rejections":cr,
        "changed_matched_exits_vs_baseline":changed,
        "new_entries_vs_baseline":sorted(set(cand_by)-set(base_by)),
        "missing_entries_vs_baseline":sorted(set(base_by)-set(cand_by)),
        "entry_sets_match_baseline":set(base_by)==set(cand_by),
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP121","research_only":True,
        "hypothesis":"A completed-close confirmed higher low AND close above confirmed high, after fee cover, plus positive W12 completed-close move, may protect winners from premature exits.",
        "w12_definition":"100*(close[i]/close[i-11]-1), 12 same-session completed candle closes; strictly >0, no tuned threshold.",
        "execution":"Signal at completed close, exit next same-session open; full chronological entry replay.",
        "safety":"EXP83 baseline parity asserted; original intrabar 1.5% stop, RSI 80 rescue, ST reversal, session end, and 0.10% fee per side unchanged.",
        "limitations":[
            "Exploratory in-sample hypothesis motivated by EXP119 and EXP120.",
            "Positive outcome does not establish predictive validity; independent dates and symbols needed.",
            "No slippage, short borrow costs, LONG, compounding, or portfolio allocation.",
            "Session-end close and stop fills remain baseline modeling assumptions.",
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP121 — JOINT SWING + POSITIVE W12 FULL REPLAY — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n",symbol,"candles:",s["candles"])
        for key in ("baseline","exp117_structural","exp121_joint_positive_w12"):
            m=s[key]
            print(" ",key,"trades:",m["trades"],"winners:",m["winners"],
                  "losers:",m["losers"],"net:",m["net_pct_sum"],
                  "delta baseline pp:",m["delta_vs_baseline_pp"],
                  "exits:",m["exit_reasons"])
        print(" EXP121 minus EXP117 pp:",s["exp121_delta_vs_exp117_pp"],
              "signals:",s["exp121_exit_signals"],
              "rejected joint warnings:",s["joint_signal_momentum_rejections"])
        print(" changed exits:",s["changed_matched_exits_vs_baseline"],
              "new entries:",s["new_entries_vs_baseline"],
              "missing entries:",s["missing_entries_vs_baseline"])
    print("\nReports:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
