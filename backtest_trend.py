# backtest_trend.py
"""
backtest_trend.py  (v2 — three strategies head-to-head)

Replays 5m candles bar-by-bar (no look-ahead) and compares:
  A  MICRO        : enter on any minor turn/flip, exit on opposite minor turn/flip
  B  ALIGNED MICRO: like A, but entries only in the 1hr MACRO trend direction
  C  TREND-RIDE   : macro-aligned entry, exit only on 30m major structure flip

Fees: FEE_PCT_PER_SIDE per side (default 0.20%).

Usage:
    python3 backtest_trend.py BTC/USD
    python3 backtest_trend.py all
"""

import sys
from trend_engine import _fetch, analyze_trend

FEE_PCT_PER_SIDE = 0.20
MINOR_WINDOW = 80      # 5m
MAJOR_WINDOW = 100     # 30m
MACRO_WINDOW = 200     # 1hr
WARMUP = 30


def _minor_dir(minor):
    if minor["flip"] == "TO_UP" or minor["turn"] == "UP":
        return "UP"
    if minor["flip"] == "TO_DOWN" or minor["turn"] == "DOWN":
        return "DOWN"
    return None


class Sim:
    def __init__(self, name):
        self.name = name
        self.pos = None
        self.trades = []
        self.last_exit = None

    def close(self, px, t, reason):
        raw = (px - self.pos["entry"]) / self.pos["entry"] * 100.0
        if self.pos["dir"] == "SHORT":
            raw = -raw
        self.trades.append({"dir": self.pos["dir"], "entry": self.pos["entry"],
                            "exit": px, "t_in": self.pos["t"], "t_out": t,
                            "pnl": raw - 2 * FEE_PCT_PER_SIDE, "reason": reason})
        self.pos = None
        self.last_exit = t

    def open(self, d, px, t):
        self.pos = {"dir": d, "entry": px, "t": t}

    def report(self, days):
        n = len(self.trades)
        wins = [t for t in self.trades if t["pnl"] > 0]
        total = sum(t["pnl"] for t in self.trades)
        wr = len(wins) / n * 100 if n else 0
        per_day = total / days if days else 0
        print(f"  {self.name:14s} trades={n:4d}  win={wr:5.1f}%  "
              f"total={total:+8.2f}%  per-day={per_day:+.2f}%")
        return {"name": self.name, "n": n, "win_rate": wr, "total": total}


def backtest(symbol):
    c5 = _fetch(symbol, "5m", 3000)
    c30 = _fetch(symbol, "30m", 1500)
    c1h = _fetch(symbol, "1hr", 1000)
    if len(c5) < WARMUP + 10 or len(c30) < 30 or len(c1h) < 30:
        print(f"{symbol}: not enough data (5m={len(c5)}, 30m={len(c30)}, 1hr={len(c1h)})")
        return None
    if c5[0]["t"] is None or c30[0]["t"] is None or c1h[0]["t"] is None:
        print(f"{symbol}: candles missing timestamps — cannot align")
        return None

    days = len(c5) * 5 / 60 / 24
    print(f"\n===== {symbol} =====  5m={len(c5)} (~{days:.1f} days)  "
          f"30m={len(c30)}  1hr={len(c1h)}")

    A, B, C = Sim("A MICRO"), Sim("B ALIGNED-MICRO"), Sim("C TREND-RIDE")
    j30 = j1h = 0

    for i in range(WARMUP, len(c5)):
        now = c5[i]["t"]; px = c5[i]["c"]
        while j30 < len(c30) and c30[j30]["t"] <= now: j30 += 1
        while j1h < len(c1h) and c1h[j1h]["t"] <= now: j1h += 1
        if j30 < 20 or j1h < 20:
            continue
        minor = analyze_trend(c5[max(0, i + 1 - MINOR_WINDOW):i + 1])
        major = analyze_trend(c30[max(0, j30 - MAJOR_WINDOW):j30])
        macro = analyze_trend(c1h[max(0, j1h - MACRO_WINDOW):j1h])
        md = _minor_dir(minor)

        # ---- A: pure micro (enter any minor turn, exit opposite minor turn)
        if A.pos and md and md != ("UP" if A.pos["dir"] == "LONG" else "DOWN"):
            A.close(px, now, "minor-flip")
        if A.pos is None and md == "UP":
            A.open("LONG", px, now)
        elif A.pos is None and md == "DOWN":
            A.open("SHORT", px, now)

        # ---- B: aligned micro (entry needs macro agreement, exit fast)
        if B.pos and md and md != ("UP" if B.pos["dir"] == "LONG" else "DOWN"):
            B.close(px, now, "minor-flip")
        if B.pos is None and md == "UP" and macro["trend"] == "UP":
            B.open("LONG", px, now)
        elif B.pos is None and md == "DOWN" and macro["trend"] == "DOWN":
            B.open("SHORT", px, now)

        # ---- C: trend ride (macro-aligned entry, exit on 30m major flip)
        if C.pos:
            if C.pos["dir"] == "LONG" and (major["flip"] == "TO_DOWN" or
                    (major["last_swing_low"] and px < major["last_swing_low"])):
                C.close(px, now, "major-flip")
            elif C.pos["dir"] == "SHORT" and (major["flip"] == "TO_UP" or
                    (major["last_swing_high"] and px > major["last_swing_high"])):
                C.close(px, now, "major-flip")
        if C.last_exit is None:
            cooled = True
        else:
            _dt = now - C.last_exit
            cooled = (_dt.total_seconds() if hasattr(_dt, "total_seconds") else _dt) >= 3600

        if C.pos is None and cooled and md == "UP" and macro["trend"] == "UP":
            C.open("LONG", px, now)
        elif C.pos is None and cooled and md == "DOWN" and macro["trend"] == "DOWN":
            C.open("SHORT", px, now)

    px = c5[-1]["c"]; now = c5[-1]["t"]
    for s in (A, B, C):
        if s.pos:
            s.close(px, now, "END")

    stats = [s.report(days) for s in (A, B, C)]
    return {"symbol": symbol, "stats": stats}


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "BTC/USD"
    symbols = ["BTC/USD", "ETH/USD", "SOL/USD", "LINK/USD"] if arg == "all" else [arg]
    all_r = [r for s in symbols if (r := backtest(s))]
    if len(all_r) > 1:
        print("\n===== TOTALS ACROSS SYMBOLS =====")
        for k in range(3):
            name = all_r[0]["stats"][k]["name"]
            tot = sum(r["stats"][k]["total"] for r in all_r)
            n = sum(r["stats"][k]["n"] for r in all_r)
            print(f"  {name:14s} trades={n:4d}  total={tot:+8.2f}%")