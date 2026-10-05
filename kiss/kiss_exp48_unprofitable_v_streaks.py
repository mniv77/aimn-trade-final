#!/usr/bin/env python3
"""
AIMn KISS — Experiment #48
UNPROFITABLE V: WHAT HAPPENS IMMEDIATELY AFTER THE V?

RESEARCH ONLY
-------------
No production strategy changes.
No orders.
No AI training.
No threshold promotion.
No re-entry simulation.

QUESTION
--------
At an unprofitable V, is the price merely making noise,
or is the reversal continuing against the trade?

IMPORTANT
---------
Experiment #46 already identified the qualifying unprofitable V events.
Therefore #48 deliberately STARTS FROM THE #46 EVENT FILE.
It does NOT try to rediscover the events from the larger #42 file.

For each #46 event, we attach the raw 5-minute candles immediately after
that exact causal V candle and report the observed P&L-change sequence:

    V -> A -> F -> F
    V -> A -> Z -> F
    V -> A -> A -> A

A = adverse P&L change from the prior 5-minute candle
F = favorable P&L change
Z = unchanged / numerically flat

No percentage threshold is used to define A/F/Z; only the sign of the
5-minute P&L change is recorded.
"""

from __future__ import annotations

from pathlib import Path
import glob
import math
import sys

import pandas as pd

ROOT = Path.home() / "aimn-trade-final"
KISS = ROOT / "kiss"
RESULTS = KISS / "results"
OUT = RESULTS / "exp48_unprofitable_v_streaks"
OUT.mkdir(parents=True, exist_ok=True)

EVENT_CANDIDATES = [
    RESULTS / "exp46_not_yet_profitable_v" / "nvda_not_yet_profitable_v_events.csv",
]

RAW_CANDIDATES = [
    RESULTS / "exp32_raw_candle_v_geometry" / "raw_v_trajectory.csv",
    RESULTS / "exp37_nvda_causal" / "nvda_causal_path.csv",
    RESULTS / "exp38_profit_at_v" / "nvda_profit_at_v_path.csv",
]


def die(msg: str) -> None:
    print("=" * 100)
    print("ERROR")
    print("=" * 100)
    print(msg)
    sys.exit(1)


def first_existing(paths):
    for p in paths:
        if p.exists():
            return p
    return None


def pick_event_file() -> Path:
    p = first_existing(EVENT_CANDIDATES)
    if p is None:
        die(
            "Experiment #46 event file is missing. Tried:\n"
            + "\n".join(f"  {p}" for p in EVENT_CANDIDATES)
        )
    return p


def pick_raw_file() -> Path:
    p = first_existing(RAW_CANDIDATES)
    if p is None:
        # Diagnostic search only; do not substitute arbitrary files.
        matches = sorted(glob.glob(str(RESULTS / "**" / "*trajectory*.csv"), recursive=True))
        die(
            "Raw trajectory file is missing. Tried:\n"
            + "\n".join(f"  {p}" for p in RAW_CANDIDATES)
            + ("\n\nOther trajectory-like files found:\n" + "\n".join(f"  {m}" for m in matches[:20]) if matches else "")
        )
    return p


def utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def get_event_pnl_column(df: pd.DataFrame) -> str:
    for c in ("exit_now_pnl_pct", "pnl_at_v_pct"):
        if c in df.columns:
            return c
    raise KeyError("#46 event file has neither exit_now_pnl_pct nor pnl_at_v_pct")


def get_stay_column(df: pd.DataFrame) -> str:
    for c in ("eventual_pnl_hindsight_pct", "stay_actual_pnl_pct"):
        if c in df.columns:
            return c
    raise KeyError("#46 event file has no eventual STAY P&L column")


def pnl_from_close(direction: str, entry_price: float, close_price: float) -> float:
    if not math.isfinite(entry_price) or entry_price == 0 or not math.isfinite(close_price):
        return float("nan")
    d = str(direction).upper()
    if d == "LONG":
        return (close_price - entry_price) / entry_price * 100.0
    if d == "SHORT":
        return (entry_price - close_price) / entry_price * 100.0
    return float("nan")


def sign_code(x: float, eps: float = 0.0) -> str:
    if pd.isna(x):
        return "?"
    if x < -eps:
        return "A"
    if x > eps:
        return "F"
    return "Z"


def consecutive_from_start(codes: list[str], wanted: str) -> int:
    n = 0
    for c in codes:
        if c == wanted:
            n += 1
        else:
            break
    return n


def main() -> None:
    event_path = pick_event_file()
    raw_path = pick_raw_file()

    events = pd.read_csv(event_path)
    raw = pd.read_csv(raw_path)

    print("=" * 100)
    print("AIMn KISS — EXPERIMENT #48 UNPROFITABLE V: IMMEDIATE POST-V BEHAVIOR")
    print("=" * 100)
    print("Research only. No production changes. No orders. No AI. No threshold promotion.")
    print()
    print("#46 EVENT SOURCE")
    print(f"Selected: {event_path}")
    print(f"Rows:     {len(events):,}")
    print(f"Columns:  {list(events.columns)}")
    print()
    print("RAW 5-MINUTE SOURCE")
    print(f"Selected: {raw_path}")
    print(f"Rows:     {len(raw):,}")
    print(f"Columns:  {list(raw.columns)}")
    print("=" * 100)

    required_event = {"case_id", "trade_id", "direction", "event_time_utc"}
    required_raw = {
        "case_id",
        "symbol",
        "direction",
        "transition_known_utc",
        "candle_utc",
    }
    miss_e = required_event - set(events.columns)
    miss_r = required_raw - set(raw.columns)
    if miss_e:
        die(f"#46 event file is missing columns: {sorted(miss_e)}")
    if miss_r:
        die(f"Raw trajectory is missing columns: {sorted(miss_r)}")

    event_pnl_col = get_event_pnl_column(events)
    stay_col = get_stay_column(events)

    events = events.copy()
    raw = raw.copy()
    events["event_time_utc"] = utc(events["event_time_utc"])
    raw["candle_utc"] = utc(raw["candle_utc"])
    raw["transition_known_utc"] = utc(raw["transition_known_utc"])

    if events["event_time_utc"].isna().any():
        die("Some #46 event timestamps could not be parsed as UTC.")
    if raw["candle_utc"].isna().any():
        die("Some raw candle timestamps could not be parsed as UTC.")

    # We only want the five #46 qualifying unprofitable V events.
    # No rediscovery and no new profitability threshold.
    events = events[events[event_pnl_col] <= 0.0].copy()

    # Keep only the NVDA research sample represented by #46.
    if "symbol" in events.columns:
        nvda = events[events["symbol"].astype(str).str.upper().eq("NVDA")].copy()
        if not nvda.empty:
            events = nvda

    if events.empty:
        die("#46 event file contains no unprofitable V events at the existing 0.0000% level.")

    # Prefer the full raw trajectory. The actual source is expected to have one
    # row per completed 5-minute candle after transition_known_utc.
    raw["minutes_after_known_calc"] = (
        raw["candle_utc"] - raw["transition_known_utc"]
    ).dt.total_seconds() / 60.0

    # Build case-local sorted raw rows.
    raw = raw.sort_values(["case_id", "candle_utc"]).reset_index(drop=True)

    output_rows = []
    unmatched = []

    for _, ev in events.sort_values(["event_time_utc", "case_id"]).iterrows():
        case_id = str(ev["case_id"])
        direction = str(ev["direction"]).upper()
        event_time = ev["event_time_utc"]
        entry_price = float(ev["entry_price"]) if "entry_price" in ev and pd.notna(ev["entry_price"]) else float("nan")
        exit_pnl = float(ev[event_pnl_col]) if pd.notna(ev[event_pnl_col]) else float("nan")
        stay_pnl = float(ev[stay_col]) if pd.notna(ev[stay_col]) else float("nan")

        r = raw[raw["case_id"].astype(str).eq(case_id)].copy()
        if r.empty:
            unmatched.append((case_id, "case_id not found"))
            continue
        r = r.sort_values("candle_utc").copy()

        # Exact causal event candle first.
        exact = r[r["candle_utc"].eq(event_time)]
        if not exact.empty:
            event_row = exact.iloc[-1]
            alignment = "EXACT"
        else:
            # Diagnostic only: choose the nearest raw candle no farther than 5m.
            r["delta_sec"] = (r["candle_utc"] - event_time).abs().dt.total_seconds()
            near = r[r["delta_sec"] <= 300].sort_values("delta_sec")
            if near.empty:
                unmatched.append((case_id, "event candle not found within 5m"))
                continue
            event_row = near.iloc[0]
            alignment = "NEAREST_WITHIN_5M"

        event_candle_time = event_row["candle_utc"]

        # Only completed candles strictly AFTER the causal V candle.
        post = r[r["candle_utc"] > event_candle_time].copy().sort_values("candle_utc")
        if post.empty:
            unmatched.append((case_id, "no post-V candles"))
            continue

        # We need the entry price to calculate a consistent P&L path.
        if not math.isfinite(entry_price):
            unmatched.append((case_id, "entry_price missing/invalid"))
            continue

        post["pnl_pct_calc"] = post["close"].astype(float).map(
            lambda px: pnl_from_close(direction, entry_price, float(px))
        )
        event_close = float(event_row["close"])
        event_pnl_calc = pnl_from_close(direction, entry_price, event_close)
        post["d_pnl_pct"] = post["pnl_pct_calc"].diff()
        post.loc[post.index[0], "d_pnl_pct"] = post.iloc[0]["pnl_pct_calc"] - event_pnl_calc
        post["code"] = post["d_pnl_pct"].map(sign_code)

        # First 12 completed 5-minute candles after the V = one hour.
        first = post.head(12).copy()
        codes = first["code"].tolist()
        seq = "".join(codes)

        # Checkpoint P&L / changes.
        rec = {
            "case_id": case_id,
            "trade_id": ev["trade_id"],
            "symbol": ev["symbol"] if "symbol" in ev else "NVDA",
            "direction": direction,
            "event_time_utc": event_time.isoformat(),
            "aligned_raw_candle_utc": event_candle_time.isoformat(),
            "alignment": alignment,
            "exit_now_pnl_pct": exit_pnl,
            "raw_pnl_at_v_pct": event_pnl_calc,
            "stay_actual_pnl_pct": stay_pnl,
            "stay_minus_exit_pct": stay_pnl - exit_pnl,
            "sequence_12_candles_60m": seq,
            "first_adverse_streak": consecutive_from_start(codes, "A"),
            "first_favorable_streak": consecutive_from_start(codes, "F"),
            "post_v_candles_available": len(post),
            "min_pnl_after_v_pct": float(post["pnl_pct_calc"].min()),
            "max_pnl_after_v_pct": float(post["pnl_pct_calc"].max()),
        }

        for mins in (5, 10, 15, 20, 30, 45, 60):
            n = mins // 5
            if len(post) >= n:
                val = float(post.iloc[n - 1]["pnl_pct_calc"])
                rec[f"pnl_after_{mins}m_pct"] = val
                rec[f"change_from_v_after_{mins}m_pct"] = val - event_pnl_calc
                rec[f"sign_after_{mins}m"] = sign_code(val - event_pnl_calc)
            else:
                rec[f"pnl_after_{mins}m_pct"] = float("nan")
                rec[f"change_from_v_after_{mins}m_pct"] = float("nan")
                rec[f"sign_after_{mins}m"] = "?"

        # Store the individual post-V candle observations for auditability.
        for i, (_, rr) in enumerate(first.iterrows(), start=1):
            rec[f"candle_{i}_time_utc"] = rr["candle_utc"].isoformat()
            rec[f"candle_{i}_d_pnl_pct"] = float(rr["d_pnl_pct"])
            rec[f"candle_{i}_code"] = rr["code"]

        output_rows.append(rec)

    result = pd.DataFrame(output_rows)

    event_out = OUT / "nvda_unprofitable_v_post_v_streaks.csv"
    summary_out = OUT / "nvda_unprofitable_v_post_v_streaks_summary.csv"
    metadata_out = OUT / "exp48_metadata.txt"

    if result.empty:
        die("No #46 events could be attached to the raw 5-minute trajectory.")

    result.to_csv(event_out, index=False)

    # Pattern counts are descriptive only.
    pattern_counts = (
        result["sequence_12_candles_60m"]
        .value_counts(dropna=False)
        .rename_axis("sequence_12_candles_60m")
        .reset_index(name="events")
    )

    summary = pd.DataFrame(
        [
            {
                "events_analyzed": len(result),
                "unique_trades": result["trade_id"].nunique(),
                "exact_alignment": int((result["alignment"] == "EXACT").sum()),
                "nearest_alignment": int((result["alignment"] != "EXACT").sum()),
                "avg_first_adverse_streak": result["first_adverse_streak"].mean(),
                "median_first_adverse_streak": result["first_adverse_streak"].median(),
                "avg_first_favorable_streak": result["first_favorable_streak"].mean(),
                "median_first_favorable_streak": result["first_favorable_streak"].median(),
                "avg_exit_now_pnl_pct": result["exit_now_pnl_pct"].mean(),
                "avg_stay_actual_pnl_pct": result["stay_actual_pnl_pct"].mean(),
                "avg_stay_minus_exit_pct": result["stay_minus_exit_pct"].mean(),
                "stay_better_count": int((result["stay_minus_exit_pct"] > 0).sum()),
                "exit_better_count": int((result["stay_minus_exit_pct"] < 0).sum()),
                "same_count": int((result["stay_minus_exit_pct"] == 0).sum()),
            }
        ]
    )
    summary.to_csv(summary_out, index=False)

    with metadata_out.open("w", encoding="utf-8") as f:
        f.write("AIMn KISS — Experiment #48\n")
        f.write("UNPROFITABLE V: IMMEDIATE POST-V BEHAVIOR\n\n")
        f.write("RESEARCH ONLY\n")
        f.write("No production strategy changes.\n")
        f.write("No orders.\n")
        f.write("No AI training.\n")
        f.write("No threshold promotion.\n")
        f.write("No re-entry simulation.\n\n")
        f.write(f"#46 event source: {event_path}\n")
        f.write(f"Raw trajectory source: {raw_path}\n")
        f.write(f"Events supplied by #46: {len(events)}\n")
        f.write(f"Events attached to raw trajectory: {len(result)}\n")
        f.write("A = adverse 5m P&L change; F = favorable; Z = flat.\n")
        f.write("The sequence is descriptive and is NOT a trading rule.\n")

    print()
    print("=" * 100)
    print("CORE RESULT")
    print("=" * 100)
    print(f"#46 unprofitable V events supplied : {len(events)}")
    print(f"Events attached to raw trajectory  : {len(result)}")
    print(f"Exact causal candle alignment      : {(result['alignment'] == 'EXACT').sum()}")
    print(f"Nearest-within-5m alignment         : {(result['alignment'] != 'EXACT').sum()}")
    print()
    print(f"Average EXIT NOW P&L                : {result['exit_now_pnl_pct'].mean():.4f}%")
    print(f"Average STAY actual P&L             : {result['stay_actual_pnl_pct'].mean():.4f}%")
    print(f"Average STAY minus EXIT              : {result['stay_minus_exit_pct'].mean():.4f}%")
    print(f"STAY better                          : {(result['stay_minus_exit_pct'] > 0).sum()}")
    print(f"EXIT better                          : {(result['stay_minus_exit_pct'] < 0).sum()}")
    print(f"Same                                 : {(result['stay_minus_exit_pct'] == 0).sum()}")
    print()
    print("FIRST ADVERSE STREAK")
    print(f"Average consecutive A candles        : {result['first_adverse_streak'].mean():.3f}")
    print(f"Median consecutive A candles         : {result['first_adverse_streak'].median():.3f}")
    print("FIRST FAVORABLE STREAK")
    print(f"Average consecutive F candles        : {result['first_favorable_streak'].mean():.3f}")
    print(f"Median consecutive F candles         : {result['first_favorable_streak'].median():.3f}")
    print()
    print("POST-V 60-MINUTE SEQUENCES (DESCRIPTIVE — NO RULE)")
    print(result[["trade_id", "direction", "sequence_12_candles_60m", "first_adverse_streak", "first_favorable_streak", "exit_now_pnl_pct", "stay_actual_pnl_pct", "stay_minus_exit_pct"]].to_string(index=False))
    print()
    print("SEQUENCE COUNTS")
    print(pattern_counts.to_string(index=False))
    print()
    if unmatched:
        print("UNMATCHED #46 EVENTS")
        for item in unmatched:
            print(f"  {item[0]}: {item[1]}")
    print()
    print("OUTPUTS")
    print(f"Events : {event_out}")
    print(f"Summary: {summary_out}")
    print(f"Meta   : {metadata_out}")


if __name__ == "__main__":
    main()