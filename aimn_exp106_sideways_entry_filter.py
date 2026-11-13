#!/usr/bin/env python3
"""EXP106 — Sideways ENTRY filter, blocked-winner / avoided-loser audit.

Research only. Reuses EXP93's pre-existing 12-bar efficiency and displacement
filter without tuning. Full strategy reruns; existing V16 SHORT exits unchanged.
The baseline is checked against EXP83 byte-for-byte trade dictionaries.
Historical baseline trades absent from filtered run are NOT automatically
'avoided losers': report their baseline outcomes, plus all replacement entries.
No production code changes.
"""
import csv
import json
from pathlib import Path
from collections import Counter
import aimn_exp83_v16_structural_exit as base
import aimn_exp93_sideways_research as exp93

OUT=Path(__file__).resolve().parent/"kiss/results/exp106_sideways_entry_filter"

def write_csv(path,records,fields=None):
    if not records and not fields:
        return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields or list(records[0]))
        w.writeheader()
        w.writerows(records)

def stats(trades):
    return {"trades":len(trades),
            "winners":sum(t["net_pnl_pct"]>0 for t in trades),
            "losers":sum(t["net_pnl_pct"]<=0 for t in trades),
            "net_sum_pct":round(sum(t["net_pnl_pct"] for t in trades),6),
            "gross_sum_pct":round(sum(t["gross_pnl_pct"] for t in trades),6),
            "worst_net_pct":round(min((t["net_pnl_pct"] for t in trades),default=0),6),
            "exit_reasons":dict(Counter(t["exit_reason"] for t in trades))}

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    baseline,candidates,rejections,baseline_audit,_,_=exp93.simulate(rows,st,rsi,market,"BASELINE")
    filtered,filtered_candidates,filtered_rejections,filtered_audit,_,_=exp93.simulate(
        rows,st,rsi,market,"ENTRY_FILTER")
    expected,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    if baseline!=expected:
        raise AssertionError(symbol+": baseline mismatch with EXP83")
    if candidates!=filtered_candidates:
        raise AssertionError(symbol+": entry candidate count changed")
    if len({t["entry_time"] for t in baseline})!=len(baseline):
        raise AssertionError("Duplicate baseline entry")
    if len({t["entry_time"] for t in filtered})!=len(filtered):
        raise AssertionError("Duplicate filtered entry")
    a={t["entry_time"]:t for t in baseline}
    b={t["entry_time"]:t for t in filtered}
    matched=sorted(set(a)&set(b))
    removed=sorted(set(a)-set(b))
    added=sorted(set(b)-set(a))
    blocked=[r for r in filtered_audit if r["decision"]=="SIDEWAYS_FILTER"]
    # Baseline trade entries are executed one bar after signal; link the
    # baseline's accepted signal to its next-session-local entry time.
    baseline_accepted=[r for r in baseline_audit if r["decision"]=="ACCEPTED"]
    signal_to_entry={}
    time_to_i={str(r["timestamp"]):i for i,r in enumerate(rows)}
    for r in baseline_accepted:
        i=time_to_i[r["signal_time"]]
        if i+1<len(rows) and str(rows[i+1]["timestamp"])[:10]==str(rows[i]["timestamp"])[:10]:
            signal_to_entry[str(rows[i+1]["timestamp"])]=r
    removed_audit=[]
    for entry in removed:
        t=a[entry]
        sig=signal_to_entry.get(entry)
        removed_audit.append({
            "entry_time":entry,
            "signal_time":sig["signal_time"] if sig else "",
            "sideways_at_baseline_signal":sig["sideways"] if sig else "",
            "efficiency":sig["efficiency"] if sig else "",
            "displacement_fraction":sig["displacement_fraction"] if sig else "",
            "baseline_exit_time":t["exit_time"],
            "baseline_exit_reason":t["exit_reason"],
            "baseline_net_pct":t["net_pnl_pct"],
            "baseline_winner":t["net_pnl_pct"]>0,
            "note":"Absent from filtered run; may be directly blocked or indirectly displaced"
        })
    added_audit=[{"entry_time":entry,"exit_time":b[entry]["exit_time"],
                  "exit_reason":b[entry]["exit_reason"],
                  "net_pnl_pct":b[entry]["net_pnl_pct"]} for entry in added]
    paired=[]
    for entry in matched:
        x,y=a[entry],b[entry]
        paired.append({"entry_time":entry,
                       "baseline_exit":x["exit_time"],
                       "filtered_exit":y["exit_time"],
                       "baseline_net_pct":x["net_pnl_pct"],
                       "filtered_net_pct":y["net_pnl_pct"],
                       "delta_pp":round(y["net_pnl_pct"]-x["net_pnl_pct"],6)})
    blocked_signal_times={r["signal_time"] for r in blocked}
    directly_blocked=[r for r in removed_audit if r["signal_time"] in blocked_signal_times]
    baseline_net=sum(t["net_pnl_pct"] for t in baseline)
    filtered_net=sum(t["net_pnl_pct"] for t in filtered)
    reconciled=(sum(r["delta_pp"] for r in paired)+
                sum(b[t]["net_pnl_pct"] for t in added)-
                sum(a[t]["net_pnl_pct"] for t in removed))
    if abs(filtered_net-baseline_net-reconciled)>0.00002:
        raise AssertionError(symbol+": trade-level reconciliation failed")
    write_csv(OUT/(symbol.lower()+"_baseline_trades.csv"),baseline)
    write_csv(OUT/(symbol.lower()+"_filtered_trades.csv"),filtered)
    write_csv(OUT/(symbol.lower()+"_blocked_signals.csv"),blocked)
    write_csv(OUT/(symbol.lower()+"_removed_baseline_entries.csv"),removed_audit)
    write_csv(OUT/(symbol.lower()+"_new_filtered_entries.csv"),added_audit)
    write_csv(OUT/(symbol.lower()+"_matched_entries.csv"),paired)
    monthly=[]
    for month in sorted({str(r["timestamp"])[:7] for r in rows}):
        ba=[t for t in baseline if t["entry_time"][:7]==month]
        fi=[t for t in filtered if t["entry_time"][:7]==month]
        month_blocked=[r for r in blocked if r["signal_time"][:7]==month]
        monthly.append({"month":month,"baseline_trades":len(ba),"filtered_trades":len(fi),
                        "baseline_net_pct":round(sum(t["net_pnl_pct"] for t in ba),6),
                        "filtered_net_pct":round(sum(t["net_pnl_pct"] for t in fi),6),
                        "blocked_signals":len(month_blocked)})
    write_csv(OUT/(symbol.lower()+"_monthly.csv"),monthly)
    return {
        "candles":len(rows),"candidate_signals":candidates,
        "sideways_thresholds":{"window":exp93.WINDOW,
            "max_efficiency":exp93.EFF_MAX,
            "max_displacement_fraction":exp93.DISPLACEMENT_FRACTION_MAX},
        "baseline":stats(baseline),"filtered":stats(filtered),
        "net_delta_pp":round(filtered_net-baseline_net,6),
        "blocked_candidate_signals":len(blocked),
        "blocked_signals_while_baseline_accepted":sum(
            r["signal_time"] in {x["signal_time"] for x in baseline_accepted} for r in blocked),
        "removed_baseline_entries":len(removed),
        "removed_baseline_winners":sum(a[t]["net_pnl_pct"]>0 for t in removed),
        "removed_baseline_losers":sum(a[t]["net_pnl_pct"]<=0 for t in removed),
        "directly_blocked_baseline_entries":len(directly_blocked),
        "new_filtered_entries":len(added),
        "matched_entries":len(matched),
        "changed_matched_exit_times":sum(a[t]["exit_time"]!=b[t]["exit_time"] for t in matched),
        "monthly":monthly
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={"experiment":"EXP106","research_only":True,
        "method":"EXP93 pre-existing sideways entry filter only, full causal V16 SHORT strategy reruns.",
        "execution":"Completed-bar signals, next same-session open, same original stop/ST/RSI/session exits and 0.10% fee per side.",
        "limitations":[
            "June-August 2026 previously studied; not independent validation.",
            "Blocked candidate signals are not identical to removed baseline trades.",
            "Removed baseline trades can be indirectly displaced by changed position state.",
            "A later replacement entry can occur; full rerun captures this.",
            "Trade-return sums are not portfolio returns.",
            "No slippage, LONG test, additional symbols, or live changes."
        ],"symbols":{}}
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP106 — SIDEWAYS ENTRY FILTER — FULL V16 BACKTEST — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n"+symbol,"candles:",s["candles"],"candidates:",s["candidate_signals"])
        print(" BASELINE:",s["baseline"])
        print(" FILTERED:",s["filtered"])
        print(" delta pp:",s["net_delta_pp"],
              "blocked candidate signals:",s["blocked_candidate_signals"],
              "blocked baseline-accepted signals:",s["blocked_signals_while_baseline_accepted"])
        print(" removed baseline entries:",s["removed_baseline_entries"],
              "of which winners:",s["removed_baseline_winners"],
              "losers:",s["removed_baseline_losers"],
              "directly blocked:",s["directly_blocked_baseline_entries"])
        print(" new filtered entries:",s["new_filtered_entries"],
              "matched entries:",s["matched_entries"],
              "changed matched exits:",s["changed_matched_exit_times"])
        for m in s["monthly"]:
            print(" month",m["month"],"baseline:",m["baseline_trades"],
                  "filtered:",m["filtered_trades"],
                  "baseline net:",m["baseline_net_pct"],
                  "filtered net:",m["filtered_net_pct"],
                  "blocked signals:",m["blocked_signals"])
    print("\nDetailed files:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":
    main()
