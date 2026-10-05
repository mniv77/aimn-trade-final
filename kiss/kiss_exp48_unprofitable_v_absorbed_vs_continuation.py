#!/usr/bin/env python3

"""
AIMn KISS — Experiment #48
UNPROFITABLE V: ABSORBED vs CONTINUING REVERSAL

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

    Does the adverse move get absorbed
    and the trade recover?

or:

    Does the reversal continue
    against the trade?

DATA DESIGN
-----------
1. Experiment #46 identifies the qualifying causal V events.
2. RAW 5-minute trajectory is then used to inspect what happened
   after each exact V candle.

The raw trajectory is the source of truth for the post-V path.

NO PRICE-LOSS THRESHOLD
-----------------------
We do not choose a percentage such as 0.10%, 0.20%, etc.

We observe the actual sequence of P&L changes:

    V
    +5m
    +10m
    +15m
    +30m
    +60m

The descriptive labels are exploratory only.

DESCRIPTIVE STATES
------------------
ABSORBED_RECOVERY
    The trade initially suffers or remains weak, then P&L improves
    for a sustained sequence and finishes above the V P&L.

CONTINUING_REVERSAL
    P&L continues deteriorating for a sustained sequence and finishes
    below the V P&L.

MIXED
    Neither pattern is cleanly established.

INSUFFICIENT
    Not enough future 5-minute data is available.

STAY vs EXIT
------------
EXIT NOW
    P&L at the causal V candle.

STAY
    Actual eventual trade P&L from Experiment #46.

This is hindsight research only.
It is NOT a trading rule.
"""

from pathlib import Path
import pandas as pd
import numpy as np


# ============================================================================
# PATHS
# ============================================================================

ROOT = Path("kiss")

RAW_TRAJECTORY = (
    ROOT
    / "results"
    / "exp32_raw_candle_v_geometry"
    / "raw_v_trajectory.csv"
)

EXP46_DIR = ROOT / "results" / "exp46_not_yet_profitable_v"

OUTPUT_DIR = ROOT / "results" / "exp48_unprofitable_v_absorbed_vs_continuation"

OUTPUT_EVENTS = (
    OUTPUT_DIR
    / "nvda_unprofitable_v_absorbed_vs_continuation_events.csv"
)

OUTPUT_SUMMARY = (
    OUTPUT_DIR
    / "nvda_unprofitable_v_absorbed_vs_continuation_summary.csv"
)

OUTPUT_META = OUTPUT_DIR / "exp48_metadata.txt"


# ============================================================================
# HELPERS
# ============================================================================

def find_exp46_events() -> Path:
    """
    Find the real Experiment #46 event file.

    We intentionally do not assume one exact filename so this experiment
    does not break because of a harmless filename variation.
    """

    candidates = [
        EXP46_DIR / "nvda_not_yet_profitable_v_events.csv",
        EXP46_DIR / "not_yet_profitable_v_events.csv",
    ]

    for path in candidates:
        if path.exists():
            return path

    discovered = sorted(
        EXP46_DIR.glob("*not*yet*profitable*v*events*.csv")
    )

    if discovered:
        return discovered[0]

    raise FileNotFoundError(
        "\nExperiment #46 event file was not found.\n"
        f"Expected directory:\n{EXP46_DIR.resolve()}\n"
        "Looked for:\n"
        "  nvda_not_yet_profitable_v_events.csv\n"
        "  not_yet_profitable_v_events.csv\n"
    )


def require_columns(df: pd.DataFrame, required, label: str):
    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            f"\n{label} is missing required columns:\n"
            f"  {missing}\n"
            f"\nActual columns:\n"
            f"  {list(df.columns)}"
        )


def to_utc(series: pd.Series) -> pd.Series:
    """
    Convert timestamps into timezone-aware UTC.

    The raw research trajectory is intended to be UTC.
    utc=True ensures consistent comparison of timestamps.
    """
    return pd.to_datetime(series, errors="coerce", utc=True)


def trade_pnl_pct(direction: str, entry_price: float, close_price: float) -> float:
    """
    Mark-to-market P&L percentage from entry.

    LONG:
        close / entry - 1

    SHORT:
        entry / close - 1
    """

    if not np.isfinite(entry_price):
        return np.nan

    if not np.isfinite(close_price) or close_price <= 0:
        return np.nan

    d = str(direction).upper().strip()

    if d == "LONG":
        return ((close_price / entry_price) - 1.0) * 100.0

    if d == "SHORT":
        return ((entry_price / close_price) - 1.0) * 100.0

    return np.nan


def get_future_row(
    raw_case: pd.DataFrame,
    event_time: pd.Timestamp,
    minutes_forward: int,
):
    """
    Return the first completed raw 5-minute candle at or after the requested
    future offset.
    """

    target = event_time + pd.Timedelta(minutes=minutes_forward)

    future = raw_case[raw_case["candle_utc"] >= target]

    if future.empty:
        return None

    row = future.iloc[0]

    actual_minutes = (
        row["candle_utc"] - event_time
    ).total_seconds() / 60.0

    return row, actual_minutes


def classify_sequence(values):
    """
    Exploratory qualitative classification.

    No percentage threshold is used.

    We inspect direction of consecutive P&L movement.

    ABSORBED_RECOVERY:
        At least one weak/adverse move followed by a clean sequence
        of improvement, finishing above the V P&L.

    CONTINUING_REVERSAL:
        A clean sequence of deterioration with the final observation
        below the V P&L.

    MIXED:
        Everything else.

    INSUFFICIENT:
        Too few observations.
    """

    # values dictionary:
    # "v", "5m", "10m", "15m", "30m", "60m"

    ordered = []

    for label in ["v", "5m", "10m", "15m", "30m", "60m"]:
        value = values.get(label)

        if value is not None and np.isfinite(value):
            ordered.append((label, float(value)))

    if len(ordered) < 3:
        return "INSUFFICIENT"

    pnls = [x[1] for x in ordered]

    # Consecutive changes.
    changes = np.diff(pnls)

    positive = changes > 0
    negative = changes < 0

    # ----------------------------------------------------------------------
    # Look for an adverse move followed by sustained recovery.
    # ----------------------------------------------------------------------

    recovery_found = False

    for i in range(len(changes) - 2):
        if (
            changes[i] < 0
            and changes[i + 1] > 0
            and changes[i + 2] > 0
        ):
            recovery_found = True
            break

    if recovery_found and pnls[-1] > pnls[0]:
        return "ABSORBED_RECOVERY"

    # ----------------------------------------------------------------------
    # Look for sustained deterioration.
    # ----------------------------------------------------------------------

    continuation_found = False

    for i in range(len(changes) - 2):
        if (
            changes[i] < 0
            and changes[i + 1] < 0
            and changes[i + 2] < 0
        ):
            continuation_found = True
            break

    if continuation_found and pnls[-1] < pnls[0]:
        return "CONTINUING_REVERSAL"

    return "MIXED"


# ============================================================================
# LOAD DATA
# ============================================================================

def main():

    print("=" * 110)
    print("AIMn KISS — EXPERIMENT #48")
    print("UNPROFITABLE V: ABSORBED vs CONTINUING REVERSAL")
    print("=" * 110)
    print("Research only.")
    print("No production strategy changes.")
    print("No orders.")
    print("No AI.")
    print("No threshold promotion.")
    print("No re-entry simulation.")

    # ----------------------------------------------------------------------
    # Locate files.
    # ----------------------------------------------------------------------

    exp46_path = find_exp46_events()

    if not RAW_TRAJECTORY.exists():
        raise FileNotFoundError(
            "\nRAW 5-minute trajectory was not found:\n"
            f"{RAW_TRAJECTORY.resolve()}"
        )

    print("\n" + "=" * 110)
    print("INPUT FILES")
    print("=" * 110)

    print(f"Experiment #46 events:")
    print(f"  {exp46_path.resolve()}")

    print(f"\nRaw 5-minute trajectory:")
    print(f"  {RAW_TRAJECTORY.resolve()}")

    # ----------------------------------------------------------------------
    # Read.
    # ----------------------------------------------------------------------

    events = pd.read_csv(exp46_path)
    raw = pd.read_csv(RAW_TRAJECTORY)

    print(f"\n#46 rows : {len(events):,}")
    print(f"RAW rows : {len(raw):,}")

    # ----------------------------------------------------------------------
    # Validate #46.
    # ----------------------------------------------------------------------

    required_event_columns = [
        "case_id",
        "direction",
        "event_time_utc",
        "pnl_at_v_pct",
        "eventual_pnl_hindsight_pct",
    ]

    require_columns(
        events,
        required_event_columns,
        "Experiment #46 event file",
    )

    # ----------------------------------------------------------------------
    # Validate raw trajectory.
    # ----------------------------------------------------------------------

    required_raw_columns = [
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
    ]

    require_columns(
        raw,
        required_raw_columns,
        "RAW 5-minute trajectory",
    )

    # ----------------------------------------------------------------------
    # Parse timestamps.
    # ----------------------------------------------------------------------

    events["event_time_utc"] = to_utc(events["event_time_utc"])
    raw["candle_utc"] = to_utc(raw["candle_utc"])

    events = events.dropna(subset=["event_time_utc"]).copy()
    raw = raw.dropna(subset=["candle_utc"]).copy()

    # ----------------------------------------------------------------------
    # Numeric conversion.
    # ----------------------------------------------------------------------

    for col in [
        "pnl_at_v_pct",
        "eventual_pnl_hindsight_pct",
        "entry_price",
    ]:
        if col in events.columns:
            events[col] = pd.to_numeric(
                events[col],
                errors="coerce",
            )

    for col in ["open", "high", "low", "close"]:
        raw[col] = pd.to_numeric(
            raw[col],
            errors="coerce",
        )

    # ----------------------------------------------------------------------
    # Only qualifying events from #46.
    # ----------------------------------------------------------------------

    if "exit_now_pnl_pct" in events.columns:
        events["exit_now_pnl_used_pct"] = pd.to_numeric(
            events["exit_now_pnl_pct"],
            errors="coerce",
        )
    else:
        events["exit_now_pnl_used_pct"] = pd.to_numeric(
            events["pnl_at_v_pct"],
            errors="coerce",
        )

    events = events[
        events["exit_now_pnl_used_pct"].notna()
    ].copy()

    print("\n" + "=" * 110)
    print("QUALIFYING V EVENTS")
    print("=" * 110)

    print(f"Events : {len(events)}")
    print(
        f"Unique cases : "
        f"{events['case_id'].nunique()}"
    )

    if events.empty:
        print("\nNo qualifying events.")
        return

    # =========================================================================
    # RAW TRAJECTORY ANALYSIS
    # =========================================================================

    records = []

    offsets = [5, 10, 15, 30, 60]

    for _, event in events.iterrows():

        case_id = event["case_id"]
        direction = str(event["direction"]).upper().strip()
        event_time = event["event_time_utc"]

        raw_case = raw[
            raw["case_id"].astype(str) == str(case_id)
        ].copy()

        if raw_case.empty:
            print(
                f"\nWARNING: no raw trajectory found for case {case_id}"
            )
            continue

        raw_case = raw_case.sort_values("candle_utc")

        # -------------------------------------------------------------
        # Entry price.
        # -------------------------------------------------------------

        entry_price = event.get("entry_price", np.nan)

        if pd.isna(entry_price):
            print(
                f"\nWARNING: entry_price missing for {case_id}; "
                f"cannot derive raw P&L."
            )
            continue

        try:
            entry_price = float(entry_price)
        except Exception:
            continue

        # -------------------------------------------------------------
        # Find the causal V candle itself.
        # -------------------------------------------------------------

        event_candidates = raw_case[
            raw_case["candle_utc"] >= event_time
        ]

        if event_candidates.empty:
            print(
                f"\nWARNING: no raw candle found at/after V for {case_id}"
            )
            continue

        event_row = event_candidates.iloc[0]

        event_raw_time = event_row["candle_utc"]

        event_close = float(event_row["close"])

        raw_v_pnl = trade_pnl_pct(
            direction,
            entry_price,
            event_close,
        )

        # -------------------------------------------------------------
        # Future trajectory.
        # -------------------------------------------------------------

        values = {
            "v": raw_v_pnl,
            "5m": np.nan,
            "10m": np.nan,
            "15m": np.nan,
            "30m": np.nan,
            "60m": np.nan,
        }

        actual_minutes = {
            "5m": np.nan,
            "10m": np.nan,
            "15m": np.nan,
            "30m": np.nan,
            "60m": np.nan,
        }

        close_values = {
            "v": event_close,
            "5m": np.nan,
            "10m": np.nan,
            "15m": np.nan,
            "30m": np.nan,
            "60m": np.nan,
        }

        for offset in offsets:

            found = get_future_row(
                raw_case,
                event_raw_time,
                offset,
            )

            if found is None:
                continue

            row, minutes_found = found

            close_price = float(row["close"])

            pnl = trade_pnl_pct(
                direction,
                entry_price,
                close_price,
            )

            label = f"{offset}m"

            values[label] = pnl
            actual_minutes[label] = minutes_found
            close_values[label] = close_price

        # -------------------------------------------------------------
        # Build change-from-V values.
        # -------------------------------------------------------------

        changes_from_v = {}

        for label in ["5m", "10m", "15m", "30m", "60m"]:

            value = values[label]

            if np.isfinite(value) and np.isfinite(raw_v_pnl):
                changes_from_v[label] = value - raw_v_pnl
            else:
                changes_from_v[label] = np.nan

        # -------------------------------------------------------------
        # Sequence classification.
        # -------------------------------------------------------------

        behavior = classify_sequence(values)

        exit_now = float(event["exit_now_pnl_used_pct"])

        stay = event["eventual_pnl_hindsight_pct"]

        if pd.notna(stay):
            stay = float(stay)
            stay_minus_exit = stay - exit_now

            if stay > exit_now:
                decision = "STAY_BETTER"

            elif stay < exit_now:
                decision = "EXIT_BETTER"

            else:
                decision = "SAME"
        else:
            stay_minus_exit = np.nan
            decision = "NO_STAY_OUTCOME"

        # -------------------------------------------------------------
        # Record.
        # -------------------------------------------------------------

        records.append(
            {
                "case_id": case_id,
                "trade_id": event.get("trade_id", ""),
                "symbol": event.get(
                    "symbol",
                    raw_case["symbol"].iloc[0]
                    if "symbol" in raw_case.columns
                    else "",
                ),
                "direction": direction,

                "event_time_utc": event_time.isoformat(),
                "raw_v_candle_utc": event_raw_time.isoformat(),

                "entry_price": entry_price,

                "exit_now_pnl_pct": exit_now,
                "raw_pnl_at_v_pct": raw_v_pnl,
                "eventual_stay_pnl_pct": stay,
                "stay_minus_exit_pct": stay_minus_exit,

                "raw_pnl_after_5m_pct": values["5m"],
                "raw_pnl_after_10m_pct": values["10m"],
                "raw_pnl_after_15m_pct": values["15m"],
                "raw_pnl_after_30m_pct": values["30m"],
                "raw_pnl_after_60m_pct": values["60m"],

                "change_from_v_5m_pct": changes_from_v["5m"],
                "change_from_v_10m_pct": changes_from_v["10m"],
                "change_from_v_15m_pct": changes_from_v["15m"],
                "change_from_v_30m_pct": changes_from_v["30m"],
                "change_from_v_60m_pct": changes_from_v["60m"],

                "actual_minutes_to_5m": actual_minutes["5m"],
                "actual_minutes_to_10m": actual_minutes["10m"],
                "actual_minutes_to_15m": actual_minutes["15m"],
                "actual_minutes_to_30m": actual_minutes["30m"],
                "actual_minutes_to_60m": actual_minutes["60m"],

                "close_at_v": close_values["v"],
                "close_after_5m": close_values["5m"],
                "close_after_10m": close_values["10m"],
                "close_after_15m": close_values["15m"],
                "close_after_30m": close_values["30m"],
                "close_after_60m": close_values["60m"],

                "behavior": behavior,
                "stay_vs_exit": decision,

                "original_pnl_at_v_pct": event.get(
                    "pnl_at_v_pct",
                    np.nan,
                ),

                "original_observation_outcome": event.get(
                    "observation_outcome",
                    "",
                ),
            }
        )

    # =========================================================================
    # RESULTS
    # =========================================================================

    result = pd.DataFrame(records)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_EVENTS,
        index=False,
    )

    print("\n" + "=" * 110)
    print("EXPERIMENT #48 — CORE RESULT")
    print("=" * 110)

    print(f"Events analyzed : {len(result)}")

    if result.empty:
        print("\nNo usable raw trajectory matches.")
        return

    # -------------------------------------------------------------------------
    # Behavior counts.
    # -------------------------------------------------------------------------

    behavior_counts = (
        result["behavior"]
        .value_counts()
        .reindex(
            [
                "ABSORBED_RECOVERY",
                "CONTINUING_REVERSAL",
                "MIXED",
                "INSUFFICIENT",
            ],
            fill_value=0,
        )
    )

    print("\nBEHAVIOR")
    print("-" * 80)

    for behavior, count in behavior_counts.items():
        pct = (
            count / len(result) * 100.0
            if len(result)
            else 0.0
        )

        print(
            f"{behavior:<25} "
            f"{count:>4} "
            f"({pct:>6.2f}%)"
        )

    # -------------------------------------------------------------------------
    # STAY vs EXIT.
    # -------------------------------------------------------------------------

    valid_decisions = result[
        result["stay_vs_exit"].isin(
            [
                "STAY_BETTER",
                "EXIT_BETTER",
                "SAME",
            ]
        )
    ]

    print("\nSTAY vs EXIT")
    print("-" * 80)

    if not valid_decisions.empty:

        stay_better = (
            valid_decisions["stay_vs_exit"] == "STAY_BETTER"
        ).sum()

        exit_better = (
            valid_decisions["stay_vs_exit"] == "EXIT_BETTER"
        ).sum()

        same = (
            valid_decisions["stay_vs_exit"] == "SAME"
        ).sum()

        print(f"STAY better : {stay_better}")
        print(f"EXIT better : {exit_better}")
        print(f"Same        : {same}")

        print(
            f"Average EXIT P&L : "
            f"{valid_decisions['exit_now_pnl_pct'].mean():.4f}%"
        )

        print(
            f"Average STAY P&L : "
            f"{valid_decisions['eventual_stay_pnl_pct'].mean():.4f}%"
        )

        print(
            f"Average STAY-EXIT: "
            f"{valid_decisions['stay_minus_exit_pct'].mean():.4f}%"
        )

    # -------------------------------------------------------------------------
    # Behavior x STAY/EXIT.
    # -------------------------------------------------------------------------

    print("\nBEHAVIOR x STAY vs EXIT")
    print("-" * 80)

    cross = pd.crosstab(
        result["behavior"],
        result["stay_vs_exit"],
    )

    print(cross.to_string())

    # -------------------------------------------------------------------------
    # Detailed table.
    # -------------------------------------------------------------------------

    print("\n" + "=" * 110)
    print("CASE-BY-CASE RAW 5-MINUTE PATH")
    print("=" * 110)

    display_cols = [
        "case_id",
        "trade_id",
        "direction",
        "raw_pnl_at_v_pct",
        "raw_pnl_after_5m_pct",
        "raw_pnl_after_10m_pct",
        "raw_pnl_after_15m_pct",
        "raw_pnl_after_30m_pct",
        "raw_pnl_after_60m_pct",
        "behavior",
        "exit_now_pnl_pct",
        "eventual_stay_pnl_pct",
        "stay_vs_exit",
    ]

    display_cols = [
        c for c in display_cols
        if c in result.columns
    ]

    print(
        result[display_cols].to_string(
            index=False
        )
    )

    # =========================================================================
    # SUMMARY FILE
    # =========================================================================

    summary_rows = []

    for behavior in [
        "ABSORBED_RECOVERY",
        "CONTINUING_REVERSAL",
        "MIXED",
        "INSUFFICIENT",
    ]:

        g = result[
            result["behavior"] == behavior
        ].copy()

        if g.empty:
            continue

        valid = g[
            g["stay_vs_exit"].isin(
                [
                    "STAY_BETTER",
                    "EXIT_BETTER",
                    "SAME",
                ]
            )
        ]

        summary_rows.append(
            {
                "behavior": behavior,
                "events": len(g),
                "unique_cases": g["case_id"].nunique(),

                "avg_raw_pnl_at_v_pct":
                    g["raw_pnl_at_v_pct"].mean(),

                "avg_raw_change_5m_pct":
                    g["change_from_v_5m_pct"].mean(),

                "avg_raw_change_10m_pct":
                    g["change_from_v_10m_pct"].mean(),

                "avg_raw_change_15m_pct":
                    g["change_from_v_15m_pct"].mean(),

                "avg_raw_change_30m_pct":
                    g["change_from_v_30m_pct"].mean(),

                "avg_raw_change_60m_pct":
                    g["change_from_v_60m_pct"].mean(),

                "avg_exit_now_pnl_pct":
                    g["exit_now_pnl_pct"].mean(),

                "avg_stay_pnl_pct":
                    g["eventual_stay_pnl_pct"].mean(),

                "avg_stay_minus_exit_pct":
                    g["stay_minus_exit_pct"].mean(),

                "stay_better_count":
                    int(
                        (
                            valid["stay_vs_exit"]
                            == "STAY_BETTER"
                        ).sum()
                    ),

                "exit_better_count":
                    int(
                        (
                            valid["stay_vs_exit"]
                            == "EXIT_BETTER"
                        ).sum()
                    ),

                "same_count":
                    int(
                        (
                            valid["stay_vs_exit"]
                            == "SAME"
                        ).sum()
                    ),
            }
        )

    summary = pd.DataFrame(summary_rows)

    summary.to_csv(
        OUTPUT_SUMMARY,
        index=False,
    )

    # =========================================================================
    # METADATA
    # =========================================================================

    with open(
        OUTPUT_META,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            "AIMn KISS — Experiment #48\n"
        )

        f.write(
            "UNPROFITABLE V: ABSORBED vs CONTINUING REVERSAL\n\n"
        )

        f.write(
            "Research only.\n"
        )

        f.write(
            "No production changes.\n"
        )

        f.write(
            "No orders.\n"
        )

        f.write(
            "No AI training.\n"
        )

        f.write(
            "No threshold promotion.\n"
        )

        f.write(
            "No re-entry simulation.\n\n"
        )

        f.write(
            f"Experiment #46 source:\n"
            f"{exp46_path.resolve()}\n\n"
        )

        f.write(
            f"Raw trajectory source:\n"
            f"{RAW_TRAJECTORY.resolve()}\n\n"
        )

        f.write(
            f"Qualifying V events:\n"
            f"{len(events)}\n\n"
        )

        f.write(
            "Experiment purpose:\n"
            "Observe whether an unprofitable V is absorbed or becomes "
            "a continuing adverse sequence.\n"
        )

    # =========================================================================
    # OUTPUT PATHS
    # =========================================================================

    print("\n" + "=" * 110)
    print("OUTPUTS")
    print("=" * 110)

    print(f"Events : {OUTPUT_EVENTS.resolve()}")
    print(f"Summary: {OUTPUT_SUMMARY.resolve()}")
    print(f"Meta   : {OUTPUT_META.resolve()}")

    print("\n" + "=" * 110)
    print("END EXPERIMENT #48")
    print("=" * 110)


if __name__ == "__main__":
    main()
