#!/usr/bin/env python3
"""EXP93 — causal sideways entry and in-position exit audit.

Independent RESEARCH ONLY; no live orders or production edits.
All entry/exit decisions use completed bars, executed at next session-local
open. EXP83 baseline is replayed exactly. The new variants are full strategy
reruns, not subsets of baseline trade outcomes. Stops/RSI/ST remain active.

Rules are hypotheses, not fitted thresholds. Sideways means low price-path
efficiency AND small net displacement relative to the session-local high/low
range. Exit variants require two consecutive completed sideways readings,
at least 0.20% gross favorable close excursion, and no new favorable close
for >= 3 bars. Early session insufficient windows are never called sideways.
"""
import csv
import json
from collections import Counter
from pathlib import Path

import aimn_exp83_v16_structural_exit as base
import aimn_exp79_v16_early_exit as exp79

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "kiss/results/exp93_sideways_research"
WINDOW = 12
EFF_MAX = 0.22
DISPLACEMENT_FRACTION_MAX = 0.32
MIN_HEIGHT_PCT = 0.0
MIN_STALL_BARS = 3
PROFIT_ARM = 2 * exp79.FEE
VARIANTS = ("BASELINE", "ENTRY_FILTER", "SIDEWAYS_EXIT", "COMBINED")

def metrics(rows, i):
    if i < WINDOW-1:
        return None
    part = rows[i-WINDOW+1:i+1]
    day = str(rows[i]["timestamp"])[:10]
    if any(str(r["timestamp"])[:10] != day for r in part):
        return None
    c = [float(r["close"]) for r in part]
    h = max(float(r["high"]) for r in part)
    l = min(float(r["low"]) for r in part)
    net = abs(c[-1]-c[0])
    path = sum(abs(c[k]-c[k-1]) for k in range(1,len(c)))
    height = 100*(h/l-1) if l else 0
    return {
        "height_pct":height,
        "efficiency":net/path if path else 0,
        "displacement_fraction":net/(h-l) if h>l else 0,
        "signed_slope_pct_per_5m":100*(c[-1]/c[0]-1)/(WINDOW-1) if c[0] else 0,
    }

def is_sideways(m):
    return m is not None and m["efficiency"] <= EFF_MAX and m["displacement_fraction"] <= DISPLACEMENT_FRACTION_MAX

def simulate(rows, st, rsi, market, variant):
    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]
    closes = [float(r["close"]) for r in rows]
    opens = [float(r["open"]) for r in rows]
    times = [str(r["timestamp"]) for r in rows]
    n = len(rows)
    geometries = [metrics(rows, i) for i in range(n)]
    sideways = [is_sideways(m) for m in geometries]
    filter_entry = variant in ("ENTRY_FILTER", "COMBINED")
    exit_sideways = variant in ("SIDEWAYS_EXIT", "COMBINED")
    pos = None
    pending = None
    trades = []
    candidates = 0
    rejected = Counter()
    exit_audit = []
    entry_audit = []
    for i in range(35,n):
        day = times[i][:10]
        if day != times[i-1][:10]:
            if pos is not None:
                trades.append(exp79.finish(pos, i-1, closes[i-1], "SESSION_END", times))
                pos = None
            pending = None
        exited_at_open = False
        if pending is not None:
            action = pending
            pending = None
            if action == "ENTER" and pos is None:
                pos = {"entry_time":times[i],"entry_price":opens[i],
                       "entry_index":i,"lowest_close":opens[i],
                       "last_new_low_i":i}
            elif action != "ENTER" and pos is not None:
                trades.append(exp79.finish(pos,i,opens[i],action,times))
                pos = None
                exited_at_open = True
        if pos is not None:
            stop_price = pos["entry_price"]*(1+exp79.STOP_PCT/100)
            if highs[i] >= stop_price:
                trades.append(exp79.finish(pos,i,max(stop_price,opens[i]),"STOP_LOSS",times))
                pos = None
                pending = None
            else:
                if closes[i] < pos["lowest_close"]:
                    pos["lowest_close"] = closes[i]
                    pos["last_new_low_i"] = i
                if i+1<n and times[i+1][:10] == day:
                    if st[i-1] == "SHORT" and st[i] == "LONG":
                        pending = "ST_REVERSE"
                    elif rsi[i] is not None and rsi[i] >= exp79.RSI_LIMIT:
                        pending = "RSI_RESCUE"
                    elif exit_sideways:
                        armed = (pos["entry_price"]/pos["lowest_close"]-1)*100 > PROFIT_ARM
                        stall = i-pos["last_new_low_i"] >= MIN_STALL_BARS
                        two = i>0 and sideways[i] and sideways[i-1]
                        if armed and stall and two:
                            pending = "SIDEWAYS_EXIT"
                            exit_audit.append({
                                "entry_time":pos["entry_time"],"signal_time":times[i],
                                "gross_best_close_pct":round((pos["entry_price"]/pos["lowest_close"]-1)*100,6),
                                "efficiency":round(geometries[i]["efficiency"],6),
                                "displacement_fraction":round(geometries[i]["displacement_fraction"],6),
                            })
        signal = base.is_major_long_to_short_reversal(highs,lows,closes,market,i) is not None
        if signal:
            candidates += 1
            reason = None
            if pos is not None or exited_at_open or pending in ("ST_REVERSE","RSI_RESCUE","SIDEWAYS_EXIT"):
                reason = "IN_TRADE_OR_EXITING"
            elif pending == "ENTER":
                reason = "ALREADY_QUEUED"
            elif st[i] != "LONG":
                reason = "ST_NOT_LONG"
            elif i+1>=n or times[i+1][:10] != day:
                reason = "SESSION_BOUNDARY"
            elif filter_entry and sideways[i]:
                reason = "SIDEWAYS_FILTER"
            else:
                pending = "ENTER"
                reason = "ACCEPTED"
            if reason != "ACCEPTED":
                rejected[reason] += 1
            m = geometries[i]
            entry_audit.append({
                "signal_time":times[i],"decision":reason,
                "sideways":sideways[i],
                "height_pct":round(m["height_pct"],6) if m else None,
                "efficiency":round(m["efficiency"],6) if m else None,
                "displacement_fraction":round(m["displacement_fraction"],6) if m else None,
            })
    if pos is not None:
        trades.append(exp79.finish(pos,n-1,closes[-1],"DATA_END",times))
    return trades,candidates,dict(rejected),entry_audit,exit_audit,sideways

def summarize(trades,candidates,rejected):
    return {
        "candidates":candidates,"trades":len(trades),
        "winners":sum(t["net_pnl_pct"]>0 for t in trades),
        "losers":sum(t["net_pnl_pct"]<=0 for t in trades),
        "gross_pct_sum":round(sum(t["gross_pnl_pct"] for t in trades),6),
        "commission_pct_sum":round(len(trades)*2*exp79.FEE,6),
        "net_pct_sum":round(sum(t["net_pnl_pct"] for t in trades),6),
        "exit_reasons":dict(Counter(t["exit_reason"] for t in trades)),
        "rejected_signals":rejected,
    }

def write_csv(path,rows):
    if not rows: return
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def run_symbol(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    closes=[float(r["close"]) for r in rows]
    st=base.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=base.rsi_wilder(closes)
    market=[base.get_market_state(closes,i) for i in range(len(rows))]
    expected,_,_,_=base.simulate(rows,st,rsi,market,None,False)
    result={}
    for variant in VARIANTS:
        trades,candidates,rejected,entries,exits,sideways=simulate(rows,st,rsi,market,variant)
        if variant=="BASELINE":
            # Strong baseline invariance check: trade details must match exactly.
            if trades != expected:
                for idx,(a,b) in enumerate(zip(trades,expected)):
                    if a!=b:
                        raise AssertionError(f"{symbol} baseline drift at trade {idx}: {a} != {b}")
                raise AssertionError(f"{symbol} baseline trade count mismatch: {len(trades)} != {len(expected)}")
        write_csv(OUT/f"{symbol.lower()}_{variant.lower()}_trades.csv",trades)
        if variant=="BASELINE":
            write_csv(OUT/f"{symbol.lower()}_v16_candidates.csv",entries)
        if variant=="COMBINED":
            write_csv(OUT/f"{symbol.lower()}_sideways_exit_events.csv",exits)
        result[variant]=summarize(trades,candidates,rejected)
        result[variant]["sideways_exit_events"]=len(exits)
    baseline_net=result["BASELINE"]["net_pct_sum"]
    for variant in VARIANTS:
        result[variant]["net_delta_vs_baseline_pp"]=round(result[variant]["net_pct_sum"]-baseline_net,6)
    return {
        "candles":len(rows),
        "sideways_candles_within_session":sum(sideways),
        "valid_geometry_candles":sum(metrics(rows,i) is not None for i in range(len(rows))),
        "variants":result,
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
        "experiment":"EXP93",
        "research_only":True,
        "rules":{
            "window_candles":WINDOW,
            "sideways_efficiency_max":EFF_MAX,
            "sideways_displacement_fraction_max":DISPLACEMENT_FRACTION_MAX,
            "entry_filter":"Reject V16 entry if 12 completed same-session bars show sideways.",
            "sideways_exit":"Two consecutive sideways readings; 3 bars without new favorable close; best gross close profit above 0.20%; signal close, fill next open.",
            "execution":"EXP83 baseline, same-session next-open signals, 1.5% intrabar stop, RSI rescue, ST exit, session-end close, 0.10% commission per side.",
        },
        "limitations":[
            "Fixed exploratory thresholds, NOT optimized or validated.",
            "Only NVDA/AAPL V16 SHORT, not LONG or multi-symbol allocation.",
            "Small historical sample; any observed improvement may be chance.",
            "No slippage; percentage sums are not compounded account returns.",
            "Cannot prove opportunity switching without simultaneous symbol data and portfolio simulation.",
            "Entry filter can change subsequent entry timing; variants are full causal reruns.",
        ],
        "symbols":{},
    }
    for symbol,path in base.DATA.items():
        report["symbols"][symbol]=run_symbol(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP93 — SIDEWAYS ENTRY + EXIT COUNTERFACTUAL — RESEARCH ONLY")
    for symbol,data in report["symbols"].items():
        print("\n",symbol,"candles:",data["candles"],
              "sideways candles:",data["sideways_candles_within_session"],
              "valid geometry:",data["valid_geometry_candles"])
        for variant,summary in data["variants"].items():
            print(variant,summary)
    print("\nDetailed CSV and summary:",OUT)
    print("Production trading code unchanged.")

if __name__=="__main__":
    main()
