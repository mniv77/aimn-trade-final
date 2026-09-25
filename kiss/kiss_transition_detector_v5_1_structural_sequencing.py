"""KISS Transition Detector V5.1 — causal market-structure sequencing.

RESEARCH ONLY. No orders. No DB writes. No engine changes.

V5.1 is a correction/rebuild of V5's structural timing logic.

The target is the actual price-structure change, not prediction of the
30m MA-state transition.

LONG -> SHORT structural sequence:
    established HH/HL structure
    T0 = first meaningful weakness after the latest HH
    T1 = confirmed lower high after T0 (failed continuation)
    T2 = first close below the prior higher-low after T1
    T3 = confirmed lower low after T2
    T4 = confirmed lower high after T3 (new bearish structure)
    T5 = official 30m LONG -> SHORT state transition

SHORT -> LONG is the exact mirror.

CAUSAL TIMING:
    A 5m candle timestamp is its START. Its information becomes available
    only at timestamp + 5 minutes.
    A swing is confirmed only after SWING_LOOKBACK completed bars to its right.
    Every stage is therefore timestamped only when the required information
    is actually available.

IMPORTANT V5.1 CHANGE:
    Stages are strictly sequential. A later stage can never be satisfied by
    a swing or price break that occurred before the previous stage.
    T1/T2/etc are not reconstructed from a future-complete pattern.

The research also probes negative/non-transition observations so we can see
whether the structural sequence fires during ordinary continuation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
SWING_LOOKBACK = 3
SEARCH_BACK = 36
LOOKBACK_MINUTES = 180
NEGATIVE_HORIZON_MINUTES = 180
MIN_5M_HISTORY = 24
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


def num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def ts(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    return datetime.fromisoformat(
        str(v).replace("Z", "+00:00").replace("+00:00", "")
    ).replace(tzinfo=None)


def load(symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    conn, cur = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        cur.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC LIMIT %s""",
            (symbol, timeframe, int(limit)),
        )
        rows = cur.fetchall() or []
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r) if isinstance(r, dict) else {
                "timestamp": r[0], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4], "volume": r[5],
            }
            d["timestamp"] = ts(d["timestamp"])
            for k in ("open", "high", "low", "close", "volume"):
                d[k] = num(d[k])
            out.append(d)
        return out
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def market_state(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"
    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def opposite(s: str) -> str:
    return "SHORT" if s == "LONG" else "LONG"


def direct_transitions(rows30: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [r["close"] for r in rows30]
    states = [market_state(closes, i) for i in range(len(rows30))]
    out: List[Dict[str, Any]] = []
    for i in range(TREND_WINDOW + 1, len(rows30)):
        a, b = states[i - 1], states[i]
        if a in ("LONG", "SHORT") and b == opposite(a):
            out.append({
                "index": i,
                "known_time": rows30[i]["timestamp"] + timedelta(minutes=30),
                "from": a,
                "to": b,
                "price": rows30[i]["close"],
            })
    return out


def _local_high(h: Sequence[float], i: int) -> bool:
    if i < SWING_LOOKBACK or i + SWING_LOOKBACK >= len(h):
        return False
    return (
        h[i] >= max(h[i - SWING_LOOKBACK:i])
        and h[i] >= max(h[i + 1:i + SWING_LOOKBACK + 1])
    )


def _local_low(l: Sequence[float], i: int) -> bool:
    if i < SWING_LOOKBACK or i + SWING_LOOKBACK >= len(l):
        return False
    return (
        l[i] <= min(l[i - SWING_LOOKBACK:i])
        and l[i] <= min(l[i + 1:i + SWING_LOOKBACK + 1])
    )


def confirmed_swings(bars: Sequence[Dict[str, Any]]) -> Tuple[List[int], List[int]]:
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    highs = [i for i in range(len(bars)) if _local_high(h, i)]
    lows = [i for i in range(len(bars)) if _local_low(l, i)]
    return highs, lows


def observation_time(bars: Sequence[Dict[str, Any]], idx: int) -> datetime:
    return bars[idx]["timestamp"] + timedelta(minutes=5)


def causal_structure(bars: Sequence[Dict[str, Any]], prior: str) -> Dict[str, Any]:
    """Return the highest strictly sequential structural stage visible now.

    All swings are confirmed using bars that were already available at the
    current observation. No stage is allowed to use a swing from before the
    preceding stage's structural event.
    """
    if len(bars) < MIN_5M_HISTORY:
        return {"stage": 0}

    c = [b["close"] for b in bars]
    h = [b["high"] for b in bars]
    l = [b["low"] for b in bars]
    highs, lows = confirmed_swings(bars)
    lo = max(0, len(bars) - SEARCH_BACK)
    hi = len(bars) - 1

    if prior == "LONG":
        # Establish the old bullish structure: two confirmed higher highs
        # with a confirmed higher-low between them.
        old_highs = [x for x in highs if lo <= x < hi]
        if len(old_highs) < 2:
            return {"stage": 0}
        hh1, hh2 = old_highs[-2], old_highs[-1]
        if h[hh2] <= h[hh1]:
            return {"stage": 0}
        old_lows = [x for x in lows if hh1 < x < hh2]
        if not old_lows:
            old_lows = [x for x in lows if x < hh2]
        if not old_lows:
            return {"stage": 0}
        hl = old_lows[-1]

        # T0: first observed weakness after the latest HH. This is an
        # observation, not a hindsight swing.
        t0 = next((j for j in range(hh2 + 1, len(c)) if c[j] < h[hh2]), None)
        if t0 is None:
            return {"stage": 0}

        # T1: confirmed lower high strictly after T0 and below HH2.
        lh_candidates = [
            x for x in highs
            if x > t0 and x < hi and h[x] < h[hh2]
        ]
        if not lh_candidates:
            return {"stage": 1, "t0": t0, "hh": hh2, "hl": hl}
        lh = lh_candidates[0]

        # T2: first close below the old higher-low, strictly after T1.
        break_idx = next((j for j in range(lh + 1, len(c)) if c[j] < l[hl]), None)
        if break_idx is None:
            return {"stage": 2, "t0": t0, "hh": hh2, "hl": hl, "lh": lh}

        # T3: confirmed lower low strictly after the structural break.
        ll_candidates = [
            x for x in lows
            if x > break_idx and l[x] < l[hl]
        ]
        if not ll_candidates:
            return {
                "stage": 3, "t0": t0, "hh": hh2, "hl": hl,
                "lh": lh, "break": break_idx,
            }
        ll = ll_candidates[0]

        # T4: confirmed lower high strictly after the new lower low and below
        # the failed-continuation high. This is new bearish structure.
        nh_candidates = [
            x for x in highs
            if x > ll and h[x] < h[lh]
        ]
        if not nh_candidates:
            return {
                "stage": 4, "t0": t0, "hh": hh2, "hl": hl,
                "lh": lh, "break": break_idx, "ll": ll,
            }
        nh = nh_candidates[0]
        return {
            "stage": 5, "t0": t0, "hh": hh2, "hl": hl,
            "lh": lh, "break": break_idx, "ll": ll, "new_high": nh,
        }

    if prior == "SHORT":
        old_lows = [x for x in lows if lo <= x < hi]
        if len(old_lows) < 2:
            return {"stage": 0}
        ll1, ll2 = old_lows[-2], old_lows[-1]
        if l[ll2] >= l[ll1]:
            return {"stage": 0}
        old_highs = [x for x in highs if ll1 < x < ll2]
        if not old_highs:
            old_highs = [x for x in highs if x < ll2]
        if not old_highs:
            return {"stage": 0}
        lh = old_highs[-1]

        t0 = next((j for j in range(ll2 + 1, len(c)) if c[j] > l[ll2]), None)
        if t0 is None:
            return {"stage": 0}

        hl_candidates = [
            x for x in lows
            if x > t0 and x < hi and l[x] > l[ll2]
        ]
        if not hl_candidates:
            return {"stage": 1, "t0": t0, "ll": ll2, "lh": lh}
        hl = hl_candidates[0]

        break_idx = next((j for j in range(hl + 1, len(c)) if c[j] > h[lh]), None)
        if break_idx is None:
            return {"stage": 2, "t0": t0, "ll": ll2, "lh": lh, "hl": hl}

        hh_candidates = [
            x for x in highs
            if x > break_idx and h[x] > h[lh]
        ]
        if not hh_candidates:
            return {
                "stage": 3, "t0": t0, "ll": ll2, "lh": lh,
                "hl": hl, "break": break_idx,
            }
        hh = hh_candidates[0]

        nl_candidates = [
            x for x in lows
            if x > hh and l[x] > l[hl]
        ]
        if not nl_candidates:
            return {
                "stage": 4, "t0": t0, "ll": ll2, "lh": lh,
                "hl": hl, "break": break_idx, "hh": hh,
            }
        nl = nl_candidates[0]
        return {
            "stage": 5, "t0": t0, "ll": ll2, "lh": lh,
            "hl": hl, "break": break_idx, "hh": hh, "new_low": nl,
        }

    return {"stage": 0}


def earliest_stages(
    rows5: Sequence[Dict[str, Any]],
    event_time: datetime,
    prior: str,
) -> Dict[str, Optional[datetime]]:
    """Find first causal observation at which each cumulative stage exists."""
    start = event_time - timedelta(minutes=LOOKBACK_MINUTES)
    stages: Dict[str, Optional[datetime]] = {f"T{i}": None for i in range(0, 6)}
    last_stage = 0

    for i in range(len(rows5)):
        obs = observation_time(rows5, i)
        if obs < start:
            continue
        if obs > event_time:
            break

        # Only bars available by this observation may be used.
        hist = rows5[: i + 1]
        result = causal_structure(hist[-(SEARCH_BACK + 12):], prior)
        stage = int(result.get("stage", 0))

        # Stages must be reached in order. Once a stage has a timestamp it is
        # never overwritten by a later reconstruction.
        while last_stage < stage and last_stage < 5:
            last_stage += 1
            stages[f"T{last_stage}"] = obs

    return stages


def evaluate_symbol(
    symbol: str,
    rows30: Sequence[Dict[str, Any]],
    rows5: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    events = direct_transitions(rows30)
    cases: List[Dict[str, Any]] = []
    for e in events:
        stages = earliest_stages(rows5, e["known_time"], e["from"])
        cases.append({
            "kind": "REAL",
            "symbol": symbol,
            "from": e["from"],
            "to": e["to"],
            "event_time": e["known_time"],
            "stages": stages,
        })
    return cases


def negative_cases(
    symbol: str,
    rows30: Sequence[Dict[str, Any]],
    rows5: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build non-transition probes from directional 30m periods.

    A probe is anchored at a completed 30m candle whose state is LONG/SHORT
    and which is not itself a direct opposite transition. We inspect the next
    NEGATIVE_HORIZON_MINUTES. If the structural detector reaches T4/T5 during
    that horizon, it is a false structural alarm unless a direct transition
    occurs in the same horizon.
    """
    closes = [r["close"] for r in rows30]
    states = [market_state(closes, i) for i in range(len(rows30))]
    direct_idx = {e["index"] for e in direct_transitions(rows30)}
    out: List[Dict[str, Any]] = []

    for i in range(TREND_WINDOW + 1, len(rows30) - 6):
        prior = states[i]
        if prior not in ("LONG", "SHORT"):
            continue
        if i + 1 in direct_idx:
            continue

        anchor = rows30[i]["timestamp"] + timedelta(minutes=30)
        end = anchor + timedelta(minutes=NEGATIVE_HORIZON_MINUTES)
        stages = earliest_stages(rows5, end, prior)
        t4 = stages.get("T4")
        t5 = stages.get("T5")

        # Determine whether an actual direct opposite transition occurred
        # during this probe horizon.
        actual = False
        for j in range(i + 1, min(len(rows30), i + 8)):
            if states[j] == opposite(prior) and states[j - 1] == prior:
                actual = True
                break

        if t4 is not None:
            out.append({
                "kind": "NEG",
                "symbol": symbol,
                "from": prior,
                "to": opposite(prior),
                "event_time": anchor,
                "end_time": end,
                "stages": stages,
                "actual_transition": actual,
                "false_t4": not actual,
                "false_t5": (t5 is not None and not actual),
            })

    return out


def split_cases(cases: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by = defaultdict(list)
    for c in cases:
        by[c["symbol"]].append(c)
    discovery: List[Dict[str, Any]] = []
    holdout: List[Dict[str, Any]] = []
    for rows in by.values():
        rows.sort(key=lambda x: x["event_time"])
        cut = int(len(rows) * 0.70)
        discovery.extend(rows[:cut])
        holdout.extend(rows[cut:])
    return discovery, holdout


def pct(n: int, d: int) -> float:
    return 100.0 * n / d if d else 0.0


def summarize_real(cases: Sequence[Dict[str, Any]], label: str) -> None:
    print(f"\n{label}")
    print("=" * len(label))
    print(f"CASES {len(cases)}")
    for stage in range(0, 6):
        key = f"T{stage}"
        rows = [c for c in cases if c["stages"].get(key) is not None]
        leads = [
            (c["event_time"] - c["stages"][key]).total_seconds() / 60.0
            for c in rows
        ]
        if leads:
            print(
                f"{key}: reached={len(rows)}/{len(cases)} ({pct(len(rows), len(cases)):.1f}%) "
                f"lead_mean={mean(leads):.1f}m median={median(leads):.1f}m "
                f"within15={pct(sum(x <= 15 for x in leads), len(leads)):.1f}% "
                f"within30={pct(sum(x <= 30 for x in leads), len(leads)):.1f}%"
            )
        else:
            print(f"{key}: reached=0/{len(cases)}")


def summarize_negative(cases: Sequence[Dict[str, Any]], label: str) -> None:
    print(f"\n{label}")
    print("=" * len(label))
    print(f"NEGATIVE PROBES {len(cases)}")
    if not cases:
        return
    t4 = [c for c in cases if c["stages"].get("T4") is not None]
    t5 = [c for c in cases if c["stages"].get("T5") is not None]
    false4 = [c for c in t4 if c.get("false_t4")]
    false5 = [c for c in t5 if c.get("false_t5")]
    print(f"T4 fired={len(t4)}/{len(cases)} ({pct(len(t4), len(cases)):.1f}%)")
    print(f"T4 false={len(false4)}/{len(cases)} ({pct(len(false4), len(cases)):.1f}%)")
    print(f"T5 fired={len(t5)}/{len(cases)} ({pct(len(t5), len(cases)):.1f}%)")
    print(f"T5 false={len(false5)}/{len(cases)} ({pct(len(false5), len(cases)):.1f}%)")


def stage_pairs(cases: Sequence[Dict[str, Any]], label: str) -> None:
    print(f"\nSTAGE-TO-STAGE TIMING — {label}")
    print("=" * (27 + len(label)))
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]:
        vals: List[float] = []
        for c in cases:
            ta = c["stages"].get(f"T{a}")
            tb = c["stages"].get(f"T{b}")
            if ta is not None and tb is not None and tb >= ta:
                vals.append((tb - ta).total_seconds() / 60.0)
        if vals:
            print(f"T{a}->T{b}: N={len(vals)} mean={mean(vals):.1f}m median={median(vals):.1f}m")


def by_direction(cases: Sequence[Dict[str, Any]], label: str) -> None:
    print(f"\nDIRECTION — {label}")
    print("=" * (13 + len(label)))
    for direction in ("LONG->SHORT", "SHORT->LONG"):
        a, b = direction.split("->")
        rows = [c for c in cases if c["from"] == a and c["to"] == b]
        print(f"{direction}: N={len(rows)}")
        for stage in ("T1", "T2", "T3", "T4", "T5"):
            n = sum(c["stages"].get(stage) is not None for c in rows)
            print(f"  {stage}: {n}/{len(rows)} ({pct(n, len(rows)):.1f}%)")


def run(symbols: Sequence[str], limit30: int, limit5: int) -> None:
    all_real: List[Dict[str, Any]] = []
    all_neg: List[Dict[str, Any]] = []

    print("KISS V5.1 MARKET STRUCTURE TRANSITION — RESEARCH ONLY")
    print("No orders. No DB writes. No engine changes.")
    print("Target: actual market structure with strict causal sequencing.")
    print("T0 weakness -> T1 failed continuation -> T2 structure break -> T3 new LL/HH -> T4 new structure -> T5 official 30m transition.")

    for symbol in symbols:
        rows30 = load(symbol, "30m", limit30)
        rows5 = load(symbol, "5m", limit5)
        real = evaluate_symbol(symbol, rows30, rows5)
        neg = negative_cases(symbol, rows30, rows5)
        all_real.extend(real)
        all_neg.extend(neg)
        print(f"{symbol}: real_cases={len(real)} negative_probes={len(neg)}")

    discovery, holdout = split_cases(all_real)
    neg_discovery, neg_holdout = split_cases(all_neg)

    print(f"\nREAL TOTAL {len(all_real)} discovery={len(discovery)} holdout={len(holdout)}")
    summarize_real(all_real, "FULL REAL")
    summarize_real(discovery, "DISCOVERY 70% REAL")
    summarize_real(holdout, "HOLDOUT 30% REAL")
    by_direction(all_real, "FULL REAL")
    by_direction(holdout, "HOLDOUT REAL")
    stage_pairs(discovery, "DISCOVERY")
    stage_pairs(holdout, "HOLDOUT")

    print(f"\nNEGATIVE TOTAL {len(all_neg)} discovery={len(neg_discovery)} holdout={len(neg_holdout)}")
    summarize_negative(all_neg, "FULL NEGATIVE")
    summarize_negative(neg_discovery, "DISCOVERY 70% NEGATIVE")
    summarize_negative(neg_holdout, "HOLDOUT 30% NEGATIVE")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="KISS V5.1 causal market structure transition research")
    p.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    p.add_argument("--limit30", type=int, default=5000)
    p.add_argument("--limit5", type=int, default=30000)
    args = p.parse_args()
    run(args.symbols, args.limit30, args.limit5)
