#!/usr/bin/env python3
"""
AIMn KISS — Experiment #48
UNPROFITABLE V: IMMEDIATE POST-V BEHAVIOR

RESEARCH ONLY
-------------
No production strategy changes.
No orders.
No AI training.
No threshold promotion.
No re-entry simulation.

QUESTION
--------
At an unprofitable V:

    Is price merely making noise?

or

    Is the reversal continuing against the trade?

This experiment starts ONLY from the five qualifying #46
not-yet-profitable V events and attaches the real raw 5-minute
trajectory immediately after the exact causal V-reversal candle.

IMPORTANT
---------
The #46 event file does NOT use "event_time_utc".

Its causal V timestamp is:

    v_reversal_candle_utc

That is the field used here.

RAW SOURCE
----------
kiss/results/exp32_raw_candle_v_geometry/raw_v_trajectory.csv

For each #46 event we calculate P&L directly from:

    entry_price
    direction
    raw 5-minute close

Then we inspect the next 12 completed 5-minute candles:

    V -> +5m -> +10m -> ... -> +60m

A = adverse P&L change
F = favorable P&L change
Z = unchanged

This is descriptive research only.
"""

from __future__ import annotations

from pathlib import Path
import math
import sys

import pandas as pd


ROOT = Path.home() / "aimn-trade-final"
RESULTS = ROOT / "kiss" / "results"
OUT = RESULTS / "exp48_unprofitable_v_streaks"
OUT.mkdir(parents=True, exist_ok=True)

EVENT_PATH = (
    RESULTS
    / "exp46_not_yet_profitable_v"
    / "nvda_not_yet_profitable_v_events.csv"
)

RAW_PATH = (
    RESULTS
    / "exp32_raw_candle_v_geometry"
    / "raw_v_trajectory.csv"
)


def die(message: str) -> None:
    print("=" * 100)
    print("ERROR")
    print("=" * 100)
    print(message)
    sys.exit(1)


def utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def get_first_existing_column(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    die(
        f"{label} is missing.\n"
        f"Tried: {candidates}\n"
        f"Actual columns: {list(df.columns)}"
    )


def pnl_from_close(direction: str, entry_price: float, close_price: float) -> float:
    if (
        not math.isfinite(entry_price)
        or entry_price == 0
        or not math.isfinite(close_price)
    ):
        return float("nan")

    d = direction.upper()

    if d == "LONG":
        return (close_price - entry_price) / entry_price * 100.0

    if d == "SHORT":
        return (entry_price - close_price) / entry_price * 100.0

    return float("nan")


def sign_code(value: float) -> str:
    if pd.isna(value):
        return "?"
    if value < 0:
        return "A"
    if value > 0:
        return "F"
    return "Z"


def starting_streak(codes: list[str], wanted: str) -> int:
    count = 0
    for code in codes:
        if code != wanted:
            break
        count += 1
    return count


def classify_first_three(codes: list[str]) -> str:
    """
    Descriptive label only.

    We do NOT promote this to a rule.

    CONTINUING_REVERSAL:
        first three post-V P&L changes are all adverse.

    IMMEDIATE_RECOVERY:
        first three are all favorable.

    NOISE_THEN_RECOVERY:
        starts adverse, then turns favorable within first three.

    REVERSAL_THEN_BOUNCE:
        starts favorable, then turns adverse within first three.

    MIXED:
        anything else / insufficient pattern.
    """
    if len(codes) < 3 or any(c == "?" for c in codes[:3]):
        return "INSUFFICIENT"

    first3 = codes[:3]

    if first3 == ["A", "A", "A"]:
        return "CONTINUING_REVERSAL"

    if first3 == ["F", "F", "F"]:
        return "IMMEDIATE_RECOVERY"

    if first3[0] == "A" and "F" in first3:
        return "NOISE_THEN_RECOVERY"

    if first3[0] == "F" and "A" in first3:
        return "REVERSAL_THEN_BOUNCE"

    return "MIXED"


def main() -> None:
    if not EVENT_PATH.exists():
        die(f"#46 event file does not exist:\n{EVENT_PATH}")

    if not RAW_PATH.exists():
        die(f"Raw 5-minute trajectory does not exist:\n{RAW_PATH}")

    events = pd.read_csv(EVENT_PATH)
    raw = pd.read_csv(RAW_PATH)

    print("=" * 100)
    print("AIMn KISS — EXPERIMENT #48")
    print("UNPROFITABLE V: IMMEDIATE POST-V BEHAVIOR")
    print("=" * 100)
    print("Research only. No production changes. No orders. No AI.")
    print("No threshold promotion. No re-entry simulation.")
    print()

    print("#46 EVENT SOURCE")
    print(f"Selected: {EVENT_PATH}")
    print(f"Rows:     {len(events):,}")
    print(f"Columns:  {list(events.columns)}")
    print()

    print("RAW 5-MINUTE SOURCE")
    print(f"Selected: {RAW_PATH}")
    print(f"Rows:     {len(raw):,}")
    print(f"Columns:  {list(raw.columns)}")
    print("=" * 100)

    # ------------------------------------------------------------------
    # Exact column names from the REAL #46 event file.
    # Prefer the causal V reversal timestamp.
    # ------------------------------------------------------------------
    event_time_col = get_first_existing_column(
        events,
        [
            "v_reversal_candle_utc",
            "event_time_utc",
            "event_time",
            "v_reversal_time_utc",
        ],
        "The #46 causal V timestamp",
    )

    event_pnl_col = get_first_existing_column(
        events,
        [
            "exit_now_pnl_pct",
            "pnl_at_v_pct",
        ],
        "#46 EXIT NOW P&L",
    )

    stay_pnl_col = get_first_existing_column(
        events,
        [
            "stay_actual_pnl_pct",
            "eventual_pnl_hindsight_pct",
        ],
        "#46 STAY P&L",
    )

    required_event = {"case_id", "trade_id", "direction", "entry_price"}
    missing_event = required_event - set(events.columns)
    if missing_event:
        die(
            "#46 event file is missing required columns:\n"
            + "\n".join(f"  {x}" for x in sorted(missing_event))
        )

    required_raw = {
        "case_id",
        "symbol",
        "direction",
        "transition_known_utc",
        "candle_utc",
        "close",
    }
    missing_raw = required_raw - set(raw.columns)
    if missing_raw:
        die(
            "RAW trajectory is missing required columns:\n"
            + "\n".join(f"  {x}" for x in sorted(missing_raw))
        )

    events = events.copy()
    raw = raw.copy()

    events["causal_v_time_utc"] = utc(events[event_time_col])
    raw["candle_utc"] = utc(raw["candle_utc"])
    raw["transition_known_utc"] = utc(raw["transition_known_utc"])

    if events["causal_v_time_utc"].isna().any():
        die(f"Some #46 timestamps in '{event_time_col}' could not be parsed as UTC.")

    if raw["candle_utc"].isna().any():
        die("Some raw candle timestamps could not be parsed as UTC.")

    # #46 already selected the qualifying events.
    # Keep the existing 0.0000% test definition:
    # not-yet-profitable means EXIT NOW P&L <= 0.
    events["exit_now_pnl_num"] = pd.to_numeric(
        events[event_pnl_col], errors="coerce"
    )
    events = events[events["exit_now_pnl_num"] <= 0.0].copy()

    # Keep the NVDA sample used by #46.
    if "symbol" in events.columns:
        nvda = events[
            events["symbol"].astype(str).str.upper().eq("NVDA")
        ].copy()
        if not nvda.empty:
            events = nvda

    if events.empty:
        die("No #46 unprofitable V events remain at the existing 0.0000% level.")

    raw = raw.sort_values(["case_id", "candle_utc"]).reset_index(drop=True)

    output_rows: list[dict] = []
    unmatched: list[tuple[str, str]] = []

    for _, ev in events.sort_values(["causal_v_time_utc", "case_id"]).iterrows():
        case_id = str(ev["case_id"])
        trade_id = str(ev["trade_id"])
        direction = str(ev["direction"]).upper()

        event_time = ev["causal_v_time_utc"]
        entry_price = pd.to_numeric(ev["entry_price"], errors="coerce")
        entry_price = float(entry_price) if pd.notna(entry_price) else float("nan")

        exit_now = pd.to_numeric(ev[event_pnl_col], errors="coerce")
        exit_now = float(exit_now) if pd.notna(exit_now) else float("nan")

        stay_actual = pd.to_numeric(ev[stay_pnl_col], errors="coerce")
        stay_actual = (
            float(stay_actual) if pd.notna(stay_actual) else float("nan")
        )

        case_raw = raw[
            raw["case_id"].astype(str).eq(case_id)
        ].copy()

        if case_raw.empty:
            unmatched.append((case_id, "case_id not found in raw trajectory"))
            continue

        case_raw = case_raw.sort_values("candle_utc").copy()

        # Exact completed candle where the V reversal became known.
        exact = case_raw[
            case_raw["candle_utc"].eq(event_time)
        ]

        if exact.empty:
            # Do not silently move the event by more than one 5-minute candle.
            case_raw["delta_sec"] = (
                case_raw["candle_utc"] - event_time
            ).abs().dt.total_seconds()

            nearest = case_raw[
                case_raw["delta_sec"] <= 300
            ].sort_values("delta_sec")

            if nearest.empty:
                unmatched.append(
                    (case_id, "causal V candle not found exactly or within 5m")
                )
                continue

            event_row = nearest.iloc[0]
            alignment = "NEAREST_WITHIN_5M"
        else:
            event_row = exact.iloc[-1]
            alignment = "EXACT"

        event_candle_time = event_row["candle_utc"]
        event_close = float(event_row["close"])

        event_raw_pnl = pnl_from_close(
            direction,
            entry_price,
            event_close,
        )

        if not math.isfinite(event_raw_pnl):
            unmatched.append((case_id, "could not calculate V P&L"))
            continue

        # ONLY completed candles after the causal V candle.
        post = case_raw[
            case_raw["candle_utc"] > event_candle_time
        ].copy()

        if post.empty:
            unmatched.append((case_id, "no post-V candles"))
            continue

        post["pnl_pct"] = post["close"].astype(float).map(
            lambda px: pnl_from_close(direction, entry_price, float(px))
        )

        post["d_pnl_pct"] = post["pnl_pct"].diff()
        post.loc[post.index[0], "d_pnl_pct"] = (
            post.iloc[0]["pnl_pct"] - event_raw_pnl
        )

        post["code"] = post["d_pnl_pct"].map(sign_code)

        first = post.head(12).copy()
        codes = first["code"].tolist()
        first3 = codes[:3]

        rec = {
            "case_id": case_id,
            "trade_id": trade_id,
            "symbol": str(ev.get("symbol", "NVDA")),
            "direction": direction,
            "causal_v_time_utc": event_time.isoformat(),
            "aligned_raw_candle_utc": event_candle_time.isoformat(),
            "alignment": alignment,
            "entry_price": entry_price,
            "exit_now_pnl_pct": exit_now,
            "raw_pnl_at_v_pct": event_raw_pnl,
            "stay_actual_pnl_pct": stay_actual,
            "stay_minus_exit_pct": stay_actual - exit_now,
            "first_3_behavior": classify_first_three(first3),
            "first_adverse_streak": starting_streak(codes, "A"),
            "first_favorable_streak": starting_streak(codes, "F"),
            "post_v_candles_available": int(len(post)),
            "min_pnl_after_v_pct": float(post["pnl_pct"].min()),
            "max_pnl_after_v_pct": float(post["pnl_pct"].max()),
        }

        # Standard checkpoints.
        for minutes in (5, 10, 15, 20, 30, 45, 60):
            n = minutes // 5

            if len(post) >= n:
                value = float(post.iloc[n - 1]["pnl_pct"])
                change = value - event_raw_pnl

                rec[f"pnl_after_{minutes}m_pct"] = value
                rec[f"change_from_v_after_{minutes}m_pct"] = change
                rec[f"sign_after_{minutes}m"] = sign_code(change)
            else:
                rec[f"pnl_after_{minutes}m_pct"] = float("nan")
                rec[f"change_from_v_after_{minutes}m_pct"] = float("nan")
                rec[f"sign_after_{minutes}m"] = "?"

        # Save the first 12 post-V candles exactly for audit.
        for i, (_, row) in enumerate(first.iterrows(), start=1):
            rec[f"candle_{i}_time_utc"] = row["candle_utc"].isoformat()
            rec[f"candle_{i}_close"] = float(row["close"])
            rec[f"candle_{i}_d_pnl_pct"] = float(row["d_pnl_pct"])
            rec[f"candle_{i}_code"] = row["code"]

        rec["sequence_12_candles_60m"] = "".join(codes)

        output_rows.append(rec)

    result = pd.DataFrame(output_rows)

    if result.empty:
        die("No #46 events could be attached to the raw 5-minute trajectory.")

    event_out = OUT / "nvda_unprofitable_v_post_v_streaks.csv"
    summary_out = OUT / "nvda_unprofitable_v_post_v_streaks_summary.csv"
    metadata_out = OUT / "exp48_metadata.txt"

    result.to_csv(event_out, index=False)

    summary = pd.DataFrame(
        [
            {
                "events_analyzed": len(result),
                "unique_trades": int(result["trade_id"].nunique()),
                "exact_alignment": int(
                    (result["alignment"] == "EXACT").sum()
                ),
                "nearest_within_5m": int(
                    (result["alignment"] != "EXACT").sum()
                ),
                "avg_exit_now_pnl_pct": result["exit_now_pnl_pct"].mean(),
                "avg_stay_actual_pnl_pct": result["stay_actual_pnl_pct"].mean(),
                "avg_stay_minus_exit_pct": result["stay_minus_exit_pct"].mean(),
                "stay_better_count": int(
                    (result["stay_minus_exit_pct"] > 0).sum()
                ),
                "exit_better_count": int(
                    (result["stay_minus_exit_pct"] < 0).sum()
                ),
                "same_count": int(
                    (result["stay_minus_exit_pct"] == 0).sum()
                ),
            }
        ]
    )

    summary.to_csv(summary_out, index=False)

    behavior_summary = (
        result.groupby("first_3_behavior", dropna=False)
        .agg(
            events=("trade_id", "size"),
            unique_trades=("trade_id", "nunique"),
            avg_exit_now_pct=("exit_now_pnl_pct", "mean"),
            avg_stay_pct=("stay_actual_pnl_pct", "mean"),
            avg_stay_minus_exit_pct=("stay_minus_exit_pct", "mean"),
            stay_better=("stay_minus_exit_pct", lambda s: int((s > 0).sum())),
            exit_better=("stay_minus_exit_pct", lambda s: int((s < 0).sum())),
            same=("stay_minus_exit_pct", lambda s: int((s == 0).sum())),
        )
        .reset_index()
    )

    behavior_out = OUT / "nvda_unprofitable_v_behavior_summary.csv"
    behavior_summary.to_csv(behavior_out, index=False)

    with metadata_out.open("w", encoding="utf-8") as f:
        f.write("AIMn KISS — Experiment #48\n")
        f.write("UNPROFITABLE V: IMMEDIATE POST-V BEHAVIOR\n\n")
        f.write("RESEARCH ONLY\n")
        f.write("No production strategy changes.\n")
        f.write("No orders.\n")
        f.write("No AI training.\n")
        f.write("No threshold promotion.\n")
        f.write("No re-entry simulation.\n\n")
        f.write(f"#46 event source: {EVENT_PATH}\n")
        f.write(f"#46 causal timestamp column used: {event_time_col}\n")
        f.write(f"Raw trajectory source: {RAW_PATH}\n")
        f.write(f"Events supplied by #46 after <= 0% filter: {len(events)}\n")
        f.write(f"Events attached to raw trajectory: {len(result)}\n")
        f.write("A = adverse 5m P&L change.\n")
        f.write("F = favorable 5m P&L change.\n")
        f.write("Z = unchanged 5m P&L change.\n")
        f.write("All behavior labels are descriptive research only.\n")

    print()
    print("=" * 100)
    print("CORE RESULT")
    print("=" * 100)
    print(f"#46 unprofitable V events supplied : {len(events)}")
    print(f"Events attached to raw trajectory  : {len(result)}")
    print(
        f"Exact causal candle alignment      : "
        f"{(result['alignment'] == 'EXACT').sum()}"
    )
    print(
        f"Nearest-within-5m alignment         : "
        f"{(result['alignment'] != 'EXACT').sum()}"
    )
    print()

    print(
        f"Average EXIT NOW P&L                : "
        f"{result['exit_now_pnl_pct'].mean():.4f}%"
    )
    print(
        f"Average STAY actual P&L             : "
        f"{result['stay_actual_pnl_pct'].mean():.4f}%"
    )
    print(
        f"Average STAY minus EXIT             : "
        f"{result['stay_minus_exit_pct'].mean():.4f}%"
    )
    print(
        f"STAY better                          : "
        f"{(result['stay_minus_exit_pct'] > 0).sum()}"
    )
    print(
        f"EXIT better                          : "
        f"{(result['stay_minus_exit_pct'] < 0).sum()}"
    )
    print(
        f"Same                                 : "
        f"{(result['stay_minus_exit_pct'] == 0).sum()}"
    )
    print()

    print("IMMEDIATE POST-V BEHAVIOR")
    print(
        result[
            [
                "trade_id",
                "direction",
                "sequence_12_candles_60m",
                "first_3_behavior",
                "first_adverse_streak",
                "first_favorable_streak",
                "exit_now_pnl_pct",
                "stay_actual_pnl_pct",
                "stay_minus_exit_pct",
            ]
        ].to_string(index=False)
    )

    print()
    print("BEHAVIOR SUMMARY")
    print(behavior_summary.to_string(index=False))

    if unmatched:
        print()
        print("UNMATCHED EVENTS")
        for case_id, reason in unmatched:
            print(f"  {case_id}: {reason}")

    print()
    print("OUTPUTS")
    print(f"Events  : {event_out}")
    print(f"Summary : {summary_out}")
    print(f"Behavior: {behavior_out}")
    print(f"Meta    : {metadata_out}")


if __name__ == "__main__":
    main()
