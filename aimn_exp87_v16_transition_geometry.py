#!/usr/bin/env python3
"""EXP87 — V16 SHORT transition geometry, descriptive research only.

At each completed V16 signal, measure peak age, drawdown from prior peak,
rebound/choppiness and recent-range position. Link accepted signals to
unchanged EXP83 baseline trade outcomes. No fitted thresholds or new
entry/exits. All features use candles at or before signal close.
"""
import csv
import json
from collections import Counter
from pathlib import Path
import aimn_exp83_v16_structural_exit as exp83

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp87_v16_transition_geometry"
WINDOW=12

def mean(values):
    vals=[float(v) for v in values if v is not None]
    return round(sum(vals)/len(vals),5) if vals else None

def pct(a,b):
    return round((a/b-1)*100,5) if b else None

def geometry(rows,i):
    # Window includes signal candle. Peak is from earlier completed candles
    # to distinguish pre-signal high from signal candle itself.
    start=max(0,i-WINDOW)
    prior=rows[start:i]
    segment=rows[start:i+1]
    close=[float(r["close"]) for r in segment]
    highs=[float(r["high"]) for r in prior]
    lows=[float(r["low"]) for r in prior]
    signal_close=float(rows[i]["close"])
    if not prior:
        raise ValueError("No prior candles")
    peak_offset=max(range(len(prior)),key=lambda k:float(prior[k]["high"]))
    peak_index=start+peak_offset
    peak_price=highs[peak_offset]
    prior_low=min(lows)
    span=peak_price-prior_low
    up_moves=0
    down_moves=0
    sum_up=0.0
    sum_down=0.0
    for a,b in zip(close[:-1],close[1:]):
        delta=b-a
        if delta>0:
            up_moves+=1
            sum_up+=delta
        elif delta<0:
            down_moves+=1
            sum_down-=delta
    reversals=0
    prev_sign=0
    for a,b in zip(close[:-1],close[1:]):
        sign=1 if b>a else (-1 if b<a else 0)
        if sign and prev_sign and sign!=prev_sign:
            reversals+=1
        if sign:prev_sign=sign
    # Peak-to-signal close is a normalized geometric descriptor.
    return {
      "peak_age_bars":i-peak_index,
      "peak_to_signal_drawdown_pct":pct(peak_price,signal_close),
      "prior_12bar_range_pct":pct(peak_price,prior_low),
      "signal_position_in_prior_range":round((signal_close-prior_low)/span,5) if span>0 else None,
      "up_closes_in_window":up_moves,
      "down_closes_in_window":down_moves,
      "direction_changes_in_window":reversals,
      "total_up_close_motion_pct":round(100*sum_up/signal_close,5),
      "total_down_close_motion_pct":round(100*sum_down/signal_close,5),
      "up_to_down_motion_ratio":round(sum_up/sum_down,5) if sum_down else None,
      "close_change_from_peak_bar_pct":pct(signal_close,float(rows[peak_index]["close"])),
      "peak_bar_time":str(rows[peak_index]["timestamp"]),
    }

FEATURES=[
  "peak_age_bars","peak_to_signal_drawdown_pct",
  "prior_12bar_range_pct","signal_position_in_prior_range",
  "up_closes_in_window","down_closes_in_window",
  "direction_changes_in_window","total_up_close_motion_pct",
  "total_down_close_motion_pct","up_to_down_motion_ratio",
  "close_change_from_peak_bar_pct",
]

def summarize(items):
    return {
      "count":len(items),
      "means":{k:mean([r[k] for r in items]) for k in FEATURES},
    }

def write_csv(path,records):
    if not records:return
    fields=list(dict.fromkeys(k for row in records for k in row))
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

def run(symbol,path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    rows.sort(key=lambda r:str(r["timestamp"]))
    times=[str(r["timestamp"]) for r in rows]
    if len(set(times))!=len(times):
        raise ValueError("Duplicate timestamps")
    closes=[float(r["close"]) for r in rows]
    highs=[float(r["high"]) for r in rows]
    lows=[float(r["low"]) for r in rows]
    st=exp83.calculate_supertrend(rows,atr_period=10,multiplier=3.0)["st_trend"].tolist()
    rsi=exp83.rsi_wilder(closes)
    market=[exp83.get_market_state(closes,i) for i in range(len(rows))]
    trades,candidates,rejected,blocked=exp83.simulate(rows,st,rsi,market,None,False)
    if blocked:
        raise ValueError("Unexpected structural blocks in baseline")
    by_entry={t["entry_time"]:t for t in trades}
    records=[]
    for i in range(35,len(rows)):
        if exp83.is_major_long_to_short_reversal(highs,lows,closes,market,i) is None:
            continue
        next_time=times[i+1] if i+1<len(rows) else None
        same_day=bool(next_time and next_time[:10]==times[i][:10])
        trade=by_entry.get(next_time) if same_day else None
        record={
          "symbol":symbol,
          "signal_time":times[i],
          "ST_at_signal":st[i],
          "RSI_at_signal":round(rsi[i],5) if rsi[i] is not None else None,
          "accepted":trade is not None,
          "entry_time":trade["entry_time"] if trade else None,
          "net_trade_pct":float(trade["net_pnl_pct"]) if trade else None,
          "winner":trade["net_pnl_pct"]>0 if trade else None,
          "exit_reason":trade["exit_reason"] if trade else None,
          **geometry(rows,i)
        }
        records.append(record)
    accepted=[r for r in records if r["accepted"]]
    if len(accepted)!=len(trades) or len(records)!=candidates:
        raise ValueError(f"{symbol}: signal/trade counts disagree with baseline")
    winners=[r for r in accepted if r["winner"]]
    losers=[r for r in accepted if not r["winner"]]
    rejected_st=[r for r in records if r["ST_at_signal"]!="LONG"]
    write_csv(OUT/(symbol.lower()+"_all_signals.csv"),records)
    write_csv(OUT/(symbol.lower()+"_accepted_trades.csv"),accepted)
    return {
      "V16_candidates":candidates,
      "accepted_trades":len(trades),
      "winners":len(winners),
      "losers":len(losers),
      "baseline_net_pct_sum":round(sum(t["net_pnl_pct"] for t in trades),5),
      "rejected":rejected,
      "accepted_winners":summarize(winners),
      "accepted_losers":summarize(losers),
      "ST_NOT_LONG_signals":summarize(rejected_st),
    }

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={
      "experiment":"EXP87",
      "research_only":True,
      "method":"Unchanged EXP83 V16/ST baseline, geometry from completed signal candle and previous 12 bars.",
      "limitations":"Descriptive, in-sample, small data. No discovered geometry pattern is a validated entry rule. Prior 12-bar window can cross session boundary; features do not infer a unique chart-pattern label.",
      "symbols":{},
    }
    for symbol,path in exp83.DATA.items():
        report["symbols"][symbol]=run(symbol,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP87 — V16 TRANSITION GEOMETRY — RESEARCH ONLY")
    print(json.dumps(report,indent=2))
    print("Detailed CSV:",OUT)

if __name__=="__main__":
    main()
