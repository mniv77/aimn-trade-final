"""KISS V5.6.10.1 — safe output for V5.6.10.

RESEARCH ONLY.
No orders. No DB writes. No KISS engine changes. No RSI. No ML.

This file fixes ONLY the representative-output crash in V5.6.10.
The V5.6.10 analysis, candidate detection, policies, scoring, and statistics
are left unchanged. Missing display values are printed as N/A instead of being
inserted into the numeric calculations.
"""
from __future__ import annotations

import kiss_transition_detector_v5_6_10_decision_point_test as v5610


def _fmt_number(value, spec: str = "+.3f") -> str:
    """Format a numeric display value without modifying the source record."""
    if value is None:
        return "N/A"
    try:
        return format(value, spec)
    except (TypeError, ValueError):
        return "N/A"


def _fmt_time(value) -> str:
    return "N/A" if value is None else str(value)


def safe_summarize(records, total, skipped):
    """Exact V5.6.10 summary logic with safe representative formatting.

    Important: do not mutate records. Therefore None values remain excluded
    from the original statistics exactly as V5.6.10 intended.
    """
    print("\n================ V5.6.10 SUMMARY ================")
    print(f"TOTAL KNOWN TRANSITIONS: {total}")
    print(f"USABLE COMPLETE V5.6.10 WINDOWS: {len(records)}")
    print(f"SKIPPED FOR INSUFFICIENT 5M COVERAGE: {skipped}")

    all_eps = []
    for rec in records:
        all_eps.extend(rec["result"]["episodes"])

    print(f"FIRST-WARNING EPISODES: {len(all_eps)}")
    print(f"DECISION DELAYS: {v5610.DECISION_DELAYS} minutes")
    print(f"EPISODE GAP RULE: <= {v5610.EPISODE_GAP_MINUTES} MINUTES")
    print("SCORING: GOOD_EXIT if HOLD-60 <= -0.10%, FALSE_EXIT if HOLD-60 >= +0.10%")

    for direction in ("LONG->SHORT", "SHORT->LONG", "ALL"):
        selected = all_eps if direction == "ALL" else [
            e
            for rec in records
            if rec["direction"] == direction
            for e in rec["result"]["episodes"]
        ]

        print(f"\n{direction} CAUSAL DECISION-POINT TEST")
        print(f"EPISODES: {len(selected)}")

        for delay in v5610.DECISION_DELAYS:
            acted = [
                e["policies"][delay]
                for e in selected
                if e["policies"][delay]["acted"]
            ]
            good = [r for r in acted if r["status"] == "GOOD_EXIT"]
            false = [r for r in acted if r["status"] == "FALSE_EXIT"]
            neutral = [r for r in acted if r["status"] == "NEUTRAL"]
            valid = [r for r in acted if r["ret60"] is not None]

            avg_hold = v5610.avg([r["ret60"] for r in valid])
            print(
                f"  WAIT_{delay:02d}M: ACTED={len(acted)} VALID={len(valid)} "
                f"GOOD={len(good)} ({v5610.pct(len(good), len(valid)):.1f}%) "
                f"FALSE={len(false)} ({v5610.pct(len(false), len(valid)):.1f}%) "
                f"NEUTRAL={len(neutral)} "
                f"AVG_HOLD60={avg_hold:+.3f}%"
            )

            acted_times = [
                r["minutes_to_t0"]
                for r in acted
                if r["minutes_to_t0"] is not None
            ]
            if acted_times:
                print(f"             AVG MINUTES TO T0: {v5610.avg(acted_times):+.1f}")

    print("\nV5.6.10 REPRESENTATIVE DECISION CASES")
    shown = 0

    for rec in records:
        for e in rec["result"]["episodes"]:
            if shown >= 12:
                break

            f = e["first"]
            first_time = f["time"]
            event_time = rec["event"]["time"]
            delta_minutes = (event_time - first_time).total_seconds() / 60.0

            print(
                f"{rec['symbol']} {rec['direction']} FIRST {first_time} "
                f"T0={event_time} ({delta_minutes:+.0f}m) "
                f"reason={f['reason']} score={f['score']:.2f}"
            )

            for delay in v5610.DECISION_DELAYS:
                r = e["policies"][delay]
                if r["acted"]:
                    minutes = r["minutes_to_t0"]
                    ret60 = r["ret60"]
                    minutes_text = "N/A" if minutes is None else f"{minutes:+.0f}"
                    ret60_text = _fmt_number(ret60, "+.3f")
                    print(
                        f"  WAIT_{delay:02d}M -> {_fmt_time(r['time'])} "
                        f"({minutes_text}m to T0) {r['status']} "
                        f"hold60={ret60_text}%"
                    )
                else:
                    print(f"  WAIT_{delay:02d}M -> NO_EXIT")

            shown += 1

        if shown >= 12:
            break

    print("\nV5.6.10 KEY TEST")
    print("FIRST WARNING is a NOTICE, not automatically an EXIT.")
    print("Every WAIT policy makes its decision using only completed 5m information available at that point.")
    print("Future candles are used only after the causal decision to score exit-vs-hold.")
    print("The goal is to identify a useful causal decision delay, not to predict the 30m MA transition.")
    print("V5.6.10 is research only — no trading rule or engine change.")


v5610.summarize = safe_summarize

if __name__ == "__main__":
    v5610.main()
