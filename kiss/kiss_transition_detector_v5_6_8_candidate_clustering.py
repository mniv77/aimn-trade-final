"""KISS V5.6.8 — Candidate Clustering & Earliest Reliable Exit.

RESEARCH ONLY.
No orders. No DB writes. No KISS engine changes. No RSI. No ML.

V5.6.7.2 proved that causal deterioration candidates contain useful signal,
but it produced many overlapping candidate events inside the same deterioration
episode. Counting every candidate independently can therefore exaggerate the
quality of an exit idea.

V5.6.8 groups nearby causal candidates into one episode and compares three
CAUSAL choices inside each episode:
  1. FIRST    — earliest candidate in the episode.
  2. STRONGEST — strongest candidate using only information available then.
  3. LAST     — latest candidate before the episode ends.

For research only, an ORACLE_BEST is also reported. It is selected using the
future 60m outcome and MUST NOT be used as a trading rule. It answers the
question: how much timing opportunity existed inside the episode?

The key test is no longer "how many candidates were good?" It is:
  "When several candidates belong to the same deterioration episode, which
   causal point gives the best trade-off between being early and avoiding a
   false exit?"

Future candles are used ONLY for evaluation after a causal candidate has been
selected. Candidate selection itself never consults future candles.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
SWING_LOOKBACK = 3
LOOKBACK_MINUTES = 480
MIN_HISTORY_MINUTES = 120
POST_MINUTES = 120
EVAL_MINUTES = 60
EXIT_BUFFER = 0.10
EPISODE_GAP_MINUTES = 15
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


def num(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return float("nan")


def dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00").replace("+00:00", "")).replace(tzinfo=None)


def load(symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    conn, cur = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        cur.execute(
            "SELECT timestamp,open,high,low,close,volume FROM candles "
            "WHERE symbol=%s AND timeframe=%s ORDER BY timestamp ASC LIMIT %s",
            (symbol, timeframe, int(limit)),
        )
        out: List[Dict[str, Any]] = []
        for r in cur.fetchall() or []:
            d = dict(r) if isinstance(r, dict) else {
                "timestamp": r[0], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4], "volume": r[5]
            }
            d["timestamp"] = dt(d["timestamp"])
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


def close_time(r: Dict[str, Any]) -> datetime:
    return r["timestamp"] + timedelta(minutes=5)


def state(closes: Sequence[float], i: int) -> str:
    if i < TREND_WINDOW or i >= len(closes):
        return "FLAT"
    ma = sum(closes[i - TREND_WINDOW:i]) / TREND_WINDOW
    if closes[i] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[i] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def transitions(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [r["close"] for r in rows]
    states = [state(closes, i) for i in range(len(rows))]
    out: List[Dict[str, Any]] = []
    for i in range(TREND_WINDOW + 1, len(rows)):
        if states[i - 1] in ("LONG", "SHORT") and states[i] in ("LONG", "SHORT") and states[i] != states[i - 1]:
            out.append({
                "i": i,
                "from": states[i - 1],
                "to": states[i],
                "time": rows[i]["timestamp"] + timedelta(minutes=30),
                "price": rows[i]["close"],
            })
    return out


def nearest_completed_close(rows: Sequence[Dict[str, Any]], target: datetime) -> Tuple[Optional[int], Optional[float]]:
    best: Optional[int] = None
    best_diff: Optional[float] = None
    for i, r in enumerate(rows):
        ct = close_time(r)
        if ct > target:
            continue
        diff = (target - ct).total_seconds() / 60.0
        if best_diff is None or diff < best_diff:
            best = i
            best_diff = diff
    return best, best_diff


def exact_close_index(rows: Sequence[Dict[str, Any]], target: datetime) -> Optional[int]:
    for i, r in enumerate(rows):
        if close_time(r) == target:
            return i
    return None


def signed_return(base: float, price: float, prior: str) -> float:
    raw = (price / base - 1.0) * 100.0
    return raw if prior == "LONG" else -raw


def confirmed_swings(rows: Sequence[Dict[str, Any]], idx: int) -> Tuple[List[int], List[int]]:
    highs: List[int] = []
    lows: List[int] = []
    for i in range(SWING_LOOKBACK, idx - SWING_LOOKBACK + 1):
        if i + SWING_LOOKBACK > idx:
            continue
        h = rows[i]["high"]
        l = rows[i]["low"]
        left_h = max(rows[j]["high"] for j in range(i - SWING_LOOKBACK, i))
        right_h = max(rows[j]["high"] for j in range(i + 1, i + SWING_LOOKBACK + 1))
        left_l = min(rows[j]["low"] for j in range(i - SWING_LOOKBACK, i))
        right_l = min(rows[j]["low"] for j in range(i + 1, i + SWING_LOOKBACK + 1))
        if h >= left_h and h >= right_h:
            highs.append(i)
        if l <= left_l and l <= right_l:
            lows.append(i)
    return highs, lows


def health(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    start = max(0, idx - 11)
    closes = [rows[j]["close"] for j in range(start, idx + 1)]
    moves = [signed_return(closes[k - 1], closes[k], prior) for k in range(1, len(closes))]
    adverse = sum(x < 0 for x in moves)
    progress = sum(x > 0 for x in moves)
    net = signed_return(closes[0], closes[-1], prior) if len(closes) > 1 else 0.0
    consecutive = 0
    for x in reversed(moves):
        if x < 0:
            consecutive += 1
        else:
            break
    return {"adverse": adverse, "progress": progress, "net": net, "consecutive": consecutive}


def structure_break(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str]:
    highs, lows = confirmed_swings(rows, idx)
    if prior == "LONG":
        candidates = [j for j in lows if j < idx]
        if candidates and rows[idx]["close"] < rows[candidates[-1]]["low"]:
            j = candidates[-1]
            return True, f"break_higher_low_{rows[j]['timestamp'].strftime('%H:%M')}"
    else:
        candidates = [j for j in highs if j < idx]
        if candidates and rows[idx]["close"] > rows[candidates[-1]]["high"]:
            j = candidates[-1]
            return True, f"break_lower_high_{rows[j]['timestamp'].strftime('%H:%M')}"
    return False, ""


def candidate_signal(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Tuple[bool, str, float]:
    """Causal candidate plus a causal-only strength score."""
    h = health(rows, idx, prior)
    structural, reason = structure_break(rows, idx, prior)
    persistent = h["consecutive"] >= 2 and h["net"] <= -0.20
    balanced = h["adverse"] >= 6 and h["net"] <= -0.30

    # Score is deliberately simple and entirely causal.
    # Structural damage is stronger than pressure-only evidence; pressure
    # persistence and breadth add strength without using future outcomes.
    score = 0.0
    if structural:
        score += 3.0
    if persistent:
        score += 2.0
    if balanced:
        score += 1.0
    score += min(1.0, max(0.0, -h["net"]) / 1.0)
    score += min(0.5, h["consecutive"] * 0.10)

    if structural:
        return True, reason, score
    if persistent:
        return True, "two_or_more_consecutive_adverse_closes", score
    if balanced:
        return True, "persistent_adverse_balance", score
    return False, "", score


def evaluate(rows: Sequence[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    future = []
    base_time = close_time(rows[idx])
    for j in range(idx + 1, len(rows)):
        elapsed = (close_time(rows[j]) - base_time).total_seconds() / 60.0
        if elapsed > EVAL_MINUTES:
            break
        future.append(j)
    if not future:
        return {"status": "UNKNOWN", "hold60": None, "best": None, "worst": None}
    base = rows[idx]["close"]
    vals = [signed_return(base, rows[j]["close"], prior) for j in future]
    final = vals[-1]
    if final <= -EXIT_BUFFER:
        status = "GOOD_EXIT"
    elif final >= EXIT_BUFFER:
        status = "FALSE_EXIT"
    else:
        status = "NEUTRAL"
    return {"status": status, "hold60": final, "best": max(vals), "worst": min(vals)}


def outcome_at(rows: Sequence[Dict[str, Any]], idx: int, prior: str, minutes: int) -> Optional[float]:
    j = exact_close_index(rows, close_time(rows[idx]) + timedelta(minutes=minutes))
    if j is None:
        return None
    return signed_return(rows[idx]["close"], rows[j]["close"], prior)


def run_case(rows: Sequence[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
    t0 = event["time"]
    prior = event["from"]
    requested_start = t0 - timedelta(minutes=LOOKBACK_MINUTES)
    start, start_diff = nearest_completed_close(rows, requested_start)
    if start is None:
        return {"usable": False}
    end, end_diff = nearest_completed_close(rows, t0 + timedelta(minutes=POST_MINUTES))
    if end is None or end <= start:
        return {"usable": False}
    available_history = (t0 - close_time(rows[start])).total_seconds() / 60.0
    if available_history < MIN_HISTORY_MINUTES:
        return {"usable": False}

    candidates: List[Dict[str, Any]] = []
    for idx in range(start, end + 1):
        ok, reason, score = candidate_signal(rows, idx, prior)
        if not ok:
            continue
        ev = evaluate(rows, idx, prior)
        candidates.append({
            "idx": idx,
            "time": close_time(rows[idx]),
            "minutes_to_t0": (t0 - close_time(rows[idx])).total_seconds() / 60.0,
            "boundary": idx == start,
            "reason": reason,
            "score": score,
            "evaluation": ev,
            "ret15": outcome_at(rows, idx, prior, 15),
            "ret30": outcome_at(rows, idx, prior, 30),
            "ret60": outcome_at(rows, idx, prior, 60),
            "ret120": outcome_at(rows, idx, prior, 120),
        })
    return {
        "usable": True,
        "requested_start": requested_start,
        "actual_start": close_time(rows[start]),
        "start_offset": start_diff,
        "actual_end": close_time(rows[end]),
        "end_offset": end_diff,
        "available_history": available_history,
        "candidates": candidates,
    }


def cluster(candidates: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Group candidates into episodes using only candidate timestamps."""
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda x: x["time"])
    episodes: List[List[Dict[str, Any]]] = [[ordered[0]]]
    for c in ordered[1:]:
        gap = (c["time"] - episodes[-1][-1]["time"]).total_seconds() / 60.0
        if gap <= EPISODE_GAP_MINUTES:
            episodes[-1].append(c)
        else:
            episodes.append([c])
    return episodes


def choose_episode(ep: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    first = min(ep, key=lambda c: c["time"])
    strongest = max(ep, key=lambda c: (c["score"], c["time"]))
    last = max(ep, key=lambda c: c["time"])
    valid = [c for c in ep if c["evaluation"]["hold60"] is not None]
    oracle = min(valid, key=lambda c: c["evaluation"]["hold60"]) if valid else None
    return {"FIRST": first, "STRONGEST": strongest, "LAST": last, "ORACLE_BEST": oracle}


def pct(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(records: List[Dict[str, Any]], total: int, skipped: int) -> None:
    print("\n================ V5.6.8 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.8 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INSUFFICIENT 5M COVERAGE: {skipped}")
    all_eps: List[Dict[str, Any]] = []
    for rec in records:
        eps = cluster(rec["result"]["candidates"])
        for ep in eps:
            picks = choose_episode(ep)
            all_eps.append({"direction": rec["direction"], "symbol": rec["symbol"], "event": rec["event"], "episode": ep, "picks": picks})

    print(f"DETERIORATION EPISODES: {len(all_eps)}")
    print(f"EPISODE GAP RULE: <= {EPISODE_GAP_MINUTES} MINUTES")
    print("\nCAUSAL DECISION POINT COMPARISON")
    for direction in ("LONG->SHORT", "SHORT->LONG", "ALL"):
        eps = all_eps if direction == "ALL" else [e for e in all_eps if e["direction"] == direction]
        print(f"\n{direction} EPISODES N={len(eps)}")
        for label in ("FIRST", "STRONGEST", "LAST", "ORACLE_BEST"):
            picks = [e["picks"][label] for e in eps if e["picks"][label] is not None]
            valid = [p for p in picks if p["evaluation"]["hold60"] is not None]
            good = sum(p["evaluation"]["status"] == "GOOD_EXIT" for p in valid)
            false = sum(p["evaluation"]["status"] == "FALSE_EXIT" for p in valid)
            neutral = sum(p["evaluation"]["status"] == "NEUTRAL" for p in valid)
            avg_hold = pct([p["evaluation"]["hold60"] for p in valid])
            avg_t = pct([p["minutes_to_t0"] for p in picks])
            print(f"  {label:<12} N={len(picks):4d} valid={len(valid):4d} good={good:4d} false={false:4d} neutral={neutral:4d} good_rate={good/len(valid)*100 if valid else 0:.1f}% false_rate={false/len(valid)*100 if valid else 0:.1f}% avg_hold60={avg_hold:+.3f}% avg_minutes_to_t0={avg_t:+.1f}")

    # Most important: compare the three causal choices against each other.
    print("\nCAUSAL TIMING COMPARISON (FIRST vs STRONGEST vs LAST)")
    for label in ("FIRST", "STRONGEST", "LAST"):
        picks = [e["picks"][label] for e in all_eps]
        valid = [p for p in picks if p["evaluation"]["hold60"] is not None]
        saved = [-p["evaluation"]["hold60"] for p in valid]
        print(f"  {label:<12} N={len(valid):4d} avg_exit_advantage={pct(saved):+.3f}% avg_hold60={pct([p['evaluation']['hold60'] for p in valid]):+.3f}%")

    # Episode-level ranking: which causal choice actually won the 60m test?
    wins = {"FIRST": 0, "STRONGEST": 0, "LAST": 0, "TIE": 0}
    for e in all_eps:
        vals = {}
        for label in ("FIRST", "STRONGEST", "LAST"):
            p = e["picks"][label]
            if p is not None and p["evaluation"]["hold60"] is not None:
                vals[label] = p["evaluation"]["hold60"]
        if not vals:
            continue
        best = min(vals.values())
        winners = [k for k, v in vals.items() if abs(v - best) < 1e-9]
        if len(winners) == 1:
            wins[winners[0]] += 1
        else:
            wins["TIE"] += 1
    print("\nEPISODE WINNER AT +60M (FUTURE EVALUATION ONLY)")
    print(f"  FIRST      {wins['FIRST']}")
    print(f"  STRONGEST  {wins['STRONGEST']}")
    print(f"  LAST       {wins['LAST']}")
    print(f"  TIE        {wins['TIE']}")

    print("\nV5.6.8 KEY TEST: WHICH CAUSAL POINT IS THE BEST EXIT POINT INSIDE AN EPISODE?")
    print("V5.6.8 clusters overlapping candidates so one deterioration episode is not counted as dozens of independent events.")
    print("FIRST, STRONGEST, and LAST are causal choices; ORACLE_BEST uses future data only as a research upper bound.")
    print("V5.6.8 is research only — no trading rule or engine change.")


def print_case(n: int, rec: Dict[str, Any]) -> None:
    event = rec["event"]
    result = rec["result"]
    eps = cluster(result["candidates"])
    print(f"\nCASE {n} {rec['symbol']} {rec['direction']} T0={event['time']} candidates={len(result['candidates'])} episodes={len(eps)}")
    for k, ep in enumerate(eps[:4], 1):
        picks = choose_episode(ep)
        print(f"  EPISODE {k}: {ep[0]['time']} -> {ep[-1]['time']} candidates={len(ep)}")
        for label in ("FIRST", "STRONGEST", "LAST", "ORACLE_BEST"):
            p = picks[label]
            if p is None:
                continue
            ev = p["evaluation"]
            print(f"    {label:<12} {p['time']} ({p['minutes_to_t0']:+.0f}m) score={p['score']:.2f} {p['reason']} -> {ev['status']} hold60={ev['hold60'] if ev['hold60'] is not None else '--'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    args = ap.parse_args()

    records: List[Dict[str, Any]] = []
    total = 0
    skipped = 0
    case_no = 0
    for symbol in args.symbols:
        rows30 = load(symbol, "30m", 100000)
        rows5 = load(symbol, "5m", 300000)
        for event in transitions(rows30):
            total += 1
            result = run_case(rows5, event)
            if not result["usable"]:
                skipped += 1
                continue
            direction = f"{event['from']}->{event['to']}"
            rec = {"symbol": symbol, "direction": direction, "event": event, "result": result}
            records.append(rec)
            case_no += 1
            if case_no <= 12:
                print_case(case_no, rec)
    summarize(records, total, skipped)


if __name__ == "__main__":
    main()
