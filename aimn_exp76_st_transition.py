#!/usr/bin/env python3
"""EXP76: research-only NVDA SHORT Supertrend transition backtest.
No production imports, orders, or changes to existing datasets.
"""
import csv
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "kiss/visual_research/aimn_nvda_candles.json"
OUT = ROOT / "kiss/results/exp76_st_transition"

def rma(xs, period):
    result = [None] * len(xs)
    if len(xs) < period:
        return result
    avg = sum(xs[:period]) / period
    result[period - 1] = avg
    for i in range(period, len(xs)):
        avg = (avg * (period - 1) + xs[i]) / period
        result[i] = avg
    return result

def supertrend(rows, period=10, factor=3.0):
    n = len(rows)
    tr = []
    for i, r in enumerate(rows):
        high, low = float(r["high"]), float(r["low"])
        prev = float(rows[i - 1]["close"]) if i else float(r["close"])
        tr.append(max(high-low, abs(high-prev), abs(low-prev)))
    atr = rma(tr, period)
    upper = [None]*n
    lower = [None]*n
    trend = [None]*n
    for i in range(period-1, n):
        r = rows[i]
        mid = (float(r["high"])+float(r["low"]))/2
        bu, bl = mid+factor*atr[i], mid-factor*atr[i]
        if i == period-1:
            upper[i], lower[i] = bu, bl
            trend[i] = "LONG" if float(r["close"]) >= mid else "SHORT"
            continue
        prevclose = float(rows[i-1]["close"])
        upper[i] = bu if bu < upper[i-1] or prevclose > upper[i-1] else upper[i-1]
        lower[i] = bl if bl > lower[i-1] or prevclose < lower[i-1] else lower[i-1]
        close = float(r["close"])
        if trend[i-1] == "LONG":
            trend[i] = "SHORT" if close < lower[i-1] else "LONG"
        else:
            trend[i] = "LONG" if close > upper[i-1] else "SHORT"
    return trend

def rsi(closes, period=14):
    out = [None]*len(closes)
    if len(closes) <= period:
        return out
    gains = [max(0, closes[i]-closes[i-1]) for i in range(1,len(closes))]
    losses = [max(0, closes[i-1]-closes[i]) for i in range(1,len(closes))]
    ag, al = sum(gains[:period])/period, sum(losses[:period])/period
    for i in range(period, len(closes)):
        if i > period:
            ag = (ag*(period-1)+gains[i-1])/period
            al = (al*(period-1)+losses[i-1])/period
        out[i] = 100 if al == 0 else 100 - 100/(1+ag/al)
    return out

def run(rows):
    trend = supertrend(rows)
    rsis = rsi([float(r["close"]) for r in rows])
    trades, position = [], None
    commission = 0.10
    stop_pct = 1.5
    pending = None
    for i in range(1,len(rows)):
        r = rows[i]
        day = str(r["timestamp"])[:10]
        if position is not None and day != position["entry_day"]:
            # No overnight positions: prior session close is a research assumption.
            prev = rows[i-1]
            price = float(prev["close"])
            gross = (position["entry_price"]/price-1)*100
            trades.append(dict(entry_time=position["entry_time"],exit_time=str(prev["timestamp"]),
                               entry_price=position["entry_price"],exit_price=price,
                               exit_reason="SESSION_END",gross_pnl_pct=round(gross,6),
                               net_pnl_pct=round(gross-2*commission,6)))
            position = None
            pending = None
        if pending:
            price = float(r["open"])
            if pending == "ENTER" and position is None:
                position = dict(entry_time=str(r["timestamp"]),entry_day=day,entry_price=price)
            elif pending == "EXIT" and position is not None:
                gross = (position["entry_price"]/price-1)*100
                trades.append(dict(entry_time=position["entry_time"],exit_time=str(r["timestamp"]),
                                   entry_price=position["entry_price"],exit_price=price,
                                   exit_reason="ST_REVERSE",gross_pnl_pct=round(gross,6),
                                   net_pnl_pct=round(gross-2*commission,6)))
                position = None
            pending = None
        if position is not None:
            # Intrabar stop: conservative stop-price fill, subject to opening gaps.
            stop = position["entry_price"]*(1+stop_pct/100)
            if float(r["high"]) >= stop:
                price = max(stop,float(r["open"]))
                gross = (position["entry_price"]/price-1)*100
                trades.append(dict(entry_time=position["entry_time"],exit_time=str(r["timestamp"]),
                                   entry_price=position["entry_price"],exit_price=price,
                                   exit_reason="STOP_LOSS",gross_pnl_pct=round(gross,6),
                                   net_pnl_pct=round(gross-2*commission,6)))
                position = None
            elif rsis[i] is not None and rsis[i] >= 80:
                # RSI signal known only at candle close; fill next open.
                pending = "EXIT"
        if i+1 >= len(rows) or str(rows[i+1]["timestamp"])[:10] != day:
            continue
        if trend[i] and trend[i-1] and trend[i] != trend[i-1]:
            if trend[i] == "SHORT" and position is None and pending is None:
                pending = "ENTER"
            elif trend[i] == "LONG" and position is not None:
                pending = "EXIT"
    if position:
        last=rows[-1]
        price=float(last["close"])
        gross=(position["entry_price"]/price-1)*100
        trades.append(dict(entry_time=position["entry_time"],exit_time=str(last["timestamp"]),
                           entry_price=position["entry_price"],exit_price=price,
                           exit_reason="DATA_END",gross_pnl_pct=round(gross,6),
                           net_pnl_pct=round(gross-2*commission,6)))
    return trades

def main():
    rows=json.loads(SOURCE.read_text(encoding="utf-8"))
    assert len(rows)>100 and all(float(r["open"])>0 for r in rows)
    trades=run(rows)
    OUT.mkdir(parents=True,exist_ok=True)
    csv_path=OUT/"nvda_short_trades.csv"
    fields=["entry_time","exit_time","entry_price","exit_price","exit_reason","gross_pnl_pct","net_pnl_pct"]
    with csv_path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(trades)
    wins=sum(t["net_pnl_pct"]>0 for t in trades)
    summary=dict(experiment="EXP76",symbol="NVDA",direction="SHORT",timeframe="5m",
                 candles=len(rows),trades=len(trades),winners=wins,losers=len(trades)-wins,
                 gross_pct_sum=round(sum(t["gross_pnl_pct"] for t in trades),3),
                 net_pct_sum=round(sum(t["net_pnl_pct"] for t in trades),3),
                 assumptions="ST(10,3), next-open flips, 1.5% stop, RSI80 rescue, 0.10% per side, session close",
                 exit_reasons={k:sum(t["exit_reason"]==k for t in trades) for k in
                               ["ST_REVERSE","STOP_LOSS","SESSION_END","DATA_END"]})
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print("EXP76 — NVDA SHORT — RESEARCH ONLY")
    print(json.dumps(summary,indent=2))
    print("CSV:",csv_path)
if __name__=="__main__":
    main()
