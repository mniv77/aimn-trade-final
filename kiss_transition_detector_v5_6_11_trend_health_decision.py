"""KISS V5.6.11 — Causal Trend Health Decision Test.

RESEARCH ONLY.
No orders. No DB writes. No KISS engine changes. No RSI. No ML.

V5.6.10 showed that a fixed WAIT time is not the answer. V5.6.11 asks the
next question:

    After FIRST WARNING, is the old trend still healthy, weakening, or has
    the trade thesis actually failed?

The decision is made from completed 5m candles only. Future candles are used
ONLY afterward to score exit-vs-hold.

Decision states:
    HEALTHY       -> HOLD
    WEAKENING     -> HOLD / continue observing
    THESIS_FAILED -> EXIT CANDIDATE

Opposite-direction development is deliberately NOT used to decide the exit.
That remains a separate future research problem.

This version is deliberately simple and transparent. The thresholds are a
research probe, not a production trading rule.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
from typing import Any, Dict, List, Optional

import kiss_transition_detector_v5_6_10_decision_point_test as v5610


# Same causal/coverage framework as V5.6.10.
DECISION_DELAYS = (0, 15, 30, 45, 60)
LOOKBACK_MINUTES = v5610.LOOKBACK_MINUTES
MIN_HISTORY_MINUTES = v5610.MIN_HISTORY_MINUTES
POST_MINUTES = v5610.POST_MINUTES
EVAL_MINUTES = v5610.EVAL_MINUTES
EXIT_BUFFER = v5610.EXIT_BUFFER
EPISODE_GAP_MINUTES = v5610.EPISODE_GAP_MINUTES
DEFAULT_SYMBOLS = v5610.DEFAULT_SYMBOLS


def health_state(rows: List[Dict[str, Any]], idx: int, prior: str) -> Dict[str, Any]:
    """Classify current old-trend health using only data through idx."""
    h = v5610.health(rows, idx, prior)
    structural, structure_reason = v5610.structure_break(rows, idx, prior)

    # Transparent causal research thresholds.
    thesis_failed = (
        structural
        or h["consecutive"] >= 3
        or h["net"] <= -0.50
        or (h["adverse"] >= 7 and h["net"] <= -0.30)
    )

    weakening = (
        h["consecutive"] >= 1
        or h["adverse"] >= 3
        or h["net"] <= -0.10
    )

    if thesis_failed:
        state = "THESIS_FAILED"
    elif weakening:
        state = "WEAKENING"
    else:
        state = "HEALTHY"

    return {
        "state": state,
        "adverse": h["adverse"],
        "consecutive": h["consecutive"],
        "net": h["net"],
        "structural": structural,
        "structure_reason": structure_reason,
    }


def nearest_decision_idx(rows: List[Dict[str, Any]], warning_idx: int, delay: int) -> Optional[int]:
    target = v5610.close_time(rows[warning_idx]) + timedelta(minutes=delay)
    idx, _ = v5610.nearest_completed_close(rows, target)
    if idx is None or idx < warning_idx:
        return None
    return idx


def evaluate_policy(rows: List[Dict[str, Any]], warning_idx: int, prior: str, delay: int) -> Dict[str, Any]:
    idx = nearest_decision_idx(rows, warning_idx, delay)
    if idx is None:
        return {
            "acted": False,
            "idx": None,
            "time": None,
            "state": "NO_DATA",
            "status": "NO_EXIT",
            "ret60": None,
            "minutes_to_t0": None,
            "health": None,
        }

    health = health_state(rows, idx, prior)
    acted = health["state"] == "THESIS_FAILED"

    result: Dict[str, Any] = {
        "acted": acted,
        "idx": idx,
        "time": v5610.close_time(rows[idx]),
        "state": health["state"],
        "status": "NO_EXIT",
        "ret60": None,
        "minutes_to_t0": None,
        "health": health,
    }

    if acted:
        scored = v5610.score_exit_vs_hold(rows, idx, prior)
        result["status"] = scored["status"]
        result["ret60"] = scored["ret60"]
        result["minutes_to_t0"] = (
            v5610.close_time(rows[idx])
        )

    return result


def run_case(rows: List[Dict[str, Any]], event: Dict[str, Any]) -> Dict[str, Any]:
    t0 = event["time"]
    prior = event["from"]

    requested_start = t0 - timedelta(minutes=LOOKBACK_MINUTES)
    start, start_diff = v5610.nearest_completed_close(rows, requested_start)
    if start is None:
        return {"usable": False}

    end, end_diff = v5610.nearest_completed_close(
        rows, t0 + timedelta(minutes=POST_MINUTES)
    )
    if end is None or end <= start:
        return {"usable": False}

    available_history = (t0 - v5610.close_time(rows[start])).total_seconds() / 60.0
    if available_history < MIN_HISTORY_MINUTES:
        return {"usable": False}

    # Same causal candidate discovery as V5.6.10. No future information.
    candidates: List[Dict[str, Any]] = []
    for idx in range(start, end + 1):
        ok, reason, score = v5610.candidate_signal(rows, idx, prior)
        if ok:
            candidates.append({
                "idx": idx,
                "time": v5610.close_time(rows[idx]),
                "reason": reason,
                "score": score,
            })

    episodes: List[List[Dict[str, Any]]] = []
    for c in candidates:
        if not episodes:
            episodes.append([c])
            continue
        gap = (c["time"] - episodes[-1][-1]["time"]).total_seconds() / 60.0
        if gap <= EPISODE_GAP_MINUTES:
            episodes[-1].append(c)
        else:
            episodes.append([c])

    results: List[Dict[str, Any]] = []
    for ep in episodes:
        first = min(ep, key=lambda x: x["time"])
        policies: Dict[int, Dict[str, Any]] = {}
        for delay in DECISION_DELAYS:
            r = evaluate_policy(rows, first["idx"], prior, delay)
            if r["acted"]:
                r["minutes_to_t0"] = (
                    t0 - r["time"]
                ).total_seconds() / 60.0
            policies[delay] = r
        results.append({"first": first, "policies": policies})

    return {
        "usable": True,
        "requested_start": requested_start,
        "actual_start": v5610.close_time(rows[start]),
        "start_offset": start_diff,
        "actual_end": v5610.close_time(rows[end]),
        "end_offset": end_diff,
        "available_history": available_history,
        "episodes": results,
    }


def load_records(symbols: List[str]):
    records = []
    total = 0
    skipped = 0
    for symbol in symbols:
        rows = v5610.load(symbol, "5m", 50000)
        if not rows:
            continue
        events = v5610.transitions(rows)
        total += len(events)
        for event in events:
            result = run_case(rows, event)
            if not result.get("usable"):
                skipped += 1
                continue
            records.append({"symbol": symbol, "direction": f"{event['from']}->{event['to']}", "event": event, "result": result})
    return records, total, skipped


def pct(n: int, d: int) -> float:
    return 100.0 * n / d if d else 0.0


def avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(records, total, skipped):
    print("\n================ V5.6.11 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.11 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INSUFFICIENT 5M COVERAGE: {skipped}")
    print(f"FIRST-WARNING EPISODES: {sum(len(r['result']['episodes']) for r in records)}")
    print(f"DECISION DELAYS TESTED: {DECISION_DELAYS} minutes")
    print(f"EPISODE GAP RULE: <= {EPISODE_GAP_MINUTES} MINUTES")
    print("CAUSAL STATES: HEALTHY -> WEAKENING -> THESIS_FAILED")
    print("ACTION: EXIT CANDIDATE only when current causal state is THESIS_FAILED")
    print("SCORING: GOOD_EXIT if HOLD-60 <= -0.10%, FALSE_EXIT if HOLD-60 >= +0.10%")

    all_eps = [e for rec in records for e in rec["result"]["episodes"]]

    for direction in ("LONG->SHORT", "SHORT->LONG", "ALL"):
        selected = all_eps if direction == "ALL" else [
            e for rec in records if rec["direction"] == direction for e in rec["result"]["episodes"]
        ]
        print(f"\n{direction} TREND-HEALTH DECISION TEST")
        print(f"EPISODES: {len(selected)}")
        for delay in DECISION_DELAYS:
            acted = [e["policies"][delay] for e in selected if e["policies"][delay]["acted"]]
            good = [r for r in acted if r["status"] == "GOOD_EXIT"]
            false = [r for r in acted if r["status"] == "FALSE_EXIT"]
            neutral = [r for r in acted if r["status"] == "NEUTRAL"]
            valid = [r for r in acted if r["ret60"] is not None]
            holds = [r["ret60"] for r in valid]
            print(
                f"  WAIT_{delay:02d}M: ACTED={len(acted)} VALID={len(valid)} "
                f"GOOD={len(good)} ({pct(len(good),len(valid)):.1f}%) "
                f"FALSE={len(false)} ({pct(len(false),len(valid)):.1f}%) "
                f"NEUTRAL={len(neutral)} AVG_HOLD60={avg(holds):+.3f}%"
            )

    # State distribution at the first warning is useful for seeing whether the
    # warning itself is merely pressure or already a thesis failure.
    print("\nFIRST-WARNING STATE DISTRIBUTION")
    for direction in ("LONG->SHORT", "SHORT->LONG", "ALL"):
        selected = all_eps if direction == "ALL" else [
            e for rec in records if rec["direction"] == direction for e in rec["result"]["episodes"]
        ]
        states = []
        for e in selected:
            h = e["policies"][0]["health"]
            states.append(h["state"] if h else "NO_DATA")
        print(
            f"  {direction}: HEALTHY={states.count('HEALTHY')} "
            f"WEAKENING={states.count('WEAKENING')} "
            f"THESIS_FAILED={states.count('THESIS_FAILED')}"
        )

    print("\nV5.6.11 REPRESENTATIVE DECISION CASES")
    shown = 0
    for rec in records:
        for e in rec["result"]["episodes"]:
            if shown >= 12:
                break
            f = e["first"]
            t0 = rec["event"]["time"]
            delta = (t0 - f["time"]).total_seconds() / 60.0
            print(
                f"{rec['symbol']} {rec['direction']} FIRST {f['time']} "
                f"T0={t0} ({delta:+.0f}m) reason={f['reason']} score={f['score']:.2f}"
            )
            for delay in DECISION_DELAYS:
                r = e["policies"][delay]
                h = r["health"]
                state = h["state"] if h else "NO_DATA"
                net = h["net"] if h else None
                if r["acted"]:
                    ret = "N/A" if r["ret60"] is None else f"{r['ret60']:+.3f}%"
                    mt = "N/A" if r["minutes_to_t0"] is None else f"{r['minutes_to_t0']:+.0f}m"
                    print(f"  WAIT_{delay:02d}M -> {r['time']} {state} EXIT {r['status']} hold60={ret} ({mt})")
                else:
                    net_text = "N/A" if net is None else f"{net:+.3f}%"
                    print(f"  WAIT_{delay:02d}M -> {r['time']} {state} HOLD net={net_text}")
            shown += 1
        if shown >= 12:
            break

    print("\nV5.6.11 KEY TEST")
    print("FIRST WARNING is still a NOTICE.")
    print("The decision point is driven by CURRENT TREND HEALTH, not a fixed timer.")
    print("THESIS_FAILED is an EXIT CANDIDATE only; opposite-direction entry remains separate.")
    print("Future candles are used only after each causal decision to score exit-vs-hold.")
    print("V5.6.11 is research only — no trading rule or engine change.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    args = parser.parse_args()
    records, total, skipped = load_records(args.symbols)
    summarize(records, total, skipped)


if __name__ == "__main__":
    main()
