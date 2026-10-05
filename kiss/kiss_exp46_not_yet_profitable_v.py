#!/usr/bin/env python3
"""
AIMn KISS — Experiment #46
NOT-YET-PROFITABLE V: STAY vs EXIT

RESEARCH ONLY
-------------
No production strategy changes.
No orders.
No AI training.
No threshold promotion.
No re-entry simulation.

QUESTION
--------
A trade is already open.

A local favorable V / peak appears.

At the exact completed 5-minute candle where the reversal becomes
causally known, the trade is still at or below the profitability level.

Compare:

    EXIT NOW = P&L at the causal V reversal

    STAY     = actual eventual trade result when available

PRIMARY DATA SOURCE
-------------------
Raw 5-minute trade trajectory containing:

    case_id
    symbol
    direction
    transition_known_utc
    candle_utc
    open
    high
    low
    close

TRADE METADATA
--------------
The raw trajectory does not contain entry_price, so we separately
recover trade entry information from an existing trade/V-event CSV
containing:

    case_id
    entry_time_utc
    entry_price

When available we also use:

    exit_time_utc
    eventual_pnl_hindsight_pct

The Experiment #42 transitions CSV is preferred when present.

CAUSAL V DETECTION
------------------
A V reversal is recognized only on a completed 5-minute candle.

Because P&L is normalized for direction:

LONG:
    favorable move = P&L increases
    reversal        = next P&L decreases

SHORT:
    favorable move = P&L increases
    reversal        = next P&L decreases

Therefore the causal event is:

    previous candle P&L change > 0
    current candle P&L change  < 0

No future candle is used to decide that the V exists.

NOT-YET-PROFITABLE CONDITION
----------------------------
The event qualifies when:

    P&L at the causal reversal candle <= 0%

This is deliberately simple for the first pass.

We are NOT selecting or promoting a profitability threshold.

OUTPUT
------
events CSV
summary CSV
metadata TXT

The experiment describes what happened afterward.
It does NOT make a trading rule.
"""

from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "kiss" / "results"

OUTDIR = RESULTS / "exp46_not_yet_profitable_v"

# First clean research pass:
# "not-yet-profitable" means gross P&L <= 0%.
PROFITABILITY_LEVEL_PCT = 0.0


RAW_REQUIRED = {
    "case_id",
    "symbol",
    "direction",
    "transition_known_utc",
    "candle_utc",
    "open",
    "high",
    "low",
    "close",
}

TRADE_REQUIRED = {
    "case_id",
    "entry_time_utc",
    "entry_price",
}


def die(message: str) -> None:
    print("=" * 100)
    print("ERROR")
    print("=" * 100)
    print(message)
    sys.exit(1)


def safe_read_csv(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def score_raw_file(path: Path, columns: set[str]) -> int:
    score = 0

    name = path.name.lower()
    full = str(path).lower()

    if RAW_REQUIRED.issubset(columns):
        score += 100

    if "raw" in name:
        score += 30

    if "trajectory" in name:
        score += 40

    if "trade_trajectory" in name:
        score += 20

    if "nvda" in name:
        score += 10

    if "exp" in full:
        score += 2

    return score


def find_raw_trajectory() -> tuple[Path, pd.DataFrame]:
    if not RESULTS.exists():
        die(
            f"Results directory does not exist:\n"
            f"{RESULTS}"
        )

    candidates = []

    for path in RESULTS.rglob("*.csv"):
        df = safe_read_csv(path)

        if df is None:
            continue

        columns = set(df.columns)

        if RAW_REQUIRED.issubset(columns):
            score = score_raw_file(path, columns)
            candidates.append((score, path, df))

    if not candidates:
        die(
            "NO RAW 5-MINUTE TRAJECTORY CSV FOUND.\n\n"
            f"Required columns:\n"
            f"{sorted(RAW_REQUIRED)}\n\n"
            f"Searched under:\n{RESULTS}"
        )

    candidates.sort(
        key=lambda item: (-item[0], str(item[1]))
    )

    score, path, df = candidates[0]

    print("=" * 100)
    print("RAW 5-MINUTE TRAJECTORY")
    print("=" * 100)

    print(f"Selected: {path}")
    print(f"Rows:     {len(df):,}")
    print(f"Score:    {score}")

    print("\nActual columns:")
    print(list(df.columns))

    if len(candidates) > 1:
        print("\nOther matching raw trajectory files:")
        for score2, path2, df2 in candidates[1:6]:
            print(
                f"  score={score2:3d} "
                f"rows={len(df2):6d} "
                f"{path2}"
            )

    return path, df.copy()


def score_trade_file(path: Path, columns: set[str]) -> int:
    score = 0

    name = path.name.lower()
    full = str(path).lower()

    if TRADE_REQUIRED.issubset(columns):
        score += 100

    if {
        "exit_time_utc",
        "eventual_pnl_hindsight_pct",
    }.issubset(columns):
        score += 100

    if "exp42" in full:
        score += 80

    if "v_peak_divergence" in full:
        score += 80

    if "transitions" in name:
        score += 40

    if "trade" in name:
        score += 20

    return score


def find_trade_metadata() -> tuple[Path, pd.DataFrame]:
    candidates = []

    for path in RESULTS.rglob("*.csv"):
        df = safe_read_csv(path)

        if df is None:
            continue

        columns = set(df.columns)

        if TRADE_REQUIRED.issubset(columns):
            score = score_trade_file(path, columns)
            candidates.append((score, path, df))

    if not candidates:
        die(
            "RAW TRAJECTORY FOUND, BUT NO TRADE METADATA FILE FOUND.\n\n"
            "The raw trajectory does not contain entry_price.\n"
            "Without entry_price we cannot honestly determine whether the\n"
            "trade was profitable at the V.\n\n"
            f"Required trade columns:\n{sorted(TRADE_REQUIRED)}"
        )

    candidates.sort(
        key=lambda item: (-item[0], str(item[1]))
    )

    score, path, df = candidates[0]

    print("\n" + "=" * 100)
    print("TRADE METADATA")
    print("=" * 100)

    print(f"Selected: {path}")
    print(f"Rows:     {len(df):,}")
    print(f"Score:    {score}")

    print("\nActual columns:")
    print(list(df.columns))

    return path, df.copy()


def normalize_direction(value: object) -> str:
    text = str(value).strip().upper()

    if (
        text.startswith("LONG")
        or text in {
            "BUY",
            "BUY_LONG",
            "ENTER_LONG",
        }
    ):
        return "LONG"

    if (
        text.startswith("SHORT")
        or text in {
            "SELL",
            "SELL_SHORT",
            "ENTER_SHORT",
        }
    ):
        return "SHORT"

    return text


def prepare_trade_metadata(df: pd.DataFrame) -> pd.DataFrame:
    t = df.copy()

    t["case_id"] = t["case_id"].astype(str)

    t["entry_time_utc"] = pd.to_datetime(
        t["entry_time_utc"],
        errors="coerce",
        utc=True,
    )

    t["entry_price"] = pd.to_numeric(
        t["entry_price"],
        errors="coerce",
    )

    if "exit_time_utc" in t.columns:
        t["exit_time_utc"] = pd.to_datetime(
            t["exit_time_utc"],
            errors="coerce",
            utc=True,
        )

    if "eventual_pnl_hindsight_pct" in t.columns:
        t["eventual_pnl_hindsight_pct"] = pd.to_numeric(
            t["eventual_pnl_hindsight_pct"],
            errors="coerce",
        )

    if "direction" in t.columns:
        t["direction"] = t["direction"].map(
            normalize_direction
        )

    t = t.dropna(
        subset=[
            "case_id",
            "entry_time_utc",
            "entry_price",
        ]
    ).copy()

    t = t[t["entry_price"] > 0].copy()

    t = t.sort_values(
        [
            "case_id",
            "entry_time_utc",
        ]
    )

    # One stable trade record per case.
    # If a source contains several V rows for the same trade,
    # entry/exit information is normally repeated.
    agg = {
        "entry_time_utc": "first",
        "entry_price": "first",
    }

    for column in [
        "trade_id",
        "symbol",
        "direction",
        "exit_time_utc",
        "eventual_pnl_hindsight_pct",
    ]:
        if column in t.columns:
            agg[column] = "first"

    t = (
        t.groupby(
            "case_id",
            as_index=False,
        )
        .agg(agg)
    )

    return t


def prepare_raw_trajectory(
    df: pd.DataFrame,
) -> pd.DataFrame:
    r = df.copy()

    for column in [
        "case_id",
        "symbol",
        "direction",
    ]:
        r[column] = r[column].astype(str)

    r["direction"] = r["direction"].map(
        normalize_direction
    )

    # IMPORTANT:
    # Use the REAL column from the raw trajectory.
    r["transition_known_utc"] = pd.to_datetime(
        r["transition_known_utc"],
        errors="coerce",
        utc=True,
    )

    r["candle_utc"] = pd.to_datetime(
        r["candle_utc"],
        errors="coerce",
        utc=True,
    )

    for column in [
        "open",
        "high",
        "low",
        "close",
    ]:
        r[column] = pd.to_numeric(
            r[column],
            errors="coerce",
        )

    r = r.dropna(
        subset=[
            "case_id",
            "symbol",
            "direction",
            "transition_known_utc",
            "candle_utc",
            "close",
        ]
    ).copy()

    r = r[r["close"] > 0].copy()

    r = r.sort_values(
        [
            "case_id",
            "candle_utc",
        ]
    ).reset_index(drop=True)

    return r


def merge_real_trade_data(
    raw: pd.DataFrame,
    trades: pd.DataFrame,
) -> pd.DataFrame:

    merged = raw.merge(
        trades,
        on="case_id",
        how="left",
        suffixes=(
            "",
            "_trade",
        ),
    )

    # Raw trajectory remains the authority for direction.
    if "direction_trade" in merged.columns:

        replacement = (
            merged["direction"]
            .eq("")
            | ~merged["direction"].isin(
                [
                    "LONG",
                    "SHORT",
                ]
            )
        )

        merged.loc[
            replacement,
            "direction",
        ] = (
            merged.loc[
                replacement,
                "direction_trade",
            ]
            .map(normalize_direction)
        )

    return merged


def calculate_real_trade_pnl(
    merged: pd.DataFrame,
) -> pd.DataFrame:

    x = merged.copy()

    # Need a real entry.
    x = x.dropna(
        subset=[
            "entry_time_utc",
            "entry_price",
        ]
    ).copy()

    if x.empty:
        return x

    x["entry_time_utc"] = pd.to_datetime(
        x["entry_time_utc"],
        errors="coerce",
        utc=True,
    )

    x["candle_utc"] = pd.to_datetime(
        x["candle_utc"],
        errors="coerce",
        utc=True,
    )

    # Ignore trajectory candles that occurred before the actual trade entry.
    x = x[
        x["candle_utc"]
        >= x["entry_time_utc"]
    ].copy()

    if x.empty:
        return x

    long_mask = x["direction"].eq("LONG")

    short_mask = x["direction"].eq("SHORT")

    x["pnl_pct"] = pd.NA
    x["pnl_pct"] = x["pnl_pct"].astype("Float64")

    x.loc[
        long_mask,
        "pnl_pct",
    ] = (
        (
            x.loc[
                long_mask,
                "close",
            ]
            - x.loc[
                long_mask,
                "entry_price",
            ]
        )
        / x.loc[
            long_mask,
            "entry_price",
        ]
        * 100.0
    )

    x.loc[
        short_mask,
        "pnl_pct",
    ] = (
        (
            x.loc[
                short_mask,
                "entry_price",
            ]
            - x.loc[
                short_mask,
                "close",
            ]
        )
        / x.loc[
            short_mask,
            "entry_price",
        ]
        * 100.0
    )

    x = x.dropna(
        subset=["pnl_pct"]
    ).copy()

    return x


def detect_causal_not_yet_profitable_v(
    df: pd.DataFrame,
) -> pd.DataFrame:

    events = []

    for case_id, group in df.groupby(
        "case_id",
        sort=False,
    ):

        g = (
            group
            .sort_values("candle_utc")
            .reset_index(drop=True)
        )

        if len(g) < 3:
            continue

        pnl = (
            pd.to_numeric(
                g["pnl_pct"],
                errors="coerce",
            )
            .astype(float)
        )

        for i in range(
            2,
            len(g),
        ):

            p0 = pnl.iloc[i - 2]
            p1 = pnl.iloc[i - 1]
            p2 = pnl.iloc[i]

            if pd.isna(p0) or pd.isna(p1) or pd.isna(p2):
                continue

            previous_change = p1 - p0
            current_change = p2 - p1

            # ------------------------------------------------------------
            # CAUSAL V REVERSAL
            #
            # The previous candle moved favorably.
            # The current completed candle moved adversely.
            #
            # Therefore only at candle i do we know the local V
            # has started to reverse.
            # ------------------------------------------------------------

            if previous_change <= 0:
                continue

            if current_change >= 0:
                continue

            # The V is causally known here.
            causal_row = g.iloc[i]
            peak_row = g.iloc[i - 1]

            # ------------------------------------------------------------
            # NOT-YET-PROFITABLE
            #
            # Exact research condition:
            #
            # P&L at V reversal <= 0%
            # ------------------------------------------------------------

            if p2 > PROFITABILITY_LEVEL_PCT:
                continue

            events.append(
                {
                    "case_id": str(case_id),

                    "symbol": str(
                        causal_row["symbol"]
                    ),

                    "direction": str(
                        causal_row["direction"]
                    ),

                    "trade_id": (
                        causal_row["trade_id"]
                        if "trade_id"
                        in causal_row.index
                        else None
                    ),

                    "entry_time_utc": causal_row[
                        "entry_time_utc"
                    ],

                    "entry_price": float(
                        causal_row["entry_price"]
                    ),

                    "transition_known_utc": causal_row[
                        "transition_known_utc"
                    ],

                    # Candle where the V reversal
                    # becomes causally known.
                    "v_reversal_candle_utc": causal_row[
                        "candle_utc"
                    ],

                    # Candle that formed the local favorable peak.
                    "v_peak_candle_utc": peak_row[
                        "candle_utc"
                    ],

                    "pnl_two_candles_back_pct": float(
                        p0
                    ),

                    "pnl_before_v_pct": float(
                        p1
                    ),

                    "pnl_at_v_pct": float(
                        p2
                    ),

                    "v_reversal_change_pct": float(
                        current_change
                    ),

                    "profitability_level_pct": (
                        PROFITABILITY_LEVEL_PCT
                    ),

                    # EXIT NOW means we take this exact P&L.
                    "exit_now_pnl_pct": float(
                        p2
                    ),
                }
            )

    return pd.DataFrame(events)


def attach_actual_trade_outcome(
    events: pd.DataFrame,
    trades: pd.DataFrame,
) -> pd.DataFrame:

    if events.empty:
        return events

    columns = ["case_id"]

    for column in [
        "exit_time_utc",
        "eventual_pnl_hindsight_pct",
    ]:
        if column in trades.columns:
            columns.append(column)

    out = events.merge(
        trades[columns],
        on="case_id",
        how="left",
    )

    if (
        "eventual_pnl_hindsight_pct"
        in out.columns
    ):
        out[
            "stay_actual_pnl_pct"
        ] = pd.to_numeric(
            out[
                "eventual_pnl_hindsight_pct"
            ],
            errors="coerce",
        )
    else:
        out[
            "stay_actual_pnl_pct"
        ] = pd.NA

    out[
        "stay_minus_exit_pct"
    ] = (
        out[
            "stay_actual_pnl_pct"
        ]
        - out[
            "exit_now_pnl_pct"
        ]
    )

    def classify(value) -> str:

        if pd.isna(value):
            return "NO_ACTUAL_OUTCOME"

        if value > 0:
            return "STAY_FINISHED_HIGHER"

        if value < 0:
            return "STAY_FINISHED_LOWER"

        return "SAME"

    out[
        "stay_vs_exit"
    ] = out[
        "stay_minus_exit_pct"
    ].apply(classify)

    out[
        "stay_improved_vs_exit"
    ] = (
        out[
            "stay_minus_exit_pct"
        ] > 0
    )

    out[
        "stay_deteriorated_vs_exit"
    ] = (
        out[
            "stay_minus_exit_pct"
        ] < 0
    )

    return out


def write_outputs(
    events: pd.DataFrame,
    raw_path: Path,
    trade_path: Path,
) -> None:

    OUTDIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    events_path = (
        OUTDIR
        / "nvda_not_yet_profitable_v_events.csv"
    )

    summary_path = (
        OUTDIR
        / "nvda_not_yet_profitable_v_summary.csv"
    )

    metadata_path = (
        OUTDIR
        / "exp46_metadata.txt"
    )

    events.to_csv(
        events_path,
        index=False,
    )

    summary = []

    event_count = len(events)

    unique_cases = (
        events["case_id"].nunique()
        if event_count
        else 0
    )

    summary.append(
        {
            "metric": "events",
            "value": event_count,
        }
    )

    summary.append(
        {
            "metric": "unique_cases",
            "value": unique_cases,
        }
    )

    if event_count:

        summary.append(
            {
                "metric": "avg_exit_now_pnl_pct",
                "value": float(
                    events[
                        "exit_now_pnl_pct"
                    ].mean()
                ),
            }
        )

        summary.append(
            {
                "metric": "median_exit_now_pnl_pct",
                "value": float(
                    events[
                        "exit_now_pnl_pct"
                    ].median()
                ),
            }
        )

        actual = events[
            events[
                "stay_actual_pnl_pct"
            ].notna()
        ].copy()

        summary.append(
            {
                "metric": "cases_with_actual_outcome",
                "value": len(actual),
            }
        )

        if not actual.empty:

            summary.append(
                {
                    "metric": "avg_stay_actual_pnl_pct",
                    "value": float(
                        actual[
                            "stay_actual_pnl_pct"
                        ].mean()
                    ),
                }
            )

            summary.append(
                {
                    "metric": "median_stay_actual_pnl_pct",
                    "value": float(
                        actual[
                            "stay_actual_pnl_pct"
                        ].median()
                    ),
                }
            )

            summary.append(
                {
                    "metric": "avg_stay_minus_exit_pct",
                    "value": float(
                        actual[
                            "stay_minus_exit_pct"
                        ].mean()
                    ),
                }
            )

            summary.append(
                {
                    "metric": "stay_finished_higher_count",
                    "value": int(
                        (
                            actual[
                                "stay_vs_exit"
                            ]
                            == "STAY_FINISHED_HIGHER"
                        ).sum()
                    ),
                }
            )

            summary.append(
                {
                    "metric": "stay_finished_lower_count",
                    "value": int(
                        (
                            actual[
                                "stay_vs_exit"
                            ]
                            == "STAY_FINISHED_LOWER"
                        ).sum()
                    ),
                }
            )

            summary.append(
                {
                    "metric": "same_count",
                    "value": int(
                        (
                            actual[
                                "stay_vs_exit"
                            ]
                            == "SAME"
                        ).sum()
                    ),
                }
            )

    pd.DataFrame(
        summary
    ).to_csv(
        summary_path,
        index=False,
    )

    metadata = [
        "AIMn KISS — Experiment #46",
        "NOT-YET-PROFITABLE V: STAY vs EXIT",
        "",
        "RESEARCH ONLY",
        "No production strategy changes.",
        "No orders.",
        "No AI training.",
        "No threshold promotion.",
        "No re-entry simulation.",
        "",
        f"Raw trajectory: {raw_path}",
        f"Trade metadata: {trade_path}",
        "",
        f"Profitability level: "
        f"{PROFITABILITY_LEVEL_PCT:.6f}%",
        "",
        f"Events: {event_count}",
        f"Unique cases: {unique_cases}",
        "",
        "Causal V:",
        "previous P&L change > 0",
        "current P&L change < 0",
        "",
        "EXIT NOW = P&L at causal V reversal candle.",
        "STAY = actual eventual trade result when available.",
    ]

    metadata_path.write_text(
        "\n".join(metadata) + "\n",
        encoding="utf-8",
    )

    print("\n" + "=" * 100)
    print(
        "EXPERIMENT #46 — "
        "NOT-YET-PROFITABLE V: STAY vs EXIT"
    )
    print("=" * 100)

    print(
        f"Profitability level: "
        f"{PROFITABILITY_LEVEL_PCT:.4f}%"
    )

    print(
        f"Qualifying V events: {event_count}"
    )

    print(
        f"Unique cases: {unique_cases}"
    )

    if event_count == 0:

        print("\nNO QUALIFYING EVENTS")

        print(
            "\nThe raw 5-minute trajectory plus the "
            "real entry data produced no causal V "
            "reversal while the trade P&L was <= 0%."
        )

        print(
            "\nNothing was changed."
        )

    else:

        print(
            "\nAverage EXIT NOW P&L: "
            f"{events['exit_now_pnl_pct'].mean():.4f}%"
        )

        print(
            "Median EXIT NOW P&L:  "
            f"{events['exit_now_pnl_pct'].median():.4f}%"
        )

        actual = events[
            events[
                "stay_actual_pnl_pct"
            ].notna()
        ].copy()

        if not actual.empty:

            print(
                "\nActual STAY outcomes available: "
                f"{len(actual)}"
            )

            print(
                "Average STAY actual P&L: "
                f"{actual['stay_actual_pnl_pct'].mean():.4f}%"
            )

            print(
                "Average STAY minus EXIT: "
                f"{actual['stay_minus_exit_pct'].mean():.4f}%"
            )

            higher = (
                actual[
                    "stay_vs_exit"
                ]
                == "STAY_FINISHED_HIGHER"
            ).sum()

            lower = (
                actual[
                    "stay_vs_exit"
                ]
                == "STAY_FINISHED_LOWER"
            ).sum()

            same = (
                actual[
                    "stay_vs_exit"
                ]
                == "SAME"
            ).sum()

            print(
                f"STAY finished higher than EXIT: {higher}"
            )

            print(
                f"STAY finished lower than EXIT:  {lower}"
            )

            print(
                f"Same: {same}"
            )

        else:

            print(
                "\nNo actual eventual trade outcome "
                "was available."
            )

    print("\nOUTPUTS")
    print("-" * 100)

    print(
        f"Events : {events_path}"
    )

    print(
        f"Summary: {summary_path}"
    )

    print(
        f"Meta   : {metadata_path}"
    )


def main() -> None:

    # ------------------------------------------------------------
    # 1. Locate raw 5-minute trajectory.
    # ------------------------------------------------------------
    raw_path, raw = find_raw_trajectory()

    # ------------------------------------------------------------
    # 2. Locate real trade entry/outcome data.
    # ------------------------------------------------------------
    trade_path, trade_raw = find_trade_metadata()

    # ------------------------------------------------------------
    # 3. Prepare both sources.
    # ------------------------------------------------------------
    raw = prepare_raw_trajectory(
        raw
    )

    trades = prepare_trade_metadata(
        trade_raw
    )

    # ------------------------------------------------------------
    # 4. Join real trade information to raw 5-minute path.
    # ------------------------------------------------------------
    merged = merge_real_trade_data(
        raw,
        trades,
    )

    matched_cases = merged[
        merged["entry_time_utc"].notna()
        & merged["entry_price"].notna()
    ][
        "case_id"
    ].nunique()

    total_cases = merged[
        "case_id"
    ].nunique()

    print("\n" + "=" * 100)
    print("ENTRY METADATA MATCH")
    print("=" * 100)

    print(
        f"Raw cases:      {total_cases}"
    )

    print(
        f"Matched cases:  {matched_cases}"
    )

    print(
        f"Missing cases:  "
        f"{total_cases - matched_cases}"
    )

    if matched_cases == 0:
        die(
            "No raw trajectory cases matched "
            "real entry metadata."
        )

    # ------------------------------------------------------------
    # 5. Calculate actual trade P&L candle by candle.
    # ------------------------------------------------------------
    merged = calculate_real_trade_pnl(
        merged
    )

    if merged.empty:
        die(
            "No usable 5-minute candles remained "
            "after applying the real trade entry time."
        )

    # ------------------------------------------------------------
    # 6. Detect causal V reversals while P&L <= 0%.
    # ------------------------------------------------------------
    events = detect_causal_not_yet_profitable_v(
        merged
    )

    # ------------------------------------------------------------
    # 7. Attach actual eventual trade outcome.
    # ------------------------------------------------------------
    events = attach_actual_trade_outcome(
        events,
        trades,
    )

    # ------------------------------------------------------------
    # 8. Keep this experiment on NVDA.
    #    This preserves the current #42-45 research sequence.
    # ------------------------------------------------------------
    if "symbol" in events.columns:

        before = len(events)

        events = events[
            events[
                "symbol"
            ]
            .astype(str)
            .str.upper()
            .eq("NVDA")
        ].copy()

        removed = before - len(events)

        if removed:
            print(
                f"\nNVDA scope filter removed "
                f"{removed} non-NVDA events."
            )

    # ------------------------------------------------------------
    # 9. Write research outputs.
    # ------------------------------------------------------------
    write_outputs(
        events,
        raw_path,
        trade_path,
    )


if __name__ == "__main__":
    main()
