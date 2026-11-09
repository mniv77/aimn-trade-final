#!/usr/bin/env python3

"""
AIMn KISS — Experiment #48
UNPROFITABLE V: NOISE vs CONTINUING REVERSAL

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

IMPORTANT
---------
Experiment #46 already identified the qualifying
NOT-YET-PROFITABLE V events.

Therefore #48 MUST use the #46 event file.

Then #48 uses the RAW 5-MINUTE TRAJECTORY as the
price source of truth.

We do NOT rediscover V events.

We do NOT invent a profitability threshold.

We simply examine what happened AFTER the causal
V reversal candle.

For every qualifying event we measure:

    V
    +5m
    +10m
    +15m
    +30m
    +60m

and also inspect the candle-by-candle P&L path.

The purpose is observation, not rule creation.
"""

from __future__ import annotations

from pathlib import Path
import math
import pandas as pd


# ============================================================================
# PATHS
# ============================================================================

BASE = Path(__file__).resolve().parent

EVENTS_FILE = (
    BASE
    / "results"
    / "exp46_not_yet_profitable_v"
    / "nvda_not_yet_profitable_v_events.csv"
)

RAW_FILE = (
    BASE
    / "results"
    / "exp32_raw_candle_v_geometry"
    / "raw_v_trajectory.csv"
)

OUTPUT_DIR = (
    BASE
    / "results"
    / "exp48_unprofitable_v_streaks"
)

OUTPUT_EVENTS = OUTPUT_DIR / "nvda_unprofitable_v_post_path.csv"
OUTPUT_SUMMARY = OUTPUT_DIR / "nvda_unprofitable_v_post_path_summary.csv"
OUTPUT_META = OUTPUT_DIR / "exp48_metadata.txt"


# ============================================================================
# REQUIRED COLUMNS
# ============================================================================

EVENT_REQUIRED = [
    "case_id",
    "symbol",
    "direction",
    "trade_id",
    "entry_time_utc",
    "entry_price",
    "v_reversal_candle_utc",
    "pnl_at_v_pct",
    "exit_now_pnl_pct",
    "stay_actual_pnl_pct",
    "eventual_pnl_hindsight_pct",
    "stay_minus_exit_pct",
    "stay_vs_exit",
]

RAW_REQUIRED = [
    "case_id",
    "symbol",
    "direction",
    "candle_utc",
    "close",
]


# ============================================================================
# HELPERS
# ============================================================================

def require_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        print("=" * 120)
        print("ERROR")
        print("=" * 120)
        print(f"{name} is missing required columns:")
        print(missing)
        print("Actual columns:")
        print(list(df.columns))
        raise SystemExit(1)


def to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def trade_pnl_pct(direction: str, entry_price: float, close_price: float) -> float:
    """
    Mark-to-market P&L proxy from entry price.

    LONG:
        (close - entry) / entry

    SHORT:
        (entry - close) / entry

    This is gross price P&L only.
    No commission or slippage is added here.
    """
    if not math.isfinite(entry_price) or entry_price == 0:
        return float("nan")

    direction = str(direction).upper().strip()

    if direction == "LONG":
        return (close_price - entry_price) / entry_price * 100.0

    if direction == "SHORT":
        return (entry_price - close_price) / entry_price * 100.0

    return float("nan")


def nearest_row(
    rows: pd.DataFrame,
    target_time: pd.Timestamp,
    tolerance_minutes: int = 1,
) -> pd.Series | None:
    if rows.empty:
        return None

    temp = rows.copy()
    temp["time_distance_sec"] = (
        temp["candle_utc"] - target_time
    ).abs().dt.total_seconds()

    temp = temp.sort_values("time_distance_sec")
    best = temp.iloc[0]

    if best["time_distance_sec"] <= tolerance_minutes * 60:
        return best

    return None


def sign_of(value: float) -> str:
    if pd.isna(value):
        return "?"
    if value > 0:
        return "+"
    if value < 0:
        return "-"
    return "0"


def fmt(value: float | None, digits: int = 4) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:.{digits}f}"


def fmt_pct(value: float | None, digits: int = 4) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:.{digits}f}%"


# ============================================================================
# LOAD
# ============================================================================

def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:

    print("=" * 120)
    print("AIMn KISS — EXPERIMENT #48")
    print("UNPROFITABLE V: NOISE vs CONTINUING REVERSAL")
    print("=" * 120)
    print("Research only.")
    print("No production strategy changes.")
    print("No orders.")
    print("No AI.")
    print("No threshold promotion.")
    print("No re-entry simulation.")
    print()

    # ------------------------------------------------------------------------
    # #46 EVENTS
    # ------------------------------------------------------------------------

    if not EVENTS_FILE.exists():
        print("=" * 120)
        print("ERROR")
        print("=" * 120)
        print("Experiment #46 event file was not found:")
        print(EVENTS_FILE)
        raise SystemExit(1)

    events = pd.read_csv(EVENTS_FILE)
    require_columns(events, EVENT_REQUIRED, "Experiment #46 event file")

    print("=" * 120)
    print("SOURCE: EXPERIMENT #46 QUALIFYING EVENTS")
    print("=" * 120)
    print(f"File: {EVENTS_FILE}")
    print(f"Rows: {len(events):,}")
    print("V timestamp column: v_reversal_candle_utc")
    print()

    # ------------------------------------------------------------------------
    # RAW TRAJECTORY
    # ------------------------------------------------------------------------

    if not RAW_FILE.exists():
        print("=" * 120)
        print("ERROR")
        print("=" * 120)
        print("Raw trajectory file was not found:")
        print(RAW_FILE)
        raise SystemExit(1)

    raw = pd.read_csv(RAW_FILE)
    require_columns(raw, RAW_REQUIRED, "RAW 5-minute trajectory")

    print("=" * 120)
    print("SOURCE: RAW 5-MINUTE TRAJECTORY")
    print("=" * 120)
    print(f"File: {RAW_FILE}")
    print(f"Rows: {len(raw):,}")
    print(f"Columns: {list(raw.columns)}")
    print()

    # ------------------------------------------------------------------------
    # TIMESTAMPS
    # ------------------------------------------------------------------------

    events["v_reversal_candle_utc"] = to_utc(
        events["v_reversal_candle_utc"]
    )

    events["entry_time_utc"] = to_utc(
        events["entry_time_utc"]
    )

    raw["candle_utc"] = to_utc(raw["candle_utc"])

    bad_event_times = events["v_reversal_candle_utc"].isna().sum()
    bad_raw_times = raw["candle_utc"].isna().sum()

    if bad_event_times:
        print(
            f"ERROR: {bad_event_times} #46 events have invalid "
            "v_reversal_candle_utc."
        )
        raise SystemExit(1)

    if bad_raw_times:
        print(
            f"ERROR: {bad_raw_times} raw trajectory rows have invalid "
            "candle_utc."
        )
        raise SystemExit(1)

    # Numeric cleanup
    for c in [
        "entry_price",
        "pnl_at_v_pct",
        "exit_now_pnl_pct",
        "stay_actual_pnl_pct",
        "eventual_pnl_hindsight_pct",
        "stay_minus_exit_pct",
    ]:
        events[c] = pd.to_numeric(events[c], errors="coerce")

    raw["close"] = pd.to_numeric(raw["close"], errors="coerce")

    return events, raw


# ============================================================================
# BUILD POST-V PATH
# ============================================================================

def build_event_path(
    event: pd.Series,
    raw: pd.DataFrame,
) -> dict:

    case_id = str(event["case_id"])
    symbol = str(event["symbol"])
    direction = str(event["direction"]).upper().strip()

    v_time = event["v_reversal_candle_utc"]
    entry_price = float(event["entry_price"])

    # ------------------------------------------------------------------------
    # Find raw candles for the same case
    # ------------------------------------------------------------------------

    case_rows = raw[
        (raw["case_id"].astype(str) == case_id)
        & (raw["symbol"].astype(str) == symbol)
    ].copy()

    if case_rows.empty:
        return {
            "case_id": case_id,
            "trade_id": event["trade_id"],
            "symbol": symbol,
            "direction": direction,
            "status": "NO_RAW_CASE_MATCH",
        }

    case_rows = case_rows.sort_values("candle_utc").reset_index(drop=True)

    # Use V candle and everything AFTER it.
    post = case_rows[
        case_rows["candle_utc"] >= v_time
    ].copy()

    if post.empty:
        return {
            "case_id": case_id,
            "trade_id": event["trade_id"],
            "symbol": symbol,
            "direction": direction,
            "status": "NO_RAW_CANDLE_AT_OR_AFTER_V",
        }

    # ------------------------------------------------------------------------
    # Calculate trade-direction P&L directly from raw 5m close
    # ------------------------------------------------------------------------

    post["pnl_proxy_pct"] = post["close"].apply(
        lambda x: trade_pnl_pct(direction, entry_price, float(x))
        if pd.notna(x)
        else float("nan")
    )

    post["minutes_after_v"] = (
        post["candle_utc"] - v_time
    ).dt.total_seconds() / 60.0

    # exact causal V row = first row at or after V timestamp
    v_row = post.iloc[0]

    v_pnl = float(v_row["pnl_proxy_pct"])

    # ------------------------------------------------------------------------
    # Checkpoints
    # ------------------------------------------------------------------------

    checkpoint_values: dict[str, float] = {}

    for minutes, label in [
        (0, "v"),
        (5, "5m"),
        (10, "10m"),
        (15, "15m"),
        (30, "30m"),
        (60, "60m"),
    ]:
        target = v_time + pd.Timedelta(minutes=minutes)

        row = nearest_row(
            post,
            target,
            tolerance_minutes=1,
        )

        if row is None:
            checkpoint_values[label] = float("nan")
        else:
            checkpoint_values[label] = float(row["pnl_proxy_pct"])

    # ------------------------------------------------------------------------
    # Post-V candle-by-candle path
    # ------------------------------------------------------------------------

    path_rows = post.head(13).copy()

    # Change from previous candle's P&L.
    path_rows["pnl_change_pct"] = (
        path_rows["pnl_proxy_pct"].diff()
    )

    changes = path_rows["pnl_change_pct"].iloc[1:].tolist()

    # Count consecutive adverse candles immediately AFTER the V.
    adverse_streak = 0
    favorable_streak = 0

    for change in changes:
        if pd.isna(change):
            break

        if change < 0:
            adverse_streak += 1
            break

        if change > 0:
            favorable_streak += 1
            break

        # zero = stop counting the initial directional streak
        break

    # Stronger descriptive streak information:
    adverse_run = 0
    max_adverse_run = 0

    favorable_run = 0
    max_favorable_run = 0

    for change in changes:
        if pd.isna(change):
            continue

        if change < 0:
            adverse_run += 1
            max_adverse_run = max(max_adverse_run, adverse_run)
            favorable_run = 0

        elif change > 0:
            favorable_run += 1
            max_favorable_run = max(max_favorable_run, favorable_run)
            adverse_run = 0

        else:
            adverse_run = 0
            favorable_run = 0

    # ------------------------------------------------------------------------
    # Simple descriptive path label
    #
    # THIS IS NOT A TRADING RULE.
    # It only describes the observed first three post-V changes.
    # ------------------------------------------------------------------------

    first_changes = changes[:3]

    signs = [
        sign_of(x)
        for x in first_changes
    ]

    while len(signs) < 3:
        signs.append("?")

    first3 = "".join(signs)

    if first3 == "...":
        behavior = "INSUFFICIENT"

    elif len(first_changes) >= 1 and first_changes[0] > 0:
        behavior = "IMMEDIATE_RECOVERY"

    elif (
        len(first_changes) >= 2
        and first_changes[0] < 0
        and first_changes[1] > 0
    ):
        behavior = "NOISE_THEN_RECOVERY"

    elif (
        len(first_changes) >= 3
        and all(x < 0 for x in first_changes)
    ):
        behavior = "CONTINUING_REVERSAL"

    else:
        behavior = "MIXED"

    # ------------------------------------------------------------------------
    # V-to-checkpoint changes
    # ------------------------------------------------------------------------

    pnl_5 = checkpoint_values["5m"]
    pnl_10 = checkpoint_values["10m"]
    pnl_15 = checkpoint_values["15m"]
    pnl_30 = checkpoint_values["30m"]
    pnl_60 = checkpoint_values["60m"]

    result = {
        # Identity
        "case_id": case_id,
        "trade_id": event["trade_id"],
        "symbol": symbol,
        "direction": direction,

        # Timing
        "v_reversal_candle_utc": v_time.isoformat(),
        "entry_time_utc": event["entry_time_utc"].isoformat()
        if pd.notna(event["entry_time_utc"])
        else "",

        # #46 source values
        "pnl_at_v_pct": float(event["pnl_at_v_pct"]),
        "exit_now_pnl_pct": float(event["exit_now_pnl_pct"]),
        "stay_actual_pnl_pct": float(event["stay_actual_pnl_pct"]),
        "eventual_pnl_hindsight_pct": float(
            event["eventual_pnl_hindsight_pct"]
        ),
        "stay_minus_exit_pct": float(
            event["stay_minus_exit_pct"]
        ),
        "stay_vs_exit": str(event["stay_vs_exit"]),

        # Raw 5m P&L path
        "raw_v_pnl_proxy_pct": v_pnl,
        "pnl_after_5m_pct": pnl_5,
        "pnl_after_10m_pct": pnl_10,
        "pnl_after_15m_pct": pnl_15,
        "pnl_after_30m_pct": pnl_30,
        "pnl_after_60m_pct": pnl_60,

        # Change from V
        "change_from_v_5m_pct": pnl_5 - v_pnl
        if pd.notna(pnl_5)
        else float("nan"),

        "change_from_v_10m_pct": pnl_10 - v_pnl
        if pd.notna(pnl_10)
        else float("nan"),

        "change_from_v_15m_pct": pnl_15 - v_pnl
        if pd.notna(pnl_15)
        else float("nan"),

        "change_from_v_30m_pct": pnl_30 - v_pnl
        if pd.notna(pnl_30)
        else float("nan"),

        "change_from_v_60m_pct": pnl_60 - v_pnl
        if pd.notna(pnl_60)
        else float("nan"),

        # Descriptive behavior
        "post_v_behavior": behavior,
        "first3_change_signs": first3,
        "first_change_after_v_pct": (
            changes[0] if len(changes) >= 1 else float("nan")
        ),
        "second_change_after_v_pct": (
            changes[1] if len(changes) >= 2 else float("nan")
        ),
        "third_change_after_v_pct": (
            changes[2] if len(changes) >= 3 else float("nan")
        ),

        "initial_adverse_streak": adverse_streak,
        "initial_favorable_streak": favorable_streak,
        "max_adverse_streak_first_12_candles": max_adverse_run,
        "max_favorable_streak_first_12_candles": max_favorable_run,

        # Count of available raw observations
        "raw_candles_available_after_v": len(post),

        "status": "OK",
    }

    # ------------------------------------------------------------------------
    # Human-readable raw path
    # ------------------------------------------------------------------------

    path_parts = []

    for _, row in path_rows.iterrows():
        mins = row["minutes_after_v"]
        pnl = row["pnl_proxy_pct"]

        if pd.isna(pnl):
            continue

        path_parts.append(
            f"+{mins:.0f}m:{pnl:+.4f}%"
        )

    result["raw_pnl_path"] = " | ".join(path_parts)

    return result


# ============================================================================
# MAIN ANALYSIS
# ============================================================================

def main() -> None:

    events, raw = load_data()

    print("=" * 120)
    print("BUILDING POST-V RAW 5-MINUTE TRAJECTORIES")
    print("=" * 120)

    results = []

    for _, event in events.iterrows():
        result = build_event_path(event, raw)
        results.append(result)

    out = pd.DataFrame(results)

    # ------------------------------------------------------------------------
    # Save outputs
    # ------------------------------------------------------------------------

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    out.to_csv(
        OUTPUT_EVENTS,
        index=False,
        float_format="%.8f",
    )

    # ------------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------------

    valid = out[out["status"] == "OK"].copy()

    summary_rows = []

    if not valid.empty:

        behavior_order = [
            "IMMEDIATE_RECOVERY",
            "NOISE_THEN_RECOVERY",
            "CONTINUING_REVERSAL",
            "MIXED",
            "INSUFFICIENT",
        ]

        for behavior in behavior_order:

            g = valid[
                valid["post_v_behavior"] == behavior
            ]

            if g.empty:
                continue

            summary_rows.append(
                {
                    "behavior": behavior,
                    "events": len(g),
                    "avg_pnl_at_v_pct": g["pnl_at_v_pct"].mean(),
                    "avg_change_5m_pct": g[
                        "change_from_v_5m_pct"
                    ].mean(),
                    "avg_change_10m_pct": g[
                        "change_from_v_10m_pct"
                    ].mean(),
                    "avg_change_15m_pct": g[
                        "change_from_v_15m_pct"
                    ].mean(),
                    "avg_change_30m_pct": g[
                        "change_from_v_30m_pct"
                    ].mean(),
                    "avg_change_60m_pct": g[
                        "change_from_v_60m_pct"
                    ].mean(),
                    "avg_stay_minus_exit_pct": g[
                        "stay_minus_exit_pct"
                    ].mean(),
                    "stay_better_count": int(
                        (g["stay_vs_exit"] == "STAY_BETTER").sum()
                    ),
                    "exit_better_count": int(
                        (g["stay_vs_exit"] == "EXIT_BETTER").sum()
                    ),
                }
            )

    summary = pd.DataFrame(summary_rows)

    summary.to_csv(
        OUTPUT_SUMMARY,
        index=False,
        float_format="%.8f",
    )

    # ------------------------------------------------------------------------
    # Console report
    # ------------------------------------------------------------------------

    print()
    print("=" * 120)
    print("EXPERIMENT #48 — RESULT")
    print("=" * 120)
    print(f"#46 qualifying events : {len(events)}")
    print(f"Raw-path matches       : {len(valid)}")
    print(f"Missing raw paths      : {len(events) - len(valid)}")
    print()

    if valid.empty:
        print("NO VALID RAW PATHS FOUND.")
        print("=" * 120)
        return

    print("=" * 120)
    print("EVENT-BY-EVENT — STAY vs EXIT")
    print("=" * 120)

    display_cols = [
        "case_id",
        "trade_id",
        "direction",
        "pnl_at_v_pct",
        "exit_now_pnl_pct",
        "stay_actual_pnl_pct",
        "stay_minus_exit_pct",
        "post_v_behavior",
        "change_from_v_5m_pct",
        "change_from_v_10m_pct",
        "change_from_v_15m_pct",
        "change_from_v_30m_pct",
        "change_from_v_60m_pct",
        "stay_vs_exit",
    ]

    print(
        valid[display_cols].to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print()
    print("=" * 120)
    print("RAW 5-MINUTE PATHS")
    print("=" * 120)

    for _, row in valid.iterrows():

        print(
            f"{row['case_id']}  "
            f"{row['trade_id']}  "
            f"{row['direction']}"
        )

        print(
            f"  V P&L     : "
            f"{fmt_pct(row['pnl_at_v_pct'])}"
        )

        print(
            f"  EXIT NOW  : "
            f"{fmt_pct(row['exit_now_pnl_pct'])}"
        )

        print(
            f"  STAY      : "
            f"{fmt_pct(row['stay_actual_pnl_pct'])}"
        )

        print(
            f"  Decision  : "
            f"{row['stay_vs_exit']}"
        )

        print(
            f"  Behavior  : "
            f"{row['post_v_behavior']}"
        )

        print(
            f"  First 3 changes: "
            f"{row['first3_change_signs']}"
        )

        print(
            f"  Raw path  : "
            f"{row['raw_pnl_path']}"
        )

        print()

    # ------------------------------------------------------------------------
    # High-level counts
    # ------------------------------------------------------------------------

    print("=" * 120)
    print("BEHAVIOR COUNTS")
    print("=" * 120)

    behavior_counts = (
        valid["post_v_behavior"]
        .value_counts()
        .reindex(
            [
                "IMMEDIATE_RECOVERY",
                "NOISE_THEN_RECOVERY",
                "CONTINUING_REVERSAL",
                "MIXED",
                "INSUFFICIENT",
            ],
            fill_value=0,
        )
    )

    total = len(valid)

    for behavior, count in behavior_counts.items():
        pct = (
            count / total * 100.0
            if total
            else 0.0
        )

        print(
            f"{behavior:28s} "
            f"{count:3d} "
            f"({pct:6.2f}%)"
        )

    print()

    # ------------------------------------------------------------------------
    # Stay vs Exit totals
    # ------------------------------------------------------------------------

    print("=" * 120)
    print("STAY vs EXIT")
    print("=" * 120)

    stay_better = int(
        (valid["stay_vs_exit"] == "STAY_BETTER").sum()
    )

    exit_better = int(
        (valid["stay_vs_exit"] == "EXIT_BETTER").sum()
    )

    same = int(
        (
            pd.to_numeric(
                valid["stay_minus_exit_pct"],
                errors="coerce",
            ).abs()
            < 1e-12
        ).sum()
    )

    avg_difference = pd.to_numeric(
        valid["stay_minus_exit_pct"],
        errors="coerce",
    ).mean()

    print(f"STAY better : {stay_better}")
    print(f"EXIT better : {exit_better}")
    print(f"Same        : {same}")
    print(
        "Average STAY - EXIT : "
        f"{avg_difference:.4f}%"
    )

    # ------------------------------------------------------------------------
    # Write metadata
    # ------------------------------------------------------------------------

    with OUTPUT_META.open("w", encoding="utf-8") as f:

        f.write("AIMn KISS — Experiment #48\n")
        f.write("UNPROFITABLE V: NOISE vs CONTINUING REVERSAL\n")
        f.write("\n")
        f.write("RESEARCH ONLY\n")
        f.write("No production strategy changes.\n")
        f.write("No orders.\n")
        f.write("No AI training.\n")
        f.write("No threshold promotion.\n")
        f.write("No re-entry simulation.\n")
        f.write("\n")
        f.write(f"Events source: {EVENTS_FILE}\n")
        f.write(f"Raw source:    {RAW_FILE}\n")
        f.write(f"Input events:  {len(events)}\n")
        f.write(f"Raw matches:   {len(valid)}\n")
        f.write("\n")
        f.write(
            "The causal V timestamp is "
            "v_reversal_candle_utc from Experiment #46.\n"
        )
        f.write(
            "Post-V behavior is descriptive only; it is not a trading rule.\n"
        )

    print()
    print("=" * 120)
    print("OUTPUTS")
    print("=" * 120)
    print(f"Events : {OUTPUT_EVENTS}")
    print(f"Summary: {OUTPUT_SUMMARY}")
    print(f"Meta   : {OUTPUT_META}")
    print("=" * 120)


if __name__ == "__main__":
    main()
