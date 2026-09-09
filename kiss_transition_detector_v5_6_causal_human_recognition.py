"""KISS V5.6 — Causal Human Recognition / Strict Sequential Transition.

RESEARCH ONLY. No orders. No DB writes. No engine changes.

V5.5 showed that independently scanning for WARNING, CHARACTER_CHANGE and
CONFIRMED_TRANSITION can produce impossible timelines where a later state is
found before an earlier state. V5.6 fixes that by processing completed 5m
candles strictly forward in time and locking each stage once it occurs.

The question is deliberately human and causal:

    OLD TREND HEALTHY
        -> continuation weakens
        -> recovery / counter-move fails
        -> opposite structure appears
        -> old structure breaks

LONG -> SHORT is mirrored for SHORT -> LONG.

Important timing rules:
- 30m timestamp is candle START; official state is known at its CLOSE (+30m).
- 5m evidence is known only at its CLOSE (+5m).
- A swing is usable only after SWING_LOOKBACK completed bars exist on its right.
- Stage N may only use evidence available after Stage N-1.
- No stage searches backward for evidence that existed before its predecessor.
- The official 30m MA transition is a reference event, NOT the definition of
  market truth.

V5.6 deliberately does not use RSI, ML, prediction scores, or trading rules.
It is a structural truth-test for the earliest causal human recognition point.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

TREND_WINDOW = 20
TREND_BAND = 0.002
SWING_LOOKBACK = 3
LOOKBACK_MINUTES = 120
POST_MINUTES = 120
TARGET_OFFSETS = (-60, -45, -30, -15, 0, 15, 30)
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


# ---------------------------------------------------------------------------
# Basic data helpers
# ---------------------------------------------------------------------------

def f(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return float("nan")


def dt(v: Any) -> datetime:
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
            "SELECT timestamp,open,high,low,close,volume "
            "FROM candles WHERE symbol=%s AND timeframe=%s "
            "ORDER BY timestamp ASC LIMIT %s",
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
                d[k] = f(d[k])
            out.append(d)
        return out
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


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
        if (
            states[i - 1] in ("LONG", "SHORT")
            and states[i] in ("LONG", "SHORT")
            and states[i] != states[i - 1]
        ):
            out.append({
                "i": i,
                "from": states[i - 1],
                "to": states[i],
                "time": rows[i]["timestamp"] + timedelta(minutes=30),
                "price": rows[i]["close"],
            })
    return out


def close_index(rows: Sequence[Dict[str, Any]], target: datetime) -> Optional[int]:
    for i, r in enumerate(rows):
        if r["timestamp"] + timedelta(minutes=5) == target:
            return i
    return None


def exact_window(rows: Sequence[Dict[str, Any]], t0: datetime) -> Optional[List[Dict[str, Any]]]:
    out: List[Dict[str, Any]] = []
    for off in TARGET_OFFSETS:
        i = close_index(rows, t0 + timedelta(minutes=off))
        if i is None:
            return None
        r = dict(rows[i])
        r["offset"] = off
        r["close_at"] = r["timestamp"] + timedelta(minutes=5)
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Causal swing detection
# ---------------------------------------------------------------------------

def confirmed_swings(
    rows: Sequence[Dict[str, Any]],
    idx: int,
) -> Tuple[List[int], List[int]]:
    """Return swings whose confirmation is available by rows[idx] CLOSE."""
    highs: List[int] = []
    lows: List[int] = []
    if idx < SWING_LOOKBACK * 2:
        return highs, lows

    for i in range(SWING_LOOKBACK, idx - SWING_LOOKBACK + 1):
        # Candle i is only known as a swing after the right-hand bars close.
        if i + SWING_LOOKBACK > idx:
            continue
        h = rows[i]["high"]
        l = rows[i]["low"]
        left_high = max(x["high"] for x in rows[i - SWING_LOOKBACK:i])
        right_high = max(x["high"] for x in rows[i + 1:i + SWING_LOOKBACK + 1])
        left_low = min(x["low"] for x in rows[i - SWING_LOOKBACK:i])
        right_low = min(x["low"] for x in rows[i + 1:i + SWING_LOOKBACK + 1])
        if h >= left_high and h >= right_high:
            highs.append(i)
        if l <= left_low and l <= right_low:
            lows.append(i)
    return highs, lows


def latest_before(values: Sequence[int], idx: int) -> Optional[int]:
    candidates = [x for x in values if x < idx]
    return candidates[-1] if candidates else None


# ---------------------------------------------------------------------------
# Causal human-recognition state machine
# ---------------------------------------------------------------------------

def signed_return(base: float, price: float, prior: str) -> float:
    raw = (price / base - 1.0) * 100.0
    return raw if prior == "LONG" else -raw


def local_health(
    rows: Sequence[Dict[str, Any]],
    idx: int,
    prior: str,
) -> Dict[str, Any]:
    """Describe only the behavior available at this completed 5m close."""
    start = max(0, idx - 12)
    closes = [rows[j]["close"] for j in range(start, idx + 1)]
    base = closes[0]
    signed = [signed_return(base, p, prior) for p in closes]

    progress = sum(1 for a, b in zip(signed, signed[1:]) if b > a)
    adverse = sum(1 for x in signed[1:] if x < 0)
    max_adverse = max(0.0, -min(signed)) if signed else 0.0

    # A local impulse is required before calling the latest move a failure.
    prior_move = signed[-2] - signed[-3] if len(signed) >= 3 else 0.0
    latest_move = signed[-1] - signed[-2] if len(signed) >= 2 else 0.0
    continuation_failed = (
        len(signed) >= 3
        and prior_move > 0.0
        and latest_move < 0.0
        and signed[-1] < signed[-2]
    )

    return {
        "signed": signed[-1] if signed else 0.0,
        "progress": progress,
        "adverse": adverse,
        "max_adverse": max_adverse,
        "prior_move": prior_move,
        "latest_move": latest_move,
        "continuation_failed": continuation_failed,
    }


def find_warning(
    rows: Sequence[Dict[str, Any]],
    idx: int,
    prior: str,
) -> bool:
    x = local_health(rows, idx, prior)
    if not x["continuation_failed"]:
        return False

    # Require two adverse closes inside the most recent 3 completed bars.
    moves = []
    for j in range(max(1, idx - 2), idx + 1):
        d = signed_return(rows[j - 1]["close"], rows[j]["close"], prior)
        moves.append(d)
    adverse_closes = sum(1 for d in moves if d < 0)
    return adverse_closes >= 1 and x["max_adverse"] > 0.0


def find_character_change(
    rows: Sequence[Dict[str, Any]],
    idx: int,
    prior: str,
    warning_idx: int,
) -> Tuple[bool, str]:
    """Require deterioration AFTER warning and then failed recovery or swing."""
    if idx <= warning_idx:
        return False, ""

    start = max(warning_idx, idx - 12)
    base = rows[warning_idx]["close"]
    signed = [signed_return(base, rows[j]["close"], prior) for j in range(start, idx + 1)]
    if len(signed) < 3:
        return False, ""

    # There must first be an attempted recovery toward the old direction.
    recovery_peak = max(signed[:-1])
    recovery_attempted = recovery_peak > 0.0
    latest_failed = signed[-1] < recovery_peak and signed[-1] < 0.0

    highs, lows = confirmed_swings(rows, idx)
    recent_start = max(warning_idx, idx - 12)
    recent_highs = [j for j in highs if recent_start <= j < idx]
    recent_lows = [j for j in lows if recent_start <= j < idx]

    opposite_swing = False
    if prior == "LONG":
        # A confirmed lower high / lower low after warning is opposite structure.
        if len(recent_highs) >= 1 and len(recent_lows) >= 1:
            last_high = recent_highs[-1]
            last_low = recent_lows[-1]
            opposite_swing = rows[last_low]["low"] < rows[warning_idx]["low"] or (
                rows[last_high]["high"] < rows[warning_idx]["high"]
            )
    else:
        # Mirror: higher low / higher high after warning.
        if len(recent_highs) >= 1 and len(recent_lows) >= 1:
            last_high = recent_highs[-1]
            last_low = recent_lows[-1]
            opposite_swing = rows[last_high]["high"] > rows[warning_idx]["high"] or (
                rows[last_low]["low"] > rows[warning_idx]["low"]
            )

    if recovery_attempted and latest_failed:
        return True, "recovery_attempt_failed"
    if opposite_swing:
        return True, "confirmed_opposite_structure"
    return False, ""


def find_confirmation(
    rows: Sequence[Dict[str, Any]],
    idx: int,
    prior: str,
    warning_idx: int,
    change_idx: int,
) -> Tuple[bool, str]:
    """Confirm a break of the immediate pre-change structural level."""
    if idx <= change_idx:
        return False, ""

    highs, lows = confirmed_swings(rows, idx)
    # Only swings formed before CHARACTER_CHANGE may define the old structure.
    old_highs = [j for j in highs if warning_idx <= j < change_idx]
    old_lows = [j for j in lows if warning_idx <= j < change_idx]

    if prior == "LONG":
        # For LONG->SHORT, break the most recent confirmed higher-low.
        if old_lows:
            level_idx = old_lows[-1]
            if rows[idx]["close"] < rows[level_idx]["low"]:
                return True, f"break_prior_higher_low_{rows[level_idx]['timestamp'].strftime('%H:%M')}"
    else:
        # For SHORT->LONG, break the most recent confirmed lower-high.
        if old_highs:
            level_idx = old_highs[-1]
            if rows[idx]["close"] > rows[level_idx]["high"]:
                return True, f"break_prior_lower_high_{rows[level_idx]['timestamp'].strftime('%H:%M')}"

    return False, ""


def causal_state_machine(
    rows: Sequence[Dict[str, Any]],
    event: Dict[str, Any],
) -> Dict[str, Any]:
    """Walk forward in time; every stage is strictly downstream of the prior."""
    t0 = event["time"]
    prior = event["from"]
    start = close_index(rows, t0 - timedelta(minutes=LOOKBACK_MINUTES))
    end = close_index(rows, t0 + timedelta(minutes=POST_MINUTES))
    if start is None or end is None:
        return {"usable": False}

    stage = "NORMAL"
    warning_idx: Optional[int] = None
    change_idx: Optional[int] = None
    confirm_idx: Optional[int] = None
    events: List[Dict[str, Any]] = []

    for idx in range(start, end + 1):
        obs = rows[idx]["timestamp"] + timedelta(minutes=5)

        if stage == "NORMAL" and find_warning(rows, idx, prior):
            stage = "WARNING"
            warning_idx = idx
            events.append({
                "stage": "WARNING",
                "idx": idx,
                "time": obs,
                "minutes_to_t0": (t0 - obs).total_seconds() / 60.0,
                "reason": "continuation_weakens_after_local_progress",
            })
            continue

        if stage == "WARNING" and warning_idx is not None:
            ok, reason = find_character_change(rows, idx, prior, warning_idx)
            if ok:
                stage = "CHARACTER_CHANGE"
                change_idx = idx
                events.append({
                    "stage": "CHARACTER_CHANGE",
                    "idx": idx,
                    "time": obs,
                    "minutes_to_t0": (t0 - obs).total_seconds() / 60.0,
                    "reason": reason,
                })
                continue

        if stage == "CHARACTER_CHANGE" and warning_idx is not None and change_idx is not None:
            ok, reason = find_confirmation(rows, idx, prior, warning_idx, change_idx)
            if ok:
                stage = "CONFIRMED_TRANSITION"
                confirm_idx = idx
                events.append({
                    "stage": "CONFIRMED_TRANSITION",
                    "idx": idx,
                    "time": obs,
                    "minutes_to_t0": (t0 - obs).total_seconds() / 60.0,
                    "reason": reason,
                })
                # Once confirmed, stop detection. Post-T0 continuation is
                # measured separately and cannot alter the recognition result.
                break

    return {
        "usable": True,
        "events": events,
        "stage": stage,
        "warning_idx": warning_idx,
        "change_idx": change_idx,
        "confirm_idx": confirm_idx,
    }


# ---------------------------------------------------------------------------
# Separate outcome check — never used to create recognition stages
# ---------------------------------------------------------------------------

def post_t0_behavior(
    rows: Sequence[Dict[str, Any]],
    event: Dict[str, Any],
) -> Dict[str, Any]:
    t0 = event["time"]
    i0 = close_index(rows, t0)
    if i0 is None:
        return {}
    base = rows[i0]["close"]
    prior = event["from"]
    signed = lambda p: signed_return(base, p, prior)
    out: Dict[str, Any] = {}
    for mins in (15, 30, 60, 120):
        i = close_index(rows, t0 + timedelta(minutes=mins))
        if i is not None:
            out[f"ret_{mins}m"] = signed(rows[i]["close"])
    return out


def print_case(
    symbol: str,
    rows: Sequence[Dict[str, Any]],
    event: Dict[str, Any],
    n: int,
) -> Optional[Dict[str, Any]]:
    if exact_window(rows, event["time"]) is None:
        return None
    result = causal_state_machine(rows, event)
    if not result["usable"]:
        return None

    print(
        f"\nCASE {n} {symbol} {event['from']}->{event['to']} "
        f"T0={event['time'].strftime('%Y-%m-%d %H:%M')} "
        f"official_price={event['price']:.2f}"
    )
    print("STRICT CAUSAL RECOGNITION:")
    for name in ("WARNING", "CHARACTER_CHANGE", "CONFIRMED_TRANSITION"):
        z = next((x for x in result["events"] if x["stage"] == name), None)
        if z:
            print(
                f"  {name:<21} {z['time'].strftime('%Y-%m-%d %H:%M')} "
                f"({z['minutes_to_t0']:+.0f}m) {z['reason']}"
            )
        else:
            print(f"  {name:<21} --")

    print(f"FINAL CAUSAL STATE: {result['stage']}")
    print("CAUSAL TIMELINE:")
    if result["events"]:
        for z in result["events"]:
            print(
                f"  {z['time'].strftime('%H:%M')}  "
                f"{z['stage']:<21} {z['reason']}"
            )
    else:
        print("  -- NO CAUSAL RECOGNITION --")

    outcome = post_t0_behavior(rows, event)
    if outcome:
        print("POST-T0 OUTCOME (NOT USED FOR DETECTION):")
        for k, v in outcome.items():
            print(f"  {k:<10} {v:+.3f}%")

    print("5M PATH T-60..T+30:")
    for r in exact_window(rows, event["time"]) or []:
        print(
            f"  T{r['offset']:+d} {r['close_at'].strftime('%H:%M')} "
            f"O={r['open']:.2f} H={r['high']:.2f} "
            f"L={r['low']:.2f} C={r['close']:.2f}"
        )

    return {
        "direction": f"{event['from']}->{event['to']}",
        "events": result["events"],
        "final_stage": result["stage"],
        "outcome": outcome,
    }


def summarize(cases: Sequence[Dict[str, Any]], direction: str) -> None:
    subset = [x for x in cases if x["direction"] == direction]
    print(f"\n{direction}: N={len(subset)}")
    for stage in ("WARNING", "CHARACTER_CHANGE", "CONFIRMED_TRANSITION"):
        vals: List[float] = []
        for case in subset:
            z = next((x for x in case["events"] if x["stage"] == stage), None)
            if z:
                vals.append(z["minutes_to_t0"])
        if vals:
            vals.sort()
            med = vals[len(vals) // 2]
            print(
                f"  {stage:<21} N={len(vals):>2} "
                f"mean={sum(vals)/len(vals):.1f}m "
                f"median={med:.1f}m "
                f"earliest={max(vals):.1f}m"
            )
        else:
            print(f"  {stage:<21} N=0")

    complete = sum(1 for x in subset if x["final_stage"] == "CONFIRMED_TRANSITION")
    print(f"  COMPLETE SEQUENCE     {complete}/{len(subset)}")


def run(
    symbols: Sequence[str],
    limit30: int = 10000,
    limit5: int = 50000,
) -> None:
    print("KISS V5.6 CAUSAL HUMAN RECOGNITION — RESEARCH ONLY")
    print("Strict sequential state machine: NORMAL -> WARNING -> CHARACTER_CHANGE -> CONFIRMED_TRANSITION")
    print("No orders. No DB writes. No engine changes. No RSI. No ML.\n")

    known = 0
    usable = 0
    skipped = 0
    cases: List[Dict[str, Any]] = []

    for symbol in symbols:
        rows30 = load(symbol, "30m", limit30)
        rows5 = load(symbol, "5m", limit5)
        ev = transitions(rows30)
        print(f"{symbol}: 30m={len(rows30)} 5m={len(rows5)} transitions={len(ev)}")
        for n, event in enumerate(ev, 1):
            known += 1
            if exact_window(rows5, event["time"]) is None:
                skipped += 1
                continue
            result = print_case(symbol, rows5, event, n)
            if result is not None:
                usable += 1
                cases.append(result)

    print("\n================ V5.6 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {known}")
    print(f"USABLE COMPLETE V5.6 WINDOWS: {usable}")
    print(f"SKIPPED FOR INCOMPLETE 5M COVERAGE: {skipped}")
    summarize(cases, "LONG->SHORT")
    summarize(cases, "SHORT->LONG")
    print("\nV5.6 KEY RULE: each stage can only occur after the previous stage.")
    print("V5.6 is a causal research timeline, not a trading rule.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="KISS V5.6 causal human recognition")
    ap.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    ap.add_argument("--limit30", type=int, default=10000)
    ap.add_argument("--limit5", type=int, default=50000)
    args = ap.parse_args()
    run(args.symbols, args.limit30, args.limit5)
