#!/usr/bin/env python3
"""EXP122 — causal joint-swing signal and rejected-warning audit.

Research only. Audit every joint-swing warning during the EXP121 chronological
position lifecycle, including W12-rejected warnings and the accepted signal.
Future movement is explicitly labeled hindsight and is not a signal feature.
No threshold fitting, new trading rule, or production modifications.
"""
import csv,json
from collections import Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp117_full_swing_replay as exp117
import aimn_exp121_joint_momentum_replay as exp121

OUT=Path(__file__).resolve().parent/"kiss/results/exp122_joint_signal_audit"

def write(path,records,columns):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=columns)
        w.writeheader();w.writerows(records)

def pct(a,b):
    return round(100*(a/b-1),6) if b else None

def momentum(closes,starts,i,n):
    if i-(n-1)<starts[i]:return None
    return pct(closes[i],closes[i-(n-1)])

def future(closes,times,i,n):
    j=i+n
    if j>=len(closes) or times[j][:10]!=times[i][:10]:return None
    return pct(closes[j],closes[i])

def audit(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(set(times))!=len(times):raise AssertionError("Duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    starts=swing.get_session_starts(times)
    ph,pl,counts=swing.confirmed_pivots(rows,times,starts)
    states=[swing.structure(rows,times,starts,i,ph,pl,counts)
            for i in range(len(rows))]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    baseline,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    parity,_,_,_=exp117.simulate(rows,st,rsi,market,states,"BASELINE")
    if baseline!=parity:raise AssertionError(symbol+" baseline parity")
    candidate,accepted,_,_,blocks=exp121.replay(rows,st,rsi,market,states,starts)
    by_entry={t["entry_time"]:t for t in baseline}
    cand_by={t["entry_time"]:t for t in candidate}
    if set(by_entry)!=set(cand_by):raise AssertionError(symbol+" entry set changed")
    index={t:i for i,t in enumerate(times)}
    # The audit's eligibility is the baseline's open-trade interval.
    # This includes warnings EXP121 would not see after an earlier exit.
    # They are marked explicitly and never counted as EXP121 rejects.
    accepted_set={(x["entry_time"],x["signal_time"]) for x in accepted}
    records=[]
    for t in baseline:
        entry=t["entry_time"];ei=index[entry];xi=index[t["exit_time"]]
        last=xi if t["exit_reason"] in ("SESSION_END","DATA_END") else xi-1
        last=min(last,len(rows)-2)
        fee_seen=False;best=0.0
        cand_exit_i=index[cand_by[entry]["exit_time"]]
        for i in range(ei,max(ei,last+1)):
            if times[i][:10]!=times[ei][:10]:continue
            gross=100*(float(t["entry_price"])/closes[i]-1)
            best=max(best,gross)
            if gross>2*exp79.FEE:fee_seen=True
            if not fee_seen:continue
            if times[i+1][:10]!=times[i][:10]:continue
            if st[i-1]=="SHORT" and st[i]=="LONG":continue
            if rsi[i] is not None and rsi[i]>=exp79.RSI_LIMIT:continue
            s=states[i]
            if not (s["low_sequence"]=="HIGHER_LOW" and
                    s["close_above_last_confirmed_high"]==1):continue
            m12=momentum(closes,starts,i,12)
            m6=momentum(closes,starts,i,6)
            m24=momentum(closes,starts,i,24)
            prev12=momentum(closes,starts,i-6,12) if i>=6 else None
            active_in_exp121=(i<cand_exit_i)
            is_accepted=(entry,times[i]) in accepted_set
            if is_accepted:status="EXP121_ACCEPTED"
            elif not active_in_exp121:status="BASELINE_ONLY_AFTER_EXP121_EXIT"
            elif m12 is None:status="EXP121_REJECTED_W12_UNAVAILABLE"
            elif m12<=0:status="EXP121_REJECTED_W12_NONPOSITIVE"
            else:status="POSITIVE_W12_BUT_OTHER_PRECEDENCE"
            # Future labels are separate from causal columns.
            records.append({
                "symbol":symbol,"entry_time":entry,"signal_time":times[i],
                "status":status,
                "baseline_outcome_hindsight":"WINNER" if t["net_pnl_pct"]>0 else "LOSER",
                "baseline_net_pct_hindsight":round(t["net_pnl_pct"],6),
                "candidate_net_pct_hindsight":round(cand_by[entry]["net_pnl_pct"],6),
                "candidate_minus_baseline_pp_hindsight":
                    round(cand_by[entry]["net_pnl_pct"]-t["net_pnl_pct"],6),
                "bars_since_entry":i-ei,
                "signal_gross_pct":round(gross,6),
                "best_gross_by_signal_pct":round(best,6),
                "giveback_by_signal_pp":round(best-gross,6),
                "w6_move_pct":m6,"w12_move_pct":m12,"w24_move_pct":m24,
                "w12_six_bars_earlier_pct":prev12,
                "w12_change_vs_six_bars_earlier_pp":
                    round(m12-prev12,6) if m12 is not None and prev12 is not None else None,
                "higher_low_pct":pct(s["latest_low_price"],s["previous_low_price"])
                    if s.get("latest_low_price") and s.get("previous_low_price") else None,
                "break_above_confirmed_high_pct":
                    pct(closes[i],s["latest_high_price"])
                    if s.get("latest_high_price") else None,
                "next_3_close_move_pct_hindsight":future(closes,times,i,3),
                "next_6_close_move_pct_hindsight":future(closes,times,i,6),
                "next_12_close_move_pct_hindsight":future(closes,times,i,12),
            })
    columns=list(records[0]) if records else [
        "symbol","entry_time","signal_time","status"]
    write(OUT/(symbol.lower()+"_all_joint_warnings.csv"),records,columns)
    selected=[r for r in records if r["status"]=="EXP121_ACCEPTED"]
    write(OUT/(symbol.lower()+"_accepted.csv"),selected,columns)
    rejected=[r for r in records if r["status"].startswith("EXP121_REJECTED")]
    write(OUT/(symbol.lower()+"_rejected.csv"),rejected,columns)
    return {
        "baseline_trades":len(baseline),
        "exp121_trades":len(candidate),
        "warnings_during_baseline":len(records),
        "status_counts":dict(Counter(r["status"] for r in records)),
        "accepted_signals_from_exp121":len(accepted),
        "accepted_signals_reconciled":len(selected),
        "exp121_rejection_counts":blocks,
        "selected_signal_details":[{
            "entry":r["entry_time"],"signal":r["signal_time"],
            "status":r["status"],"w6":r["w6_move_pct"],
            "w12":r["w12_move_pct"],"w24":r["w24_move_pct"],
            "w12_change":r["w12_change_vs_six_bars_earlier_pp"],
            "giveback":r["giveback_by_signal_pp"],
            "delta_pp_hindsight":r["candidate_minus_baseline_pp_hindsight"],
        } for r in records if r["status"]=="EXP121_ACCEPTED" or
            (r["status"].startswith("EXP121_REJECTED") and
             r["entry_time"] in by_entry)],
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={
        "experiment":"EXP122","research_only":True,
        "goal":"Audit every causal joint-swing warning during baseline open positions, including accepted and rejected EXP121 signals.",
        "scope_note":"Warnings after EXP121 exited but before baseline exit are baseline-only observations, not EXP121 rejections.",
        "hindsight_note":"Baseline/candidate PnL and next 3/6/12 price moves are future outcome labels, never usable as features.",
        "limitations":[
            "In-sample NVDA/AAPL historical data, tiny number of affected trades.",
            "A warning may repeat on successive candles; rows are not independent observations.",
            "Only full chronological replay can establish an altered exit's actual PnL.",
            "No new strategy, threshold optimization, or production changes."
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        result["symbols"][symbol]=audit(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("EXP122 — JOINT SIGNAL AUDIT — RESEARCH ONLY")
    for symbol,s in result["symbols"].items():
        print("\n",symbol,"baseline trades:",s["baseline_trades"],
              "warnings:",s["warnings_during_baseline"],
              "statuses:",s["status_counts"])
        print(" accepted signals:",s["accepted_signals_from_exp121"],
              "reconciled:",s["accepted_signals_reconciled"],
              "EXP121 rejected:",s["exp121_rejection_counts"])
        for row in s["selected_signal_details"]:
            print(" ",row["entry"],row["signal"],row["status"],
                  "w6:",row["w6"],"w12:",row["w12"],
                  "w24:",row["w24"],"w12 change:",row["w12_change"],
                  "giveback:",row["giveback"],
                  "trade delta pp (hindsight):",row["delta_pp_hindsight"])
    print("\nFiles:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
