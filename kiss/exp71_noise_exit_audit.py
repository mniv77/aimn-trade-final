#!/usr/bin/env python3
"""EXP71: causal WATCH/HOLD/EXIT? chart-event audit (no trades, no AI).

Matches the Visual Lab prototype rule. Each signal uses completed candles
through its own index. The next 3/6 candles are evaluated only afterward.
"""
import argparse
import json
from pathlib import Path

from kiss.kiss_exp53_supertrend import calculate_supertrend


def events(rows):
    df = calculate_supertrend(rows, atr_period=10, multiplier=3.0)
    result = []
    watch = None
    for i in range(15, len(df)):
        c, p = df.iloc[i], df.iloc[i - 1]
        state = c["st_trend"]
        if state not in ("LONG", "SHORT") or p["st_trend"] != state:
            watch = None
            continue
        band, old = float(c["supertrend"]), float(p["supertrend"])
        tol = float(c["close"]) * 0.00015
        flat = abs(band - old) <= tol
        opposing = float(c["close"]) > float(p["close"]) if state == "SHORT" else float(c["close"]) < float(p["close"])
        favorable = not opposing and float(c["close"]) != float(p["close"])
        if watch and watch["side"] != state:
            watch = None
        def record(kind):
            result.append({"index":i, "timestamp":str(c["timestamp"]), "side":state,
                           "kind":kind, "close":float(c["close"])})
        if watch is None and flat and opposing:
            watch = {"side":state, "index":i, "price":float(c["close"])}
            record("WATCH")
        elif watch and i > watch["index"]:
            elapsed = i - watch["index"]
            reversal = float(c["close"]) > watch["price"] if state == "SHORT" else float(c["close"]) < watch["price"]
            recovery_failed = float(c["close"]) < watch["price"] if state == "SHORT" else float(c["close"]) > watch["price"]
            if elapsed >= 2 and reversal and opposing:
                record("EXIT_CANDIDATE")
                watch = None
            elif favorable and recovery_failed:
                record("HOLD")
                watch = None
            elif elapsed >= 5:
                watch = None
    return result


def audit(rows, signals):
    # Post-event evaluation is explicitly separate from signal generation.
    # Signed favorable move for original trend, from event close to later close.
    out = []
    for e in signals:
        record = dict(e)
        for n in (3, 6):
            j = e["index"] + n
            if j >= len(rows) or str(rows[j]["timestamp"])[:10] != e["timestamp"][:10]:
                record[f"original_trend_move_{n}_pct"] = None
                continue
            later = float(rows[j]["close"])
            signed = (later / e["close"] - 1) * 100
            if e["side"] == "SHORT":
                signed = -signed
            record[f"original_trend_move_{n}_pct"] = round(signed, 5)
        out.append(record)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candles", default="kiss/visual_research/aimn_nvda_candles.json")
    p.add_argument("--output", default="kiss/results/exp71_noise_exit_event_audit.json")
    a = p.parse_args()
    rows = json.loads(Path(a.candles).read_text(encoding="utf-8"))
    signals = events(rows)
    evaluated = audit(rows, signals)
    counts = {k:sum(x["kind"] == k for x in signals)
              for k in ("WATCH", "HOLD", "EXIT_CANDIDATE")}
    candidate = [x for x in evaluated if x["kind"] == "EXIT_CANDIDATE"]
    print("EXP71 chart event counts:", counts)
    for horizon in (3, 6):
        key = f"original_trend_move_{horizon}_pct"
        valid = [x[key] for x in candidate if x[key] is not None]
        resumed = sum(x > 0 for x in valid)
        print(f"EXIT? {horizon}-candle follow-up: {resumed}/{len(valid)} original trends resumed",
              "(positive favorable movement for original trend)")
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"counts":counts,"events":evaluated},indent=2),encoding="utf-8")
    print("Saved",out)


if __name__ == "__main__":
    main()
