#!/usr/bin/env python3

"""
AIMn KISS — Experiment #48
UNPROFITABLE V: NOISE OR CONTINUING REVERSAL?

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

PRIMARY SOURCE
--------------
RAW 5-MINUTE TRAJECTORY

Experiment #46 supplies the five qualifying
NOT-YET-PROFITABLE V EVENTS.

CRITICAL TIMING
---------------
The causal V is the completed candle stored in:

    v_reversal_candle_utc

We then inspect ONLY candles strictly AFTER that V.

The raw trajectory contains:

    transition_known_utc
    candle_utc
    minutes_after_known

IMPORTANT:
minutes_after_known is measured from the transition,
NOT from the V.

Therefore this experiment does NOT use that field
to calculate V+5, V+10, etc.

Instead we calculate:

    V + 5 minutes
    V + 10 minutes
    V + 15 minutes
    V + 30 minutes
    V + 60 minutes

directly from candle_utc.

BEHAVIOR
--------
Price movement is signed by trade direction.

LONG:
    price up   = FAVORABLE
    price down = ADVERSE

SHORT:
    price down = FAVORABLE
    price up   = ADVERSE

No magnitude threshold is used.

DESCRIPTIVE RESULT
------------------
First two completed candles after V:

    FAVORABLE + FAVORABLE
        IMMEDIATE_FAVORABLE

    ADVERSE + ADVERSE
        CONTINUING_REVERSAL

    ADVERSE + FAVORABLE
        REVERSAL_THEN_RECOVERY

    FAVORABLE + ADVERSE
        RECOVERY_THEN_REVERSAL

    otherwise
        MIXED

These are observations only.

STAY VS EXIT
------------
EXIT NOW:
    P&L that existed at the causal V.

STAY:
    actual eventual trade P&L from Experiment #46.

No re-entry is modeled.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import math
import sys

import pandas as pd


# ---------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "kiss" / "results"

EXP46_FILE = (
    RESULTS
    / "exp46_not_yet_profitable_v"
    / "nvda_not_yet_profitable_v_events.csv"
)

RAW_FILE = (
    RESULTS
    / "exp32_raw_candle_v_geometry"
    / "raw_v_trajectory.csv"
)

OUT_DIR = RESULTS / "exp48_unprofitable_v_immediate"

OUT_EVENTS = OUT_DIR / "nvda_unprofitable_v_immediate_events.csv"
OUT_SUMMARY = OUT_DIR / "nvda_unprofitable_v_immediate_summary.csv"
OUT_META = OUT_DIR / "exp48_metadata.txt"


# ---------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------

HORIZONS = [5, 10, 15, 30, 60]

EPS = 1e-12


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def banner(title: str = "") -> None:
    print("=" * 110)

    if title:
        print(title)
        print("=" * 110)


def fail(message: str) -> None:
    banner("ERROR")
    print(message)
    sys.exit(1)


def read_csv(path: Path, label: str) -> pd.DataFrame:

    if not path.exists():
        fail(
            f"{label} does not exist:\n\n"
            f"{path}"
        )

    try:
        return pd.read_csv(path)

    except Exception as exc:
        fail(
            f"Could not read {label}:\n\n"
            f"{path}\n\n"
            f"{exc}"
        )

        raise


def require_columns(
    df: pd.DataFrame,
    required: list[str],
    label: str,
) -> None:

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        fail(
            f"{label} is missing required columns:\n\n"
            f"{missing}\n\n"
            f"Actual columns:\n"
            f"{list(df.columns)}"
        )


def utc(series: pd.Series) -> pd.Series:

    return pd.to_datetime(
        series,
        utc=True,
        errors="coerce",
    )


def numeric(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:

    for column in columns:

        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    return df


def signed_price_move_pct(
    direction: str,
    v_close: float,
    later_close: float,
) -> float:

    if (
        pd.isna(v_close)
        or pd.isna(later_close)
        or v_close == 0
    ):
        return math.nan

    direction = str(
        direction
    ).upper().strip()

    if direction == "LONG":

        return (
            (later_close / v_close)
            - 1.0
        ) * 100.0

    if direction == "SHORT":

        return (
            (v_close / later_close)
            - 1.0
        ) * 100.0

    return math.nan


def movement_label(
    value: float,
) -> str:

    if pd.isna(value):
        return "MISSING"

    if value > EPS:
        return "FAVORABLE"

    if value < -EPS:
        return "ADVERSE"

    return "FLAT"


def classify_behavior(
    move5: float,
    move10: float,
) -> str:

    if pd.isna(move5) or pd.isna(move10):
        return "INSUFFICIENT"

    label5 = movement_label(move5)
    label10 = movement_label(move10)

    if (
        label5 == "FAVORABLE"
        and label10 == "FAVORABLE"
    ):
        return "IMMEDIATE_FAVORABLE"

    if (
        label5 == "ADVERSE"
        and label10 == "ADVERSE"
    ):
        return "CONTINUING_REVERSAL"

    if (
        label5 == "ADVERSE"
        and label10 == "FAVORABLE"
    ):
        return "REVERSAL_THEN_RECOVERY"

    if (
        label5 == "FAVORABLE"
        and label10 == "ADVERSE"
    ):
        return "RECOVERY_THEN_REVERSAL"

    return "MIXED"


def outcome(
    exit_now: float,
    stay: float,
) -> str:

    if (
        pd.isna(exit_now)
        or pd.isna(stay)
    ):
        return "UNAVAILABLE"

    if stay > exit_now:
        return "STAY_BETTER"

    if stay < exit_now:
        return "EXIT_BETTER"

    return "SAME"


def get_exact_candle(
    raw_case: pd.DataFrame,
    timestamp: pd.Timestamp,
) -> pd.Series | None:

    match = raw_case[
        raw_case["candle_utc"] == timestamp
    ]

    if match.empty:
        return None

    return (
        match
        .sort_values("candle_utc")
        .iloc[0]
    )


def get_v_timestamp(
    event: pd.Series,
) -> pd.Timestamp:

    # Experiment #46 explicitly records the causal V candle.
    if "v_reversal_candle_utc" in event.index:

        value = event[
            "v_reversal_candle_utc"
        ]

        if not pd.isna(value):

            parsed = pd.to_datetime(
                value,
                utc=True,
                errors="coerce",
            )

            if not pd.isna(parsed):
                return parsed

    # Compatibility fallback.
    if "event_time_utc" in event.index:

        parsed = pd.to_datetime(
            event["event_time_utc"],
            utc=True,
            errors="coerce",
        )

        if not pd.isna(parsed):
            return parsed

    return pd.NaT


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:

    banner(
        "AIMn KISS — EXPERIMENT #48"
        " — UNPROFITABLE V: NOISE vs CONTINUING REVERSAL"
    )

    print(
        "Research only."
        " No production changes."
        " No orders."
        " No AI."
        " No threshold promotion."
    )

    print()

    # --------------------------------------------------------------
    # CHECK FILES
    # --------------------------------------------------------------

    events = read_csv(
        EXP46_FILE,
        "Experiment #46 event file",
    )

    raw = read_csv(
        RAW_FILE,
        "Raw 5-minute trajectory",
    )

    # --------------------------------------------------------------
    # CHECK RAW SCHEMA
    # --------------------------------------------------------------

    require_columns(
        raw,
        [
            "case_id",
            "symbol",
            "direction",
            "transition_known_utc",
            "candle_utc",
            "minutes_after_known",
            "open",
            "high",
            "low",
            "close",
        ],
        "RAW TRAJECTORY",
    )

    # --------------------------------------------------------------
    # CHECK EVENT SCHEMA
    # --------------------------------------------------------------

    require_columns(
        events,
        [
            "case_id",
            "trade_id",
            "direction",
            "pnl_at_v_pct",
            "eventual_pnl_hindsight_pct",
        ],
        "EXPERIMENT #46 EVENTS",
    )

    # --------------------------------------------------------------
    # NORMALIZE
    # --------------------------------------------------------------

    raw["case_id"] = (
        raw["case_id"]
        .astype(str)
        .str.strip()
    )

    raw["direction"] = (
        raw["direction"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    raw["transition_known_utc"] = utc(
        raw["transition_known_utc"]
    )

    raw["candle_utc"] = utc(
        raw["candle_utc"]
    )

    raw = numeric(
        raw,
        [
            "minutes_after_known",
            "open",
            "high",
            "low",
            "close",
        ],
    )

    events["case_id"] = (
        events["case_id"]
        .astype(str)
        .str.strip()
    )

    events["direction"] = (
        events["direction"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    events["pnl_at_v_pct"] = pd.to_numeric(
        events["pnl_at_v_pct"],
        errors="coerce",
    )

    events[
        "eventual_pnl_hindsight_pct"
    ] = pd.to_numeric(
        events["eventual_pnl_hindsight_pct"],
        errors="coerce",
    )

    if "v_reversal_candle_utc" in events.columns:

        events[
            "v_reversal_candle_utc"
        ] = utc(
            events[
                "v_reversal_candle_utc"
            ]
        )

    if "event_time_utc" in events.columns:

        events[
            "event_time_utc"
        ] = utc(
            events[
                "event_time_utc"
            ]
        )

    # --------------------------------------------------------------
    # SELECT ONLY UNPROFITABLE V EVENTS
    # --------------------------------------------------------------

    events = events[
        events["pnl_at_v_pct"] <= 0.0
    ].copy()

    banner(
        "SOURCE DATA"
    )

    print(
        f"Raw trajectory rows : {len(raw):,}"
    )

    print(
        f"#46 events loaded   : {len(events):,}"
    )

    print()

    # --------------------------------------------------------------
    # PROCESS EACH V
    # --------------------------------------------------------------

    rows = []

    for _, event in events.iterrows():

        case_id = event["case_id"]
        trade_id = event["trade_id"]
        direction = event["direction"]

        v_time = get_v_timestamp(
            event
        )

        exit_now = event[
            "pnl_at_v_pct"
        ]

        stay = event[
            "eventual_pnl_hindsight_pct"
        ]

        base = {
            "case_id": case_id,
            "trade_id": trade_id,
            "direction": direction,
            "v_reversal_candle_utc": v_time,
            "exit_now_pnl_pct": exit_now,
            "stay_actual_pnl_pct": stay,
            "stay_minus_exit_pct": (
                stay - exit_now
                if not (
                    pd.isna(stay)
                    or pd.isna(exit_now)
                )
                else math.nan
            ),
            "stay_vs_exit": outcome(
                exit_now,
                stay,
            ),
        }

        # ----------------------------------------------------------
        # BASIC TIMESTAMP CHECK
        # ----------------------------------------------------------

        if pd.isna(v_time):

            base["match_status"] = (
                "NO_V_TIMESTAMP"
            )

            base[
                "behavior"
            ] = "INSUFFICIENT"

            rows.append(base)
            continue

        # ----------------------------------------------------------
        # MATCH EXACT CASE
        # ----------------------------------------------------------

        raw_case = raw[
            raw["case_id"] == case_id
        ].copy()

        raw_case = raw_case.sort_values(
            "candle_utc"
        )

        if raw_case.empty:

            base["match_status"] = (
                "NO_CASE_MATCH"
            )

            base[
                "behavior"
            ] = "INSUFFICIENT"

            rows.append(base)
            continue

        # ----------------------------------------------------------
        # MATCH EXACT V CANDLE
        # ----------------------------------------------------------

        v_row = get_exact_candle(
            raw_case,
            v_time,
        )

        if v_row is None:

            base["match_status"] = (
                "NO_EXACT_V_CANDLE"
            )

            base[
                "behavior"
            ] = "INSUFFICIENT"

            rows.append(base)
            continue

        v_close = float(
            v_row["close"]
        )

        base["close_at_v"] = v_close
        base["match_status"] = "MATCHED"

        # ----------------------------------------------------------
        # EXACT FUTURE CANDLES
        #
        # These are measured from the V timestamp itself.
        # NOT from transition_known_utc.
        # ----------------------------------------------------------

        moves = {}

        for mins in HORIZONS:

            target_time = (
                v_time
                + timedelta(
                    minutes=mins
                )
            )

            future_row = get_exact_candle(
                raw_case,
                target_time,
            )

            if future_row is None:

                moves[mins] = math.nan

                base[
                    f"candle_{mins}m_utc"
                ] = pd.NaT

                base[
                    f"close_{mins}m"
                ] = math.nan

            else:

                later_close = float(
                    future_row["close"]
                )

                move = signed_price_move_pct(
                    direction,
                    v_close,
                    later_close,
                )

                moves[mins] = move

                base[
                    f"candle_{mins}m_utc"
                ] = target_time

                base[
                    f"close_{mins}m"
                ] = later_close

                base[
                    f"price_move_trade_dir_{mins}m_pct"
                ] = move

                base[
                    f"price_move_trade_dir_{mins}m"
                    ] = movement_label(
                        move
                    )

        # ----------------------------------------------------------
        # FIRST TWO POST-V CANDLES
        # ----------------------------------------------------------

        base["v_move_5m_pct"] = moves[5]
        base["v_move_10m_pct"] = moves[10]

        base["v_direction_5m"] = movement_label(
            moves[5]
        )

        base["v_direction_10m"] = movement_label(
            moves[10]
        )

        base["behavior"] = classify_behavior(
            moves[5],
            moves[10],
        )

        # ----------------------------------------------------------
        # ADDITIONAL OBSERVATION
        # ----------------------------------------------------------

        available_moves = [
            moves[m]
            for m in HORIZONS
            if not pd.isna(moves[m])
        ]

        if available_moves:

            base[
                "best_trade_direction_move_pct"
            ] = max(
                available_moves
            )

            base[
                "worst_trade_direction_move_pct"
            ] = min(
                available_moves
            )

        else:

            base[
                "best_trade_direction_move_pct"
            ] = math.nan

            base[
                "worst_trade_direction_move_pct"
            ] = math.nan

        rows.append(base)

    out = pd.DataFrame(rows)

    # --------------------------------------------------------------
    # CREATE OUTPUT
    # --------------------------------------------------------------

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        OUT_EVENTS,
        index=False,
    )

    # --------------------------------------------------------------
    # CORE REPORT
    # --------------------------------------------------------------

    banner(
        "EXPERIMENT #48 — CORE RESULT"
    )

    print(
        f"Unprofitable V events : {len(out)}"
    )

    print(
        f"Exact V matched       : "
        f"{(out['match_status'] == 'MATCHED').sum()}"
    )

    print()

    print(
        "BEHAVIOR"
    )

    print("-" * 110)

    behavior_order = [
        "IMMEDIATE_FAVORABLE",
        "CONTINUING_REVERSAL",
        "REVERSAL_THEN_RECOVERY",
        "RECOVERY_THEN_REVERSAL",
        "MIXED",
        "INSUFFICIENT",
    ]

    for behavior_name in behavior_order:

        count = int(
            (
                out["behavior"]
                == behavior_name
            ).sum()
        )

        pct_value = (
            100.0 * count / len(out)
            if len(out)
            else 0.0
        )

        print(
            f"{behavior_name:30s}"
            f"{count:4d}"
            f" ({pct_value:6.2f}%)"
        )

    print()

    # --------------------------------------------------------------
    # BEHAVIOR × STAY/EXIT
    # --------------------------------------------------------------

    banner(
        "BEHAVIOR × STAY vs EXIT"
    )

    summary_rows = []

    for behavior_name, group in (
        out.groupby(
            "behavior",
            sort=False,
        )
    ):

        stay_better = int(
            (
                group["stay_vs_exit"]
                == "STAY_BETTER"
            ).sum()
        )

        exit_better = int(
            (
                group["stay_vs_exit"]
                == "EXIT_BETTER"
            ).sum()
        )

        same = int(
            (
                group["stay_vs_exit"]
                == "SAME"
            ).sum()
        )

        avg_v = group[
            "exit_now_pnl_pct"
        ].mean()

        avg_stay = group[
            "stay_actual_pnl_pct"
        ].mean()

        avg_delta = group[
            "stay_minus_exit_pct"
        ].mean()

        print(
            f"[{behavior_name}]"
        )

        print(
            f"  Events          : "
            f"{len(group)}"
        )

        print(
            f"  STAY better     : "
            f"{stay_better}"
        )

        print(
            f"  EXIT better     : "
            f"{exit_better}"
        )

        print(
            f"  Same            : "
            f"{same}"
        )

        print(
            f"  Avg EXIT P&L    : "
            f"{avg_v:.4f}%"
        )

        print(
            f"  Avg STAY P&L    : "
            f"{avg_stay:.4f}%"
        )

        print(
            f"  Avg STAY-EXIT   : "
            f"{avg_delta:.4f}%"
        )

        print()

        summary_rows.append(
            {
                "behavior": behavior_name,
                "events": len(group),
                "unique_trades": group[
                    "trade_id"
                ].nunique(),
                "stay_better": stay_better,
                "exit_better": exit_better,
                "same": same,
                "avg_exit_now_pnl_pct": avg_v,
                "avg_stay_actual_pnl_pct": avg_stay,
                "avg_stay_minus_exit_pct": avg_delta,
            }
        )

    summary = pd.DataFrame(
        summary_rows
    )

    summary.to_csv(
        OUT_SUMMARY,
        index=False,
    )

    # --------------------------------------------------------------
    # CASE BY CASE
    # --------------------------------------------------------------

    banner(
        "CASE-BY-CASE"
    )

    display_cols = [
        "case_id",
        "trade_id",
        "direction",
        "v_reversal_candle_utc",
        "exit_now_pnl_pct",
        "v_direction_5m",
        "v_direction_10m",
        "price_move_trade_dir_5m_pct",
        "price_move_trade_dir_10m_pct",
        "price_move_trade_dir_15m_pct",
        "price_move_trade_dir_30m_pct",
        "price_move_trade_dir_60m_pct",
        "behavior",
        "stay_actual_pnl_pct",
        "stay_minus_exit_pct",
        "stay_vs_exit",
        "match_status",
    ]

    display_cols = [
        c
        for c in display_cols
        if c in out.columns
    ]

    print(
        out[
            display_cols
        ].to_string(
            index=False
        )
    )

    # --------------------------------------------------------------
    # METADATA
    # --------------------------------------------------------------

    metadata = [
        "AIMn KISS Experiment #48",
        "Question: At an unprofitable V, is price noise or continuing reversal?",
        "",
        "Research only.",
        "No production strategy changes.",
        "No orders.",
        "No AI training.",
        "No threshold promotion.",
        "No re-entry simulation.",
        "",
        f"Experiment #46 source: {EXP46_FILE}",
        f"Raw 5-minute source: {RAW_FILE}",
        "",
        f"Events analyzed: {len(out)}",
        f"Exact V matches: {(out['match_status'] == 'MATCHED').sum()}",
        "",
        "CRITICAL TIMING:",
        "V timestamp comes from v_reversal_candle_utc.",
        "Post-V checkpoints are calculated from V itself.",
        "minutes_after_known is NOT used for post-V timing.",
        "",
        "Behavior classification uses only the direction",
        "of the first two completed candles after the V.",
        "No percentage threshold is used.",
    ]

    OUT_META.write_text(
        "\n".join(metadata)
        + "\n",
        encoding="utf-8",
    )

    banner(
        "OUTPUTS"
    )

    print(
        f"Events : {OUT_EVENTS}"
    )

    print(
        f"Summary: {OUT_SUMMARY}"
    )

    print(
        f"Meta   : {OUT_META}"
    )

    print()

    print(
        "Experiment #48 complete."
    )


if __name__ == "__main__":
    main()
