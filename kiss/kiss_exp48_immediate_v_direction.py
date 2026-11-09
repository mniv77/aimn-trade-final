#!/usr/bin/env python3

"""
AIMn KISS — Experiment #48
UNPROFITABLE V: IMMEDIATE POST-V PRICE DIRECTION

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

    Is the reversal continuing against the trade?

or

    Is price turning back toward the trade?

METHOD
------
Experiment #46 identifies the qualifying unprofitable V events.

Experiment #42 supplies the exact causal V timestamp.

The RAW 5-MINUTE TRAJECTORY supplies:

    V candle
    first completed 5m candle after V
    second completed 5m candle after V

We do NOT guess the V timestamp from price.

We require an exact timestamp match.

INTERPRETATION
--------------
For each of the first two candles after V:

    ADVERSE
        price movement hurts the open trade

    FAVORABLE
        price movement helps the open trade

Then:

    ADVERSE + ADVERSE
        CONTINUING_REVERSAL

    FAVORABLE + FAVORABLE
        TURNING_BACK_TOWARD_TRADE

    anything else
        MIXED_DIRECTION

This deliberately uses no percentage threshold.
"""

from pathlib import Path
import sys
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE = Path("/home/MeirNiv/aimn-trade-final")

EXP46 = (
    BASE
    / "kiss/results/exp46_not_yet_profitable_v/"
    / "nvda_not_yet_profitable_v_events.csv"
)

EXP42 = (
    BASE
    / "kiss/results/exp42_v_peak_divergence/"
    / "nvda_v_peak_divergence_transitions.csv"
)

RAW = (
    BASE
    / "kiss/results/exp32_raw_candle_v_geometry/"
    / "raw_v_trajectory.csv"
)

OUTDIR = BASE / "kiss/results/exp48_immediate_v_direction"

OUT_EVENTS = (
    OUTDIR / "nvda_unprofitable_v_immediate_direction_events.csv"
)

OUT_SUMMARY = (
    OUTDIR / "nvda_unprofitable_v_immediate_direction_summary.csv"
)

OUT_META = OUTDIR / "exp48_metadata.txt"


# ============================================================
# HELPERS
# ============================================================

def require_columns(df, required, name):
    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            f"{name} is missing required columns: {missing}\n"
            f"Actual columns: {list(df.columns)}"
        )


def to_utc(series):
    return pd.to_datetime(
        series,
        utc=True,
        errors="coerce"
    )


def classify_move(value):
    if pd.isna(value):
        return "INSUFFICIENT"

    if value < 0:
        return "ADVERSE"

    if value > 0:
        return "FAVORABLE"

    return "FLAT"


def classify_path(first_move, second_move):

    if pd.isna(first_move) or pd.isna(second_move):
        return "INSUFFICIENT"

    if first_move < 0 and second_move < 0:
        return "CONTINUING_REVERSAL"

    if first_move > 0 and second_move > 0:
        return "TURNING_BACK_TOWARD_TRADE"

    return "MIXED_DIRECTION"


def outcome_text(diff):

    if pd.isna(diff):
        return "UNAVAILABLE"

    if diff > 0:
        return "STAY_BETTER"

    if diff < 0:
        return "EXIT_BETTER"

    return "SAME"


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 110)
    print(
        "AIMn KISS — EXPERIMENT #48 "
        "UNPROFITABLE V: IMMEDIATE POST-V PRICE DIRECTION"
    )
    print("=" * 110)

    print("Research only.")
    print("No production strategy changes.")
    print("No orders.")
    print("No AI.")
    print("No threshold promotion.")
    print()

    # --------------------------------------------------------
    # VERIFY FILES
    # --------------------------------------------------------

    for path, label in [
        (EXP46, "Experiment #46 events"),
        (EXP42, "Experiment #42 V metadata"),
        (RAW, "Raw 5-minute trajectory"),
    ]:

        if not path.exists():
            raise FileNotFoundError(
                f"{label} not found:\n{path}"
            )

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    events = pd.read_csv(EXP46)
    vmeta = pd.read_csv(EXP42)
    raw = pd.read_csv(RAW)

    require_columns(
        events,
        ["case_id"],
        "Experiment #46 event file"
    )

    require_columns(
        vmeta,
        [
            "case_id",
            "event_time_utc",
            "direction",
        ],
        "Experiment #42 V metadata"
    )

    require_columns(
        raw,
        [
            "case_id",
            "candle_utc",
            "close",
        ],
        "Raw 5-minute trajectory"
    )

    print(
        f"Experiment #46 qualifying events: {len(events)}"
    )

    print(
        f"Experiment #42 V metadata rows:    {len(vmeta)}"
    )

    print(
        f"Raw 5-minute rows:                 {len(raw):,}"
    )

    print()

    # --------------------------------------------------------
    # NORMALIZE EVENT FILE
    # --------------------------------------------------------

    events["case_id"] = (
        events["case_id"]
        .astype(str)
        .str.strip()
    )

    # EXIT NOW VALUE
    #
    # Prefer the explicit exit_now column if present.
    # Otherwise use pnl_at_v_pct.

    if "exit_now_pnl_pct" in events.columns:

        events["exit_now_pnl_pct"] = pd.to_numeric(
            events["exit_now_pnl_pct"],
            errors="coerce"
        )

    elif "pnl_at_v_pct" in events.columns:

        events["exit_now_pnl_pct"] = pd.to_numeric(
            events["pnl_at_v_pct"],
            errors="coerce"
        )

    else:

        events["exit_now_pnl_pct"] = float("nan")

    # STAY VALUE

    if "eventual_pnl_hindsight_pct" in events.columns:

        events["stay_actual_pnl_pct"] = pd.to_numeric(
            events["eventual_pnl_hindsight_pct"],
            errors="coerce"
        )

    else:

        events["stay_actual_pnl_pct"] = float("nan")

    # --------------------------------------------------------
    # NORMALIZE #42 METADATA
    # --------------------------------------------------------

    vmeta["case_id"] = (
        vmeta["case_id"]
        .astype(str)
        .str.strip()
    )

    vmeta["event_time_utc"] = to_utc(
        vmeta["event_time_utc"]
    )

    vmeta["direction"] = (
        vmeta["direction"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Keep exactly one V metadata row per case.
    vmap_cols = [
        "case_id",
        "event_time_utc",
        "direction",
    ]

    if "trade_id" in vmeta.columns:
        vmap_cols.append("trade_id")

    vmap = (
        vmeta[vmap_cols]
        .dropna(subset=["event_time_utc"])
        .drop_duplicates(
            subset=["case_id"],
            keep="first"
        )
        .copy()
    )

    # --------------------------------------------------------
    # NORMALIZE RAW TRAJECTORY
    # --------------------------------------------------------

    raw["case_id"] = (
        raw["case_id"]
        .astype(str)
        .str.strip()
    )

    raw["candle_utc"] = to_utc(
        raw["candle_utc"]
    )

    raw["close"] = pd.to_numeric(
        raw["close"],
        errors="coerce"
    )

    raw = raw.dropna(
        subset=[
            "case_id",
            "candle_utc",
            "close",
        ]
    ).copy()

    # --------------------------------------------------------
    # JOIN #46 -> #42
    # --------------------------------------------------------

    df = events.merge(
        vmap,
        on="case_id",
        how="left",
        suffixes=("", "_vmeta")
    )

    # Direction from #46 if present,
    # otherwise from #42.

    if "direction" not in events.columns:

        df["direction"] = df["direction_vmeta"]

    else:

        df["direction"] = (
            df["direction"]
            .fillna(df["direction_vmeta"])
            .astype(str)
            .str.upper()
        )

    missing_times = (
        df.loc[
            df["event_time_utc"].isna(),
            "case_id"
        ]
        .tolist()
    )

    if missing_times:

        raise ValueError(
            "Could not recover the exact V timestamp "
            "from Experiment #42 for these #46 cases:\n"
            + "\n".join(
                str(x) for x in missing_times
            )
        )

    print(
        "Exact V timestamps recovered from Experiment #42."
    )

    print()

    # --------------------------------------------------------
    # BUILD IMMEDIATE POST-V PATH
    # --------------------------------------------------------

    rows = []

    for _, event in df.iterrows():

        case_id = event["case_id"]

        event_time = event["event_time_utc"]

        direction = str(
            event["direction"]
        ).upper()

        if direction == "LONG":
            trade_sign = 1.0

        elif direction == "SHORT":
            trade_sign = -1.0

        else:

            rows.append({
                **event.to_dict(),

                "error":
                    f"Unknown direction: {direction}",

                "path_class":
                    "INSUFFICIENT",
            })

            continue

        # ----------------------------------------------------
        # RAW CASE
        # ----------------------------------------------------

        case_raw = (
            raw[
                raw["case_id"] == case_id
            ]
            .sort_values("candle_utc")
            .reset_index(drop=True)
        )

        if case_raw.empty:

            rows.append({
                **event.to_dict(),

                "error":
                    "No raw trajectory rows for case",

                "path_class":
                    "INSUFFICIENT",
            })

            continue

        # ----------------------------------------------------
        # EXACT V CANDLE
        # ----------------------------------------------------

        matching = case_raw.index[
            case_raw["candle_utc"] == event_time
        ].tolist()

        if not matching:

            rows.append({
                **event.to_dict(),

                "error":
                    (
                        "No exact raw 5m candle at "
                        f"V time {event_time}"
                    ),

                "path_class":
                    "INSUFFICIENT",
            })

            continue

        v_index = matching[0]

        # Need V + two completed candles afterward.

        if v_index + 2 >= len(case_raw):

            rows.append({
                **event.to_dict(),

                "error":
                    "Fewer than two completed 5m candles after V",

                "path_class":
                    "INSUFFICIENT",
            })

            continue

        # ----------------------------------------------------
        # CANDLES
        # ----------------------------------------------------

        v = case_raw.iloc[v_index]

        n1 = case_raw.iloc[v_index + 1]

        n2 = case_raw.iloc[v_index + 2]

        v_close = float(v["close"])

        n1_close = float(n1["close"])

        n2_close = float(n2["close"])

        # ----------------------------------------------------
        # RAW PRICE MOVES
        # ----------------------------------------------------

        raw_move_1 = (
            (n1_close / v_close) - 1.0
        ) * 100.0

        raw_move_2 = (
            (n2_close / n1_close) - 1.0
        ) * 100.0

        # ----------------------------------------------------
        # TRADE-RELATIVE MOVES
        #
        # LONG:
        #   price up    = favorable
        #   price down  = adverse
        #
        # SHORT:
        #   price down  = favorable
        #   price up    = adverse
        # ----------------------------------------------------

        pnl_move_1 = (
            raw_move_1 * trade_sign
        )

        pnl_move_2 = (
            raw_move_2 * trade_sign
        )

        cumulative_move_10m = (
            (
                (n2_close / v_close) - 1.0
            )
            * 100.0
            * trade_sign
        )

        # ----------------------------------------------------
        # STAY VS EXIT
        # ----------------------------------------------------

        exit_now = event["exit_now_pnl_pct"]

        stay = event["stay_actual_pnl_pct"]

        if pd.notna(exit_now) and pd.notna(stay):

            stay_minus_exit = (
                float(stay) - float(exit_now)
            )

        else:

            stay_minus_exit = float("nan")

        # ----------------------------------------------------
        # SAVE ROW
        # ----------------------------------------------------

        rows.append({

            **event.to_dict(),

            "v_event_time_utc":
                event_time,

            "v_candle_utc":
                v["candle_utc"],

            "v_close":
                v_close,

            "next1_candle_utc":
                n1["candle_utc"],

            "next1_close":
                n1_close,

            "next2_candle_utc":
                n2["candle_utc"],

            "next2_close":
                n2_close,

            "next1_minutes_after_v":
                (
                    n1["candle_utc"] - event_time
                ).total_seconds() / 60.0,

            "next2_minutes_after_v":
                (
                    n2["candle_utc"] - event_time
                ).total_seconds() / 60.0,

            "raw_price_move_v_to_next1_pct":
                raw_move_1,

            "raw_price_move_next1_to_next2_pct":
                raw_move_2,

            "trade_pnl_move_v_to_next1_pct":
                pnl_move_1,

            "trade_pnl_move_next1_to_next2_pct":
                pnl_move_2,

            "trade_pnl_cumulative_v_to_next2_pct":
                cumulative_move_10m,

            "first_move":
                classify_move(pnl_move_1),

            "second_move":
                classify_move(pnl_move_2),

            "path_class":
                classify_path(
                    pnl_move_1,
                    pnl_move_2
                ),

            "stay_minus_exit_pct":
                stay_minus_exit,

            "historically_better":
                outcome_text(
                    stay_minus_exit
                ),

            "error":
                "",
        })

    out = pd.DataFrame(rows)

    # --------------------------------------------------------
    # SAVE EVENTS
    # --------------------------------------------------------

    OUTDIR.mkdir(
        parents=True,
        exist_ok=True
    )

    out.to_csv(
        OUT_EVENTS,
        index=False
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    valid = out[
        out["path_class"] != "INSUFFICIENT"
    ].copy()

    print("=" * 110)
    print("EXPERIMENT #48 — CORE RESULT")
    print("=" * 110)

    print(
        f"Unprofitable V events: {len(out)}"
    )

    print(
        f"Usable immediate paths: {len(valid)}"
    )

    print()

    categories = [
        "CONTINUING_REVERSAL",
        "TURNING_BACK_TOWARD_TRADE",
        "MIXED_DIRECTION",
        "INSUFFICIENT",
    ]

    for category in categories:

        n = int(
            (
                out["path_class"] == category
            ).sum()
        )

        pct = (
            100.0 * n / len(out)
            if len(out)
            else 0.0
        )

        print(
            f"{category:34s}"
            f"{n:3d} "
            f"({pct:6.2f}%)"
        )

    # --------------------------------------------------------
    # CASE-BY-CASE
    # --------------------------------------------------------

    print()
    print("=" * 110)
    print("CASE-BY-CASE")
    print("=" * 110)

    display_cols = [

        "case_id",

        "trade_id",

        "direction",

        "v_event_time_utc",

        "exit_now_pnl_pct",

        "stay_actual_pnl_pct",

        "stay_minus_exit_pct",

        "first_move",

        "second_move",

        "path_class",

        "trade_pnl_cumulative_v_to_next2_pct",

        "historically_better",
    ]

    display_cols = [
        c
        for c in display_cols
        if c in out.columns
    ]

    print(
        out[display_cols]
        .to_string(index=False)
    )

    # --------------------------------------------------------
    # BEHAVIOR x STAY/EXIT
    # --------------------------------------------------------

    print()
    print("=" * 110)
    print("BEHAVIOR × STAY vs EXIT")
    print("=" * 110)

    if len(valid):

        for category, group in (
            valid.groupby(
                "path_class",
                sort=False
            )
        ):

            stay_better = int(
                (
                    group["stay_minus_exit_pct"]
                    > 0
                ).sum()
            )

            exit_better = int(
                (
                    group["stay_minus_exit_pct"]
                    < 0
                ).sum()
            )

            same = int(
                (
                    group["stay_minus_exit_pct"]
                    == 0
                ).sum()
            )

            avg_diff = (
                group["stay_minus_exit_pct"]
                .mean()
            )

            print(
                f"{category:34s}"
                f"n={len(group):2d} "
                f"STAY={stay_better} "
                f"EXIT={exit_better} "
                f"SAME={same} "
                f"avg(STAY-EXIT)="
                f"{avg_diff:+.4f}%"
            )

    else:

        print(
            "No usable immediate paths."
        )

    # --------------------------------------------------------
    # DIRECTION CHECK
    # --------------------------------------------------------

    print()
    print("=" * 110)
    print("DIRECTION CHECK")
    print("=" * 110)

    if len(valid):

        for direction, group in (
            valid.groupby(
                "direction",
                sort=False
            )
        ):

            avg1 = (
                group[
                    "trade_pnl_move_v_to_next1_pct"
                ].mean()
            )

            avg2 = (
                group[
                    "trade_pnl_move_next1_to_next2_pct"
                ].mean()
            )

            print(
                f"{direction:6s}"
                f" n={len(group):2d} "
                f"avg first trade-move="
                f"{avg1:+.4f}% "
                f"avg second trade-move="
                f"{avg2:+.4f}%"
            )

    else:

        print(
            "No usable immediate paths."
        )

    # --------------------------------------------------------
    # SUMMARY CSV
    # --------------------------------------------------------

    summary_rows = []

    for category, group in (
        out.groupby(
            "path_class",
            sort=False
        )
    ):

        summary_rows.append({

            "path_class":
                category,

            "events":
                len(group),

            "unique_cases":
                group["case_id"].nunique(),

            "stay_better":
                int(
                    (
                        group[
                            "stay_minus_exit_pct"
                        ] > 0
                    ).sum()
                ),

            "exit_better":
                int(
                    (
                        group[
                            "stay_minus_exit_pct"
                        ] < 0
                    ).sum()
                ),

            "same":
                int(
                    (
                        group[
                            "stay_minus_exit_pct"
                        ] == 0
                    ).sum()
                ),

            "avg_first_trade_move_pct":
                group[
                    "trade_pnl_move_v_to_next1_pct"
                ].mean(),

            "avg_second_trade_move_pct":
                group[
                    "trade_pnl_move_next1_to_next2_pct"
                ].mean(),

            "avg_stay_minus_exit_pct":
                group[
                    "stay_minus_exit_pct"
                ].mean(),
        })

    summary = pd.DataFrame(
        summary_rows
    )

    summary.to_csv(
        OUT_SUMMARY,
        index=False
    )

    # --------------------------------------------------------
    # METADATA
    # --------------------------------------------------------

    with open(
        OUT_META,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "AIMn KISS — Experiment #48\n"
        )

        f.write(
            "Question: immediate post-V direction "
            "at an unprofitable V\n"
        )

        f.write(
            "Experiment #46 identifies qualifying events.\n"
        )

        f.write(
            "Experiment #42 supplies exact V timestamp.\n"
        )

        f.write(
            "Raw 5m trajectory supplies V + next "
            "two completed candles.\n"
        )

        f.write(
            "Exact timestamp matching only.\n"
        )

        f.write(
            "No timestamp guessing.\n"
        )

        f.write(
            "No production changes.\n"
        )

        f.write(
            "No orders.\n"
        )

        f.write(
            "No AI.\n"
        )

        f.write(
            "No threshold promotion.\n"
        )

        f.write(
            f"Events: {len(out)}\n"
        )

        f.write(
            f"Usable immediate paths: {len(valid)}\n"
        )

    # --------------------------------------------------------
    # OUTPUTS
    # --------------------------------------------------------

    print()
    print("=" * 110)
    print("OUTPUTS")
    print("=" * 110)

    print(
        f"Events : {OUT_EVENTS}"
    )

    print(
        f"Summary: {OUT_SUMMARY}"
    )

    print(
        f"Meta   : {OUT_META}"
    )

    print("=" * 110)


if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print("=" * 110)
        print("ERROR")
        print("=" * 110)
        print(str(exc))

        sys.exit(1)
