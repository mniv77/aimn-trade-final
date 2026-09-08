"""KISS transition detector V2 — exact event timing, research only.

Purpose:
    Measure how early 5m evidence can recognize a REAL direct
    LONG <-> SHORT transition before the 30m transition is actually known.

Important timing model:
    The candle loaders store yfinance 30m/5m bar timestamps. Those timestamps
    represent the START of each candle. Therefore a 30m state based on candle i
    is only known when candle i closes: timestamp + 30 minutes.
    A 5m observation is only available when that 5m candle closes:
    timestamp + 5 minutes.

This file does NOT change KISS execution, place orders, or write to MySQL.
It intentionally fixes the V1 evaluation problem before adding more detector
complexity.

Positive event:
    state[i-1] is LONG and state[i] is SHORT, or vice versa.
    The official transition time is rows30[i].timestamp + 30 minutes.

Positive candidates:
    Completed 5m bars in the 60 minutes before the official transition,
    through the transition 30m candle. Every feature uses only information
    available at that 5m close.

Negative opportunity:
    A 30m candle whose prior state is LONG/SHORT and for which no direct
    opposite transition becomes known within the following 60 minutes.
    A warning inside that 30m candle is counted as a false alarm.

The detector uses the same simple V1 evidence first so that this experiment
changes ONE thing: measurement correctness. No new strategy rule is declared.
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
RSI_PERIOD = 14
MIN_5M_HISTORY = 20
LOOKBACK_MINUTES = 60
NEGATIVE_HORIZON_MINUTES = 60
SCORE_THRESHOLDS = (2, 3, 4)
DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"]


def num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def ts(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None)


def load(symbol: str, timeframe: str, limit: int) -> List[Dict[str, Any]]:
    conn, cur = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        cur.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles
               WHERE symbol=%s AND timeframe=%s
               ORDER BY timestamp ASC LIMIT %s""",
            (symbol, timeframe, int(limit)),
        )
        rows = cur.fetchall() or []
        out = []
        for r in rows:
            d = dict(r) if isinstance(r, dict) else {
                "timestamp": r[0], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4], "volume": r[5]
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


def rsi_series(closes: Sequence[float], period: int = RSI_PERIOD) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains, losses = [], []
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        gain, loss = max(d, 0.0), max(-d, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def opposite(state: str) -> str:
    return "SHORT" if state == "LONG" else "LONG"


def direct_transitions(rows30: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    closes = [r["close"] for r in rows30]
    states = [market_state(closes, i) for i in range(len(rows30))]
    events = []
    for i in range(TREND_WINDOW + 1, len(rows30)):
        a, b = states[i - 1], states[i]
        if a in ("LONG", "SHORT") and b == opposite(a):
            # yfinance timestamp is candle START; state becomes known at close.
            known_time = rows30[i]["timestamp"] + timedelta(minutes=30)
            events.append({
                "index": i,
                "bar_time": rows30[i]["timestamp"],
                "known_time": known_time,
                "from": a,
                "to": b,
                "price": rows30[i]["close"],
            })
    return events


def feature_score(
    bars: Sequence[Dict[str, Any]],
    prior_state: str,
    rsi_value: Optional[float],
    ma_distance_pct: float,
) -> Tuple[int, List[str]]:
    if len(bars) < MIN_5M_HISTORY:
        return 0, []
    closes = [x["close"] for x in bars]
    highs = [x["high"] for x in bars]
    lows = [x["low"] for x in bars]
    score = 0
    reasons: List[str] = []

    if prior_state == "LONG":
        streak = 0
        for a, b in zip(reversed(closes), reversed(closes[:-1])):
            if a < b:
                streak += 1
            else:
                break
    else:
        streak = 0
        for a, b in zip(reversed(closes), reversed(closes[:-1])):
            if a > b:
                streak += 1
            else:
                break
    if streak >= 2:
        score += 1
        reasons.append(f"opposite_streak={streak}")

    prior_high = max(highs[-4:-1])
    prior_low = min(lows[-4:-1])
    if prior_state == "LONG" and closes[-1] < prior_low:
        score += 1
        reasons.append("break_recent_low")
    elif prior_state == "SHORT" and closes[-1] > prior_high:
        score += 1
        reasons.append("break_recent_high")

    moves = [closes[i] - closes[i - 1] for i in range(len(closes) - 3, len(closes))]
    opp = sum(1 for x in moves if (x < 0 if prior_state == "LONG" else x > 0))
    if opp >= 2:
        score += 1
        reasons.append(f"2of3_opposite={opp}")

    if prior_state == "LONG":
        ref = max(highs[-3:])
        adverse = (1.0 - closes[-1] / ref) * 100.0 if ref else 0.0
    else:
        ref = min(lows[-3:])
        adverse = (closes[-1] / ref - 1.0) * 100.0 if ref else 0.0
    if adverse >= 0.20:
        score += 1
        reasons.append(f"adverse={adverse:.3f}%")

    if rsi_value is not None:
        if prior_state == "LONG" and rsi_value < 45.0:
            score += 1
            reasons.append(f"rsi_context={rsi_value:.1f}")
        elif prior_state == "SHORT" and rsi_value > 55.0:
            score += 1
            reasons.append(f"rsi_context={rsi_value:.1f}")

    if prior_state == "LONG" and ma_distance_pct < 0.40:
        score += 1
        reasons.append(f"30m_distance={ma_distance_pct:.3f}%")
    elif prior_state == "SHORT" and ma_distance_pct > -0.40:
        score += 1
        reasons.append(f"30m_distance={ma_distance_pct:.3f}%")

    return score, reasons


def context_distance(rows30: Sequence[Dict[str, Any]], closes30: Sequence[float], idx: int) -> float:
    if idx < TREND_WINDOW:
        return 0.0
    ma = sum(closes30[idx - TREND_WINDOW:idx]) / TREND_WINDOW
    return 0.0 if ma == 0 else (closes30[idx] / ma - 1.0) * 100.0


def score_at(
    rows5: Sequence[Dict[str, Any]], rsi5: Sequence[Optional[float]],
    bt: datetime, prior_state: str, ma_distance: float,
) -> Tuple[int, List[str]]:
    hist = [r for r in rows5 if r["timestamp"] + timedelta(minutes=5) <= bt]
    # A 5m observation is usable only after that candle closes.
    if len(hist) < MIN_5M_HISTORY:
        return 0, []
    idx = len(hist) - 1
    return feature_score(hist[-20:], prior_state, rsi5[idx], ma_distance)


def build_positive_cases(
    rows30: Sequence[Dict[str, Any]], rows5: Sequence[Dict[str, Any]],
    symbol: str,
) -> List[Dict[str, Any]]:
    closes30 = [r["close"] for r in rows30]
    rsi5 = rsi_series([r["close"] for r in rows5])
    out = []
    for e in direct_transitions(rows30):
        start = e["known_time"] - timedelta(minutes=LOOKBACK_MINUTES)
        end = e["known_time"]
        candidates = [r for r in rows5 if start <= r["timestamp"] + timedelta(minutes=5) <= end]
        if not candidates:
            continue
        ma_dist = context_distance(rows30, closes30, e["index"] - 1)
        rows = []
        for bar in candidates:
            obs_time = bar["timestamp"] + timedelta(minutes=5)
            score, reasons = score_at(rows5, rsi5, obs_time, e["from"], ma_dist)
            rows.append({
                "time": obs_time, "score": score, "reasons": reasons,
                "known_time": e["known_time"], "transition": e,
            })
        out.append({
            "kind": "REAL",
            "symbol": symbol,
            "event_time": e["known_time"],
            "from": e["from"], "to": e["to"],
            "candidates": rows,
        })
    return out


def has_opposite_within(
    transition_events: Sequence[Dict[str, Any]],
    anchor_time: datetime,
    prior_state: str,
) -> bool:
    target = opposite(prior_state)
    horizon = anchor_time + timedelta(minutes=NEGATIVE_HORIZON_MINUTES)
    return any(e["known_time"] > anchor_time and e["known_time"] <= horizon and e["to"] == target for e in transition_events)


def build_negative_cases(
    rows30: Sequence[Dict[str, Any]], rows5: Sequence[Dict[str, Any]], symbol: str,
) -> List[Dict[str, Any]]:
    closes30 = [r["close"] for r in rows30]
    states = [market_state(closes30, i) for i in range(len(rows30))]
    transitions = direct_transitions(rows30)
    rsi5 = rsi_series([r["close"] for r in rows5])
    out = []
    for i in range(TREND_WINDOW + 1, len(rows30) - 2):
        prior = states[i - 1]
        if prior not in ("LONG", "SHORT"):
            continue
        anchor_close = rows30[i]["timestamp"] + timedelta(minutes=30)
        if has_opposite_within(transitions, anchor_close, prior):
            continue
        # Only the six 5m observations belonging to this 30m opportunity.
        start = rows30[i]["timestamp"]
        end = start + timedelta(minutes=30)
        candidates = [r for r in rows5 if start <= r["timestamp"] + timedelta(minutes=5) <= end]
        if not candidates:
            continue
        ma_dist = context_distance(rows30, closes30, i - 1)
        rows = []
        for bar in candidates:
            obs_time = bar["timestamp"] + timedelta(minutes=5)
            score, reasons = score_at(rows5, rsi5, obs_time, prior, ma_dist)
            rows.append({"time": obs_time, "score": score, "reasons": reasons})
        out.append({
            "kind": "NEGATIVE", "symbol": symbol, "event_time": anchor_close,
            "from": prior, "to": opposite(prior), "candidates": rows,
        })
    return out


def split_cases(cases: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    by = defaultdict(list)
    for c in cases:
        by[c["symbol"]].append(c)
    discovery, holdout = [], []
    for symbol, rows in by.items():
        rows.sort(key=lambda x: x["event_time"])
        cut = int(len(rows) * 0.70)
        discovery.extend(rows[:cut])
        holdout.extend(rows[cut:])
    return discovery, holdout


def pct(n: int, d: int) -> float:
    return 0.0 if d == 0 else 100.0 * n / d


def evaluate(cases: Sequence[Dict[str, Any]], threshold: int, label: str) -> None:
    real = [c for c in cases if c["kind"] == "REAL"]
    neg = [c for c in cases if c["kind"] == "NEGATIVE"]
    recognized, late = [], []
    false = []
    for c in real:
        fires = [x for x in c["candidates"] if x["score"] >= threshold]
        if not fires:
            continue
        fire = min(fires, key=lambda x: x["time"])
        if fire["time"] <= c["event_time"]:
            recognized.append((c, fire))
        else:
            late.append((c, fire))
    for c in neg:
        if any(x["score"] >= threshold for x in c["candidates"]):
            false.append(c)

    leads = [(c["event_time"] - f["time"]).total_seconds() / 60.0 for c, f in recognized]
    fires_total = len(recognized) + len(late) + len(false)
    print(f"{label} threshold={threshold}")
    print(f"  REAL events={len(real)} | NEGATIVE opportunities={len(neg)}")
    print(f"  recognized_before={pct(len(recognized), len(real)):.1f}% | late={pct(len(late), len(real)):.1f}% | missed={pct(len(real)-len(recognized)-len(late), len(real)):.1f}%")
    print(f"  false_alarm_rate={pct(len(false), len(neg)):.1f}%")
    print(f"  precision_of_fires={pct(len(recognized), fires_total):.1f}%")
    if leads:
        print(f"  lead_minutes mean={mean(leads):.1f} median={median(leads):.1f} | within5={pct(sum(x <= 5 for x in leads), len(leads)):.1f}% | within15={pct(sum(x <= 15 for x in leads), len(leads)):.1f}%")
    else:
        print("  lead_minutes n/a")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("symbols", nargs="*", default=DEFAULT_SYMBOLS)
    ap.add_argument("--limit", type=int, default=10000)
    args = ap.parse_args()

    print("KISS TRANSITION DETECTOR V2 — EXACT EVENT TIMING")
    print("Research only — NO strategy/engine changes, NO orders, NO DB writes")
    print(f"Symbols: {', '.join(args.symbols)}")
    print("30m timestamp model: candle START; state known at candle CLOSE (+30m)")
    print("5m observation model: candle START; feature available at candle CLOSE (+5m)")
    print(f"Positive lookback: {LOOKBACK_MINUTES}m | Negative horizon: {NEGATIVE_HORIZON_MINUTES}m")
    print("Features: same V1 evidence; only the evaluation timing is corrected")

    cases: List[Dict[str, Any]] = []
    for symbol in args.symbols:
        try:
            r30 = load(symbol, "30m", args.limit)
            r5 = load(symbol, "5m", args.limit)
            pos = build_positive_cases(r30, r5, symbol)
            neg = build_negative_cases(r30, r5, symbol)
            cases.extend(pos)
            cases.extend(neg)
            print(f"{symbol}: 30m={len(r30)} 5m={len(r5)} REAL={len(pos)} NEGATIVE={len(neg)}")
        except Exception as exc:
            print(f"{symbol}: ERROR: {exc}")

    discovery, holdout = split_cases(cases)
    print(f"TOTAL cases: {len(cases)} | DISCOVERY: {len(discovery)} | HOLDOUT: {len(holdout)}")

    for name, data in (("FULL", cases), ("DISCOVERY", discovery), ("HOLDOUT", holdout)):
        print("=" * 72)
        print(name)
        print("=" * 72)
        for threshold in SCORE_THRESHOLDS:
            evaluate(data, threshold, name)

    print("=" * 72)
    print("INTERPRETATION")
    print("=" * 72)
    print("This run is a measurement correction, not a production rule.")
    print("The key target is high real-transition recognition before the exact")
    print("30m close, preferably within 5–15 minutes, with manageable false alarms.")
    print("If the frontier is still poor, the next experiment will improve the")
    print("transition-sequence detector rather than changing KISS execution.")


if __name__ == "__main__":
    main()
