#!/usr/bin/env python3
"""EXP78B summary of EXP78 V16 exit groups and rejected signal forward paths.
Read-only audit; future price paths are hindsight diagnostics, never execution.
"""
import csv,json
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parent
P=ROOT/"kiss/results/exp78_v16_audit"
def read(name):
    with (P/name).open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))
def avg(xs):
    return round(sum(xs)/len(xs),4) if xs else None
def main():
    trades=read("v16_trade_audit.csv")
    rejected=read("v16_rejected_signal_audit.csv")
    groups=defaultdict(list)
    for t in trades:
        groups[t["exit_reason"]].append(t)
    exits={}
    for reason,rows in sorted(groups.items()):
        exits[reason]=dict(count=len(rows),
            net_pct_sum=round(sum(float(r["net_pct"]) for r in rows),4),
            mean_net_pct=avg([float(r["net_pct"]) for r in rows]),
            mean_giveback_pp=avg([float(r["potential_giveback_pp"]) for r in rows]),
            max_giveback_pp=max(round(float(r["potential_giveback_pp"]),4) for r in rows))
    reasons=defaultdict(list)
    for r in rejected:
        reasons[r["reason"]].append(r)
    rejects={}
    for reason,rows in sorted(reasons.items()):
        horizons={}
        for h in (3,6,12):
            observations=[r for r in rows if int(r[f"future_{h}_bars"])==h and
                          r[f"close_move_{h}_pct"] not in ("",None)]
            moves=[float(r[f"close_move_{h}_pct"]) for r in observations]
            horizons[str(h)]=dict(complete_horizon_signals=len(moves),
                close_lower_count=sum(x<0 for x in moves),
                close_higher_count=sum(x>0 for x in moves),
                mean_close_change_pct=avg(moves),
                warning="Close-to-close moves from signal time, NOT a filled trade or net P&L")
        rejects[reason]=dict(count=len(rows),horizons=horizons)
    report=dict(experiment="EXP78B",exit_groups=exits,rejected_groups=rejects,
        next_step="Audit timestamped trades and signals on chart before changing any entry/exit rules.",
        caveat="Only signals with complete same-day lookahead counted for each horizon; no transaction costs included in hypothetical forward moves.")
    (P/"breakdown.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP78B — V16 diagnostics by exit reason and rejection type")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
