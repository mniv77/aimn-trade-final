#!/usr/bin/env python3
"""EXP115 — first causal SHORT trend deterioration, research only.

Predeclared diagnostic warning definitions, not optimized thresholds.
Track each original V16 trade after its first completed fee-covering close.
Compare first next-open warning exits against the unchanged baseline, including
winner controls and missed/late warnings. No alternate chronological replay.
"""
import csv
import json
from pathlib import Path
from collections import Counter

import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79
import aimn_exp114_trade_balanced_checkpoints as exp114

OUT=Path(__file__).resolve().parent/"kiss/results/exp115_first_deterioration"
FEE=2*exp79.FEE
RULES=(
    "W6_UPWARD_TURN",
    "W12_UPWARD_TURN",
    "W6_UPWARD_AND_LOW_EFFICIENCY",
    "W12_UPWARD_AND_LOW_EFFICIENCY",
    "W6_LOSS_OF_INITIAL_MOMENTUM",
    "W12_LOSS_OF_INITIAL_MOMENTUM",
)

def write(path,records):
    if not records:return
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]))
        writer.writeheader();writer.writerows(records)

def gross(entry,price):
    return 100*(entry/price-1)

def values(rows,closes,starts,i,w):
    return exp114.snapshot(rows,closes,starts,i,w)

def warning(rule,cur,initial):
    if cur is None:return False
    if rule.endswith("UPWARD_TURN"):
        return cur["close_move_pct"]>0
    if rule.endswith("UPWARD_AND_LOW_EFFICIENCY"):
        # Fixed, descriptive half-efficiency boundary; not tuned.
        return cur["close_move_pct"]>0 and cur["directional_efficiency"]<0.5
    if rule.endswith("LOSS_OF_INITIAL_MOMENTUM"):
        # Decline in directional progress vs the first fee-cover snapshot,
        # plus nonnegative movement over the same window.
        return (initial is not None and
                cur["close_move_pct"]>=0 and
                cur["directional_efficiency"]<initial["directional_efficiency"])
    raise ValueError(rule)

def analyze(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    idx={t:i for i,t in enumerate(times)}
    if len(idx)!=len(times):raise AssertionError("Duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    opens=[float(r["open"]) for r in rows]
    starts=exp114.exp100.get_session_starts(times)
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    trades,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    inventory=[];events=[];per_trade=[]
    for t in trades:
        ei=idx[t["entry_time"]];xi=idx[t["exit_time"]]
        if times[ei][:10]!=times[xi][:10]:raise AssertionError("Cross-session trade")
        entry=float(t["entry_price"])
        # For next-open exits and stops, original exit bar close is unavailable.
        end=xi if t["exit_reason"] in ("SESSION_END","DATA_END") else xi-1
        fee_i=next((i for i in range(ei,end+1) if gross(entry,closes[i])>FEE),None)
        group=("WINNER_CONTROL" if t["net_pnl_pct"]>0 else
               "LOSING_GIVEBACK" if fee_i is not None else
               "NO_FEE_COVERING_CLOSE")
        inventory.append({
            "symbol":symbol,"entry_time":t["entry_time"],"exit_time":t["exit_time"],
            "group_hindsight":group,"original_net_pct":t["net_pnl_pct"],
            "first_fee_cover_time":times[fee_i] if fee_i is not None else None,
        })
        initial={w:values(rows,closes,starts,fee_i,w) if fee_i is not None else None
                 for w in (6,12)}
        for rule in RULES:
            w=6 if rule.startswith("W6") else 12
            first=None
            if fee_i is not None:
                for i in range(fee_i,end+1):
                    cur=values(rows,closes,starts,i,w)
                    if warning(rule,cur,initial[w]):
                        first=i;break
            next_i=first+1 if first is not None else None
            # A warning at the session-ending close is not actionable. A
            # next-open exit on the original exit candle is excluded to
            # avoid double-counting and intrabar stop timing ambiguity.
            executable=(next_i is not None and next_i<xi and
                        next_i<len(rows) and
                        times[next_i][:10]==times[first][:10])
            hypothetical=gross(entry,opens[next_i])-FEE if executable else None
            per_trade.append({
                "symbol":symbol,"rule":rule,"entry_time":t["entry_time"],
                "group_hindsight":group,"original_exit_time":t["exit_time"],
                "original_net_pct":t["net_pnl_pct"],
                "fee_cover_time":times[fee_i] if fee_i is not None else None,
                "first_warning_time":times[first] if first is not None else None,
                "bars_from_fee_to_first_warning":first-fee_i if first is not None else None,
                "gross_at_warning_close_pct":round(gross(entry,closes[first]),6)
                    if first is not None else None,
                "still_fee_covered_at_warning_close":
                    gross(entry,closes[first])>FEE if first is not None else None,
                "next_open_executable_before_original_exit":executable,
                "next_open_time":times[next_i] if executable else None,
                "hypothetical_next_open_net_pct":round(hypothetical,6)
                    if executable else None,
                "difference_vs_original_pp_hindsight":
                    round(hypothetical-t["net_pnl_pct"],6) if executable else None,
            })
            if first is not None:
                events.append({
                    "symbol":symbol,"rule":rule,"entry_time":t["entry_time"],
                    "group_hindsight":group,"first_warning_time":times[first],
                    "bars_from_fee_to_first_warning":first-fee_i,
                    "executable":executable,
                    "next_open_net_pct":round(hypothetical,6) if executable else None,
                    "original_net_pct_hindsight":t["net_pnl_pct"],
                    "difference_pp_hindsight":round(hypothetical-t["net_pnl_pct"],6)
                        if executable else None,
                })
    write(OUT/(symbol.lower()+"_trade_inventory.csv"),inventory)
    write(OUT/(symbol.lower()+"_first_warning_by_trade.csv"),per_trade)
    write(OUT/(symbol.lower()+"_warning_events.csv"),events)
    descriptives=[]
    for rule in RULES:
        for group in ("WINNER_CONTROL","LOSING_GIVEBACK","NO_FEE_COVERING_CLOSE"):
            subset=[r for r in per_trade if r["rule"]==rule and
                    r["group_hindsight"]==group]
            active=[r for r in subset if r["next_open_executable_before_original_exit"]]
            diffs=[r["difference_vs_original_pp_hindsight"] for r in active]
            descriptives.append({
                "symbol":symbol,"rule":rule,"group":group,
                "group_trades":len(subset),
                "first_warning_found_count":sum(r["first_warning_time"] is not None for r in subset),
                "first_warning_executable_count":len(active),
                "warning_not_executable_count":sum(
                    r["first_warning_time"] is not None and
                    not r["next_open_executable_before_original_exit"] for r in subset),
                "still_fee_covered_at_warning_close_count":sum(
                    r["still_fee_covered_at_warning_close"] is True for r in active),
                "helped_count_hindsight":sum(d>0 for d in diffs),
                "hurt_count_hindsight":sum(d<0 for d in diffs),
                "unchanged_count":sum(d==0 for d in diffs),
                "sum_delta_pp_hindsight":round(sum(diffs),6),
                "sum_hypothetical_next_open_net_pct":round(
                    sum(r["hypothetical_next_open_net_pct"] for r in active),6),
                "sum_original_net_on_triggered_trades_pct":round(
                    sum(r["original_net_pct"] for r in active),6),
            })
    write(OUT/(symbol.lower()+"_rule_descriptives.csv"),descriptives)
    return {
        "trades":len(trades),
        "baseline_net_sum_pct":round(sum(t["net_pnl_pct"] for t in trades),6),
        "groups":dict(Counter(r["group_hindsight"] for r in inventory)),
        "rule_group_descriptives":descriptives,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP115","research_only":True,
        "goal":"First completed-candle deterioration warning vs baseline for winners and givebacks.",
        "fee_cover_gross_pct":FEE,"rules":list(RULES),
        "limitations":[
            "All warnings use completed same-session candles; exits priced at subsequent open.",
            "Warning rules are predeclared diagnostics; no fitted or validated strategy.",
            "Winner/giveback labels are retrospective, not features.",
            "Fixed original entries and exits; alternate exits can change later entries.",
            "No warning before first fee-cover close; cannot fix never-profitable entries.",
            "A first warning on the original exit candle is not counted executable.",
            "The 0.5 efficiency cutoff is illustrative, not optimized or validated.",
            "Previously studied 20-trade sample only; no independent holdout.",
            "Summed trade returns are not compounded portfolio returns.",
        ],"symbols":{}
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=analyze(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP115 — FIRST CAUSAL SHORT TREND DETERIORATION — RESEARCH ONLY")
    for symbol,s in report["symbols"].items():
        print("\n",symbol,"trades:",s["trades"],"baseline net:",s["baseline_net_sum_pct"],
              "groups:",s["groups"])
        for row in s["rule_group_descriptives"]:
            if row["group"]=="NO_FEE_COVERING_CLOSE":continue
            print(" RULE",row["rule"],row["group"],
                  "executable:",row["first_warning_executable_count"],
                  "helped:",row["helped_count_hindsight"],
                  "hurt:",row["hurt_count_hindsight"],
                  "sum_delta_pp:",row["sum_delta_pp_hindsight"],
                  "still_fee_covered:",row["still_fee_covered_at_warning_close_count"])
    print("\nCSV and JSON:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
