#!/usr/bin/env python3
"""EXP125: exploratory fixed W12 strength grid, full chronological replay.

Research only. Predeclared W12 thresholds 0, 0.10, 0.20, 0.30 percent.
No hindsight signals. Same causal bars, fees, entries and safety exits.
These in-sample comparisons are NOT out-of-sample validation.
"""
import csv,json
from collections import Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp117_full_swing_replay as exp117
import aimn_exp121_joint_momentum_replay as exp121

OUT=Path(__file__).resolve().parent/"kiss/results/exp125_w12_strength_replay"
THRESHOLDS=(0.0,0.10,0.20,0.30)
FIELDS=("entry_time","exit_time","entry_price","exit_price","exit_reason",
        "gross_pnl_pct","net_pnl_pct","best_close_short_pct","bars_held")

def replay(rows,st,rsi,market,states,starts,threshold):
    closes=[float(r["close"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    times=[str(r["timestamp"]) for r in rows]
    n=len(rows);pos=None;pending=None;trades=[];signals=[]
    candidates=0;rejected=Counter();joint_rejected=Counter()
    exit_action="JOINT_SWING_W12_STRENGTH"
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
                # Normalize reason for strict parity with EXP121 at threshold zero.
                reason="JOINT_SWING_POSITIVE_W12" if action==exit_action else action
                trades.append(exp79.finish(pos,i,opens[i],reason,times))
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
                            m=exp121.momentum(rows,closes,starts,i)
                            if m is None:
                                joint_rejected["W12_UNAVAILABLE_SAME_SESSION"]+=1
                            elif m<=threshold:
                                joint_rejected["W12_NOT_ABOVE_THRESHOLD"]+=1
                            else:
                                pending=exit_action
                                signals.append({"entry_time":pos["entry_time"],
                                                "signal_time":times[i],
                                                "planned_exit_time":times[i+1],
                                                "w12_pct":round(m,6),
                                                "threshold_pct":threshold})
        candidate=base.is_major_long_to_short_reversal(highs,lows,closes,market,i) is not None
        if candidate:
            candidates+=1
            if pos is not None or exited_at_open or pending in (
                "ST_REVERSE","RSI_RESCUE",exit_action):
                reason="IN_TRADE_OR_EXITING"
            elif pending=="ENTER":reason="ALREADY_QUEUED"
            elif st[i]!="LONG":reason="ST_NOT_LONG"
            elif i+1>=n or times[i+1][:10]!=day:reason="SESSION_BOUNDARY"
            else:reason=None;pending="ENTER"
            if reason is not None:rejected[reason]+=1
    if pos is not None:
        trades.append(exp79.finish(pos,n-1,closes[-1],"DATA_END",times))
    return trades,signals,candidates,dict(rejected),dict(joint_rejected)

def write(path,records,fields):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)

def summary(trades,baseline):
    net=sum(t["net_pnl_pct"] for t in trades)
    return {"trades":len(trades),"winners":sum(t["net_pnl_pct"]>0 for t in trades),
            "losers":sum(t["net_pnl_pct"]<=0 for t in trades),
            "net_pct_sum":round(net,6),
            "delta_baseline_pp":round(net-baseline,6),
            "exit_reasons":dict(Counter(t["exit_reason"] for t in trades))}

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(set(times))!=len(times):raise AssertionError("Duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    starts=swing.get_session_starts(times)
    ph,pl,counts=swing.confirmed_pivots(rows,times,starts)
    states=[swing.structure(rows,times,starts,i,ph,pl,counts) for i in range(len(rows))]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    original,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    baseline,_,_,_=exp117.simulate(rows,st,rsi,market,states,"BASELINE")
    if original!=baseline:raise AssertionError(symbol+" baseline parity")
    original121,original_signals,_,_,_=exp121.replay(rows,st,rsi,market,states,starts)
    baseline_net=sum(t["net_pnl_pct"] for t in baseline)
    bybase={t["entry_time"]:t for t in baseline}
    results={};comparisons=[]
    for threshold in THRESHOLDS:
        trades,signals,cc,cr,blocks=replay(rows,st,rsi,market,states,starts,threshold)
        if threshold==0.0:
            if trades!=original121:raise AssertionError(symbol+" EXP121 zero-threshold trade parity")
            if [(x["entry_time"],x["signal_time"]) for x in signals]!=[
                (x["entry_time"],x["signal_time"]) for x in original_signals]:
                raise AssertionError(symbol+" EXP121 signal parity")
        by={t["entry_time"]:t for t in trades}
        if set(by)!=set(bybase):
            raise AssertionError(symbol+" entries changed at threshold "+str(threshold))
        tag=("%.2f"%threshold).replace(".","p")
        write(OUT/(symbol.lower()+"_w12_"+tag+"_trades.csv"),trades,FIELDS)
        write(OUT/(symbol.lower()+"_w12_"+tag+"_signals.csv"),signals,
              ("entry_time","signal_time","planned_exit_time","w12_pct","threshold_pct"))
        results[str(threshold)]={
            **summary(trades,baseline_net),
            "signals":len(signals),"momentum_rejections":blocks,
            "changed_exits_vs_baseline":sum(
                (by[e]["exit_time"],by[e]["exit_price"],by[e]["exit_reason"])!=
                (bybase[e]["exit_time"],bybase[e]["exit_price"],bybase[e]["exit_reason"])
                for e in by),
            "candidate_count":cc,"candidate_rejections":cr}
        for e in sorted(by):
            t=by[e];b=bybase[e]
            comparisons.append({
                "threshold_pct":threshold,"entry_time":e,
                "baseline_exit":b["exit_time"],"baseline_net_pct":b["net_pnl_pct"],
                "candidate_exit":t["exit_time"],"candidate_reason":t["exit_reason"],
                "candidate_net_pct":t["net_pnl_pct"],
                "delta_vs_baseline_pp":round(t["net_pnl_pct"]-b["net_pnl_pct"],6)})
    write(OUT/(symbol.lower()+"_trade_comparison.csv"),comparisons,
          ("threshold_pct","entry_time","baseline_exit","baseline_net_pct",
           "candidate_exit","candidate_reason","candidate_net_pct","delta_vs_baseline_pp"))
    return {"candles":len(rows),"baseline":summary(baseline,baseline_net),
            "thresholds":results}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP125","research_only":True,
        "hypothesis":"A minimum same-session completed-close W12 movement may distinguish meaningful upward reversals from weak structural warnings.",
        "predeclared_thresholds_pct":list(THRESHOLDS),
        "execution":"Causal signal at completed close; exit next same-session open; full replay.",
        "parity":"EXP83 baseline and EXP121 threshold-zero full trade and signal parity asserted.",
        "limitations":[
            "In-sample exploratory comparison; selecting best threshold here would overfit.",
            "No independent holdout data tested.",
            "Small number of affected trades, correlated signal observations.",
            "No slippage, short borrow fees, LONG, compounding or portfolio allocation.",
            "Stop, RSI, ST, session boundary and baseline fill assumptions retained."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP125 — W12 STRENGTH FULL CHRONOLOGICAL REPLAY — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n",symbol,"candles:",s["candles"],
              "baseline:",s["baseline"]["net_pct_sum"])
        for threshold,m in s["thresholds"].items():
            print(" threshold:",threshold,"trades:",m["trades"],
                  "winners:",m["winners"],"losers:",m["losers"],
                  "net:",m["net_pct_sum"],"delta baseline pp:",m["delta_baseline_pp"],
                  "signals:",m["signals"],"rejected:",m["momentum_rejections"],
                  "exits:",m["exit_reasons"])
    print("\nReports:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
