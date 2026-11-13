#!/usr/bin/env python3
"""EXP120 — trade-balanced 12-candle momentum and joint-swing audit.

Research only; no thresholds selected and no altered exits. Includes all
20 EXP83 V16 SHORT baseline trades, not only seven EXP117 changed exits.
Snapshots use completed same-session candles only. Hindsight outcome labels
are separated from causal features.
"""
import csv,json
from collections import Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp117_full_swing_replay as exp117

OUT=Path(__file__).resolve().parent/"kiss/results/exp120_all_trade_momentum"
CHECKPOINTS=("ENTRY_PLUS_3","ENTRY_PLUS_6","ENTRY_PLUS_12",
             "FIRST_FEE_COVER","FEE_COVER_PLUS_3",
             "FEE_COVER_PLUS_6","FEE_COVER_PLUS_12",
             "FIRST_JOINT_SWING")
FIELDS=("symbol","entry_time","outcome_hindsight","checkpoint",
        "checkpoint_time","bars_since_entry","bars_since_fee_cover",
        "w12_close_move_pct","w12_close_position","w12_up_fraction",
        "w12_efficiency","w12_complete_same_session",
        "joint_swing_at_checkpoint","fee_cover_seen_at_checkpoint",
        "gross_at_checkpoint_close_pct","baseline_net_pct_hindsight",
        "baseline_exit_time_hindsight","baseline_exit_reason_hindsight")

def write(path,items,fields=None):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields or (list(items[0]) if items else []))
        w.writeheader();w.writerows(items)

def round6(x):
    return round(x,6) if x is not None else None

def short_gross(entry,price):
    return 100*(entry/price-1)

def snapshot(rows,closes,starts,i):
    # 12 completed bars, including current close, entirely in session.
    if i-11<starts[i]:
        return dict(w12_close_move_pct=None,w12_close_position=None,
                    w12_up_fraction=None,w12_efficiency=None,
                    w12_complete_same_session=False)
    seq=closes[i-11:i+1]
    hi=max(float(r["high"]) for r in rows[i-11:i+1])
    lo=min(float(r["low"]) for r in rows[i-11:i+1])
    path=sum(abs(seq[j]-seq[j-1]) for j in range(1,len(seq)))
    return dict(
        w12_close_move_pct=round6(100*(seq[-1]/seq[0]-1)),
        w12_close_position=round6((seq[-1]-lo)/(hi-lo)) if hi>lo else 0.5,
        w12_up_fraction=round6(sum(seq[j]>seq[j-1] for j in range(1,len(seq)))/11),
        w12_efficiency=round6(abs(seq[-1]-seq[0])/path) if path>0 else 0,
        w12_complete_same_session=True)

def classify(trade,fee_cover):
    if trade["net_pnl_pct"]>0:return "WINNER"
    return "LOSING_GIVEBACK" if fee_cover is not None else "NEVER_COVERED_FEES"

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    idx={t:i for i,t in enumerate(times)}
    if len(idx)!=len(times):raise AssertionError("Duplicate timestamps")
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
    if baseline!=parity:raise AssertionError(symbol+" baseline mismatch")
    joint,events,_,_=exp117.simulate(rows,st,rsi,market,states,"JOINT_SWING")
    joint_by_entry={t["entry_time"]:t for t in joint}
    event_by_entry={e["entry_time"]:e for e in events}
    records=[];trade_rows=[]
    for trade in baseline:
        ei=idx[trade["entry_time"]];xi=idx[trade["exit_time"]]
        entry=float(trade["entry_price"])
        # Last completed candle while the original position is open.
        # For next-open exits, exit candle itself is NOT observable as a
        # completed in-trade candle. For session close, it is.
        last=xi if trade["exit_reason"] in ("SESSION_END","DATA_END") else xi-1
        last=max(ei-1,last)
        eligible=[i for i in range(ei,last+1) if times[i][:10]==times[ei][:10]]
        fee=next((i for i in eligible
                  if short_gross(entry,closes[i])>2*exp79.FEE),None)
        category=classify(trade,fee)
        # First joint signal AFTER the fee cover and while baseline remains
        # active, even if EXP117 might have exited earlier. Avoid overriding
        # ST/RSI precedence or assuming an executable next open.
        joint_signal=None
        for i in eligible:
            if fee is None or i<fee:continue
            if i+1>=len(rows) or times[i+1][:10]!=times[i][:10]:continue
            if st[i-1]=="SHORT" and st[i]=="LONG":continue
            if rsi[i] is not None and rsi[i]>=exp79.RSI_LIMIT:continue
            state=states[i]
            if (state["low_sequence"]=="HIGHER_LOW" and
                state["close_above_last_confirmed_high"]==1):
                joint_signal=i;break
        checkpoints={
            "ENTRY_PLUS_3":ei+3,"ENTRY_PLUS_6":ei+6,
            "ENTRY_PLUS_12":ei+12,
            "FIRST_FEE_COVER":fee,
            "FEE_COVER_PLUS_3":fee+3 if fee is not None else None,
            "FEE_COVER_PLUS_6":fee+6 if fee is not None else None,
            "FEE_COVER_PLUS_12":fee+12 if fee is not None else None,
            "FIRST_JOINT_SWING":joint_signal,
        }
        captured={}
        for name in CHECKPOINTS:
            i=checkpoints[name]
            if i is None or i not in eligible:
                captured[name]=None
                continue
            state=states[i]
            metrics=snapshot(rows,closes,starts,i)
            joint_here=(state["low_sequence"]=="HIGHER_LOW" and
                        state["close_above_last_confirmed_high"]==1)
            row=dict(symbol=symbol,entry_time=trade["entry_time"],
                     outcome_hindsight=category,checkpoint=name,
                     checkpoint_time=times[i],
                     bars_since_entry=i-ei,
                     bars_since_fee_cover=i-fee if fee is not None and i>=fee else None,
                     **metrics,
                     joint_swing_at_checkpoint=joint_here,
                     fee_cover_seen_at_checkpoint=fee is not None and i>=fee,
                     gross_at_checkpoint_close_pct=round6(short_gross(entry,closes[i])),
                     baseline_net_pct_hindsight=trade["net_pnl_pct"],
                     baseline_exit_time_hindsight=trade["exit_time"],
                     baseline_exit_reason_hindsight=trade["exit_reason"])
            records.append(row);captured[name]=row
        actual_event=event_by_entry.get(trade["entry_time"])
        trade_rows.append({
            "symbol":symbol,"entry_time":trade["entry_time"],
            "baseline_exit_time":trade["exit_time"],
            "baseline_exit_reason":trade["exit_reason"],
            "baseline_net_pct":trade["net_pnl_pct"],
            "outcome_hindsight":category,
            "first_fee_cover_time":times[fee] if fee is not None else None,
            "first_joint_swing_during_baseline_time":
                times[joint_signal] if joint_signal is not None else None,
            "joint_swing_seen_during_baseline":joint_signal is not None,
            "exp117_joint_swing_exit_time":
                joint_by_entry[trade["entry_time"]]["exit_time"]
                if actual_event and trade["entry_time"] in joint_by_entry else None,
            "exp117_exit_changed":
                (joint_by_entry[trade["entry_time"]]["exit_time"],
                 joint_by_entry[trade["entry_time"]]["exit_price"],
                 joint_by_entry[trade["entry_time"]]["exit_reason"])!=
                (trade["exit_time"],trade["exit_price"],trade["exit_reason"])
                if trade["entry_time"] in joint_by_entry else None,
            "entry_plus_12_w12_move":
                captured["ENTRY_PLUS_12"]["w12_close_move_pct"]
                if captured["ENTRY_PLUS_12"] else None,
            "fee_plus_12_w12_move":
                captured["FEE_COVER_PLUS_12"]["w12_close_move_pct"]
                if captured["FEE_COVER_PLUS_12"] else None,
            "joint_signal_w12_move":
                captured["FIRST_JOINT_SWING"]["w12_close_move_pct"]
                if captured["FIRST_JOINT_SWING"] else None,
        })
    write(OUT/(symbol.lower()+"_all_trades.csv"),trade_rows)
    write(OUT/(symbol.lower()+"_checkpoints.csv"),records,FIELDS)
    groups={}
    for name in CHECKPOINTS:
        groups[name]={}
        for category in ("WINNER","LOSING_GIVEBACK","NEVER_COVERED_FEES"):
            group=[r for r in records if r["checkpoint"]==name and
                   r["outcome_hindsight"]==category]
            values=[r["w12_close_move_pct"] for r in group
                    if r["w12_close_move_pct"] is not None]
            groups[name][category]={
                "observations":len(group),
                "with_complete_w12":len(values),
                "mean_w12_move_pct":round6(sum(values)/len(values)) if values else None,
                "positive_w12_count":sum(v>0 for v in values),
                "negative_or_flat_w12_count":sum(v<=0 for v in values),
                "joint_swing_at_checkpoint_count":
                    sum(bool(r["joint_swing_at_checkpoint"]) for r in group),
            }
    return {
        "trades":len(baseline),
        "outcomes":dict(Counter(r["outcome_hindsight"] for r in trade_rows)),
        "first_joint_swing_baseline_count":
            sum(r["joint_swing_seen_during_baseline"] for r in trade_rows),
        "exp117_exit_changes":
            sum(bool(r["exp117_exit_changed"]) for r in trade_rows),
        "checkpoint_groups":groups,
        "all_trade_rows":trade_rows,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP120","research_only":True,
        "purpose":"Test the 12-candle momentum observation across all baseline trades without selecting a threshold.",
        "checkpoint_definition":"Entry +3/+6/+12, first completed fee-covering close, fee cover +3/+6/+12, first executable joint swing signal while baseline position is still open.",
        "causal_features":"12 completed same-session closes including checkpoint close; no future candles used in signals.",
        "outcomes":"WINNER, LOSING_GIVEBACK, NEVER_COVERED_FEES are hindsight labels only.",
        "limitations":[
            "NVDA and AAPL June-August 2026 only, SHORT V16 only.",
            "Checkpoints missing because trade already ended are excluded, not imputed.",
            "Joint-swing checkpoint is selected by a signal, not comparable to fixed-time checkpoints.",
            "This reuses in-sample data and cannot independently validate EXP119.",
            "No threshold tuning, execution modifications, slippage, compounding or production changes.",
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP120 — ALL-TRADE MOMENTUM AUDIT — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n",symbol,"trades:",s["trades"],
              "outcomes:",s["outcomes"],
              "first joint signals:",s["first_joint_swing_baseline_count"],
              "EXP117 exit changes:",s["exp117_exit_changes"])
        for cp in CHECKPOINTS:
            print(" ",cp)
            for category,v in s["checkpoint_groups"][cp].items():
                print("  ",category,"observed:",v["observations"],
                      "complete W12:",v["with_complete_w12"],
                      "mean W12:",v["mean_w12_move_pct"],
                      "positive:",v["positive_w12_count"],
                      "negative/flat:",v["negative_or_flat_w12_count"],
                      "joint:",v["joint_swing_at_checkpoint_count"])
    print("\nFiles:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
