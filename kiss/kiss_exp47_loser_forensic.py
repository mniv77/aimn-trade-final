#!/usr/bin/env python3

"""
AIMn KISS — LOSER FORENSIC TEST
================================

RESEARCH ONLY

No production strategy changes.
No orders.
No AI training.
No threshold promotion.
No re-entry simulation.

QUESTION
--------

For trades that eventually became LOSERS:

At an unprofitable V, was the price:

    1. merely making noise,

or

    2. continuing the reversal against the trade?

And, historically:

    EXIT NOW
        versus
    STAY

which would have been better?

IMPORTANT
---------

This version uses the RAW 5-MINUTE TRAJECTORY.

It does NOT assume that the raw trajectory contains:
    transition_time_utc

The actual raw trajectory columns are:

    case_id
    symbol
    direction
    transition_known_utc
    candle_utc
    minutes_after_known
    open
    high
    low
    close
    adverse_from_transition_pct
    favorable_from_transition_pct
    recovery_from_raw_extreme_pct

The trade/V metadata supplies:
    event_time_utc
    entry_time_utc
    pnl_at_v_pct
    eventual_pnl_hindsight_pct
    etc.

No hindsight is used to DETECT the V.

Hindsight is used ONLY to evaluate what happened afterward.
"""

from pathlib import Path
import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[1]

RAW_PATH = (
    ROOT
    / "kiss/results/exp32_raw_candle_v_geometry/raw_v_trajectory.csv"
)

V_PATH = (
    ROOT
    / "kiss/results/exp42_v_peak_divergence/"
    / "nvda_v_peak_divergence_transitions.csv"
)

OUT_DIR = ROOT / "kiss/results/exp47_loser_forensic"
OUT_DIR.mkdir(parents=True, exist_ok=True)

EVENTS_OUT = OUT_DIR / "loser_v_forensic_events.csv"
SUMMARY_OUT = OUT_DIR / "loser_v_forensic_summary.csv"
META_OUT = OUT_DIR / "exp47_metadata.txt"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def pct(x):
    if pd.isna(x):
        return "NA"
    return f"{float(x):.4f}%"


def num(x):
    try:
        return float(x)
    except Exception:
        return np.nan


def classify_immediate_path(row):
    """
    Classify the price after the causal V.

    This is deliberately descriptive.

    LONG:
        falling P&L after V = reversal continuing against trade
        rising P&L after V = recovery

    SHORT:
        same P&L interpretation applies because pnl is
        already direction-adjusted.

    We therefore classify using P&L changes.
    """

    changes = []

    for c in [
        "change_from_v_after_5m_pct",
        "change_from_v_after_10m_pct",
        "change_from_v_after_15m_pct",
    ]:
        if c in row.index and pd.notna(row[c]):
            changes.append(float(row[c]))

    if len(changes) == 0:
        return "INSUFFICIENT"

    first = changes[0]

    later = [x for x in changes[1:] if pd.notna(x)]

    # Immediate improvement followed by deterioration.
    if first > 0:
        if any(x < 0 for x in later):
            return "NOISE_THEN_REVERSAL"
        return "IMMEDIATE_RECOVERY"

    # Immediate deterioration.
    if first < 0:
        if later and all(x < 0 for x in later):
            return "CONTINUING_REVERSAL"

        if any(x > 0 for x in later):
            return "REVERSAL_THEN_RECOVERY"

        return "IMMEDIATE_REVERSAL"

    return "FLAT"


def choose_v_events(vdf):
    """
    Keep V events that occurred while the trade was not profitable.

    We intentionally do NOT impose a new profitability threshold.

    The raw research definition here is:

        pnl_at_v_pct <= 0

    This gives the cleanest answer to the current question:

        "not yet profitable"
    """

    x = vdf.copy()

    x["pnl_at_v_pct"] = pd.to_numeric(
        x["pnl_at_v_pct"], errors="coerce"
    )

    x["eventual_pnl_hindsight_pct"] = pd.to_numeric(
        x["eventual_pnl_hindsight_pct"],
        errors="coerce",
    )

    return x[
        x["pnl_at_v_pct"].notna()
        & (x["pnl_at_v_pct"] <= 0)
    ].copy()


def build_raw_lookup(raw):
    """
    Build:

        case_id -> raw trajectory

    with candle_utc as the causal time axis.
    """

    raw = raw.copy()

    raw["candle_utc"] = pd.to_datetime(
        raw["candle_utc"],
        utc=True,
        errors="coerce",
    )

    raw["transition_known_utc"] = pd.to_datetime(
        raw["transition_known_utc"],
        utc=True,
        errors="coerce",
    )

    raw["minutes_after_known"] = pd.to_numeric(
        raw["minutes_after_known"],
        errors="coerce",
    )

    raw = raw.dropna(
        subset=[
            "case_id",
            "candle_utc",
        ]
    )

    return raw


def nearest_raw_row(raw_case, event_time):
    """
    Find the completed 5-minute candle corresponding to the V event.

    We do not invent a timestamp.

    event_time_utc is matched to the nearest completed raw candle.
    """

    if raw_case.empty or pd.isna(event_time):
        return None

    r = raw_case.copy()

    r["delta_seconds"] = (
        r["candle_utc"] - event_time
    ).abs().dt.total_seconds()

    r = r.sort_values("delta_seconds")

    if r.empty:
        return None

    return r.iloc[0]


def get_forward_pnl(raw_case, event_time):
    """
    Extract direction-adjusted price behavior after the V.

    We use close-to-close movement relative to the V close.

    +5m means one completed 5-minute candle after V.
    +10m means two candles, etc.

    No future information is used to define the V itself.
    """

    r = raw_case.copy()

    r = r.sort_values("candle_utc")

    if r.empty:
        return {}

    event_row = nearest_raw_row(r, event_time)

    if event_row is None:
        return {}

    event_idx = event_row.name
    event_close = num(event_row["close"])

    if not np.isfinite(event_close) or event_close == 0:
        return {}

    after = r[
        r["candle_utc"] > event_row["candle_utc"]
    ].copy()

    result = {
        "raw_v_close": event_close,
        "raw_v_time_utc": event_row["candle_utc"],
    }

    for minutes in [5, 10, 15, 30, 60]:

        target = event_row["candle_utc"] + pd.Timedelta(
            minutes=minutes
        )

        candidates = after[
            after["candle_utc"] >= target
        ]

        if candidates.empty:
            result[f"raw_close_after_{minutes}m"] = np.nan
            result[f"raw_change_after_{minutes}m_pct"] = np.nan
            continue

        row = candidates.iloc[0]

        close = num(row["close"])

        if not np.isfinite(close):
            change = np.nan
        else:
            change = (close / event_close - 1.0) * 100.0

        result[f"raw_close_after_{minutes}m"] = close
        result[f"raw_change_after_{minutes}m_pct"] = change

    return result


def print_header(title):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    print_header(
        "AIMn KISS — LOSER FORENSIC TEST"
    )

    print("Research only.")
    print("Raw 5-minute trajectory.")
    print("No production changes.")
    print("No orders.")
    print("No AI.")
    print("No threshold promotion.")

    # ---------------------------------------------------------------
    # Load raw trajectory
    # ---------------------------------------------------------------

    if not RAW_PATH.exists():
        raise SystemExit(
            f"RAW TRAJECTORY NOT FOUND:\n{RAW_PATH}"
        )

    raw = pd.read_csv(RAW_PATH)

    required_raw = [
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
        "adverse_from_transition_pct",
        "favorable_from_transition_pct",
        "recovery_from_raw_extreme_pct",
    ]

    missing = [
        c for c in required_raw
        if c not in raw.columns
    ]

    if missing:
        raise SystemExit(
            "RAW TRAJECTORY IS MISSING REQUIRED COLUMNS:\n"
            + str(missing)
            + "\n\nActual columns:\n"
            + str(list(raw.columns))
        )

    raw = build_raw_lookup(raw)

    # ---------------------------------------------------------------
    # Load V/trade metadata
    # ---------------------------------------------------------------

    if not V_PATH.exists():
        raise SystemExit(
            f"V METADATA NOT FOUND:\n{V_PATH}"
        )

    vdf = pd.read_csv(V_PATH)

    required_v = [
        "case_id",
        "trade_id",
        "symbol",
        "direction",
        "event_time_utc",
        "entry_time_utc",
        "entry_price",
        "pnl_at_v_pct",
        "eventual_pnl_hindsight_pct",
    ]

    missing = [
        c for c in required_v
        if c not in vdf.columns
    ]

    if missing:
        raise SystemExit(
            "V METADATA IS MISSING REQUIRED COLUMNS:\n"
            + str(missing)
            + "\n\nActual columns:\n"
            + str(list(vdf.columns))
        )

    vdf["event_time_utc"] = pd.to_datetime(
        vdf["event_time_utc"],
        utc=True,
        errors="coerce",
    )

    vdf["entry_time_utc"] = pd.to_datetime(
        vdf["entry_time_utc"],
        utc=True,
        errors="coerce",
    )

    # ---------------------------------------------------------------
    # LOSER population
    # ---------------------------------------------------------------

    losers = vdf[
        pd.to_numeric(
            vdf["eventual_pnl_hindsight_pct"],
            errors="coerce",
        ) < 0
    ].copy()

    loser_trade_ids = (
        losers["trade_id"]
        .dropna()
        .astype(str)
        .unique()
    )

    print_header("LOSER POPULATION")

    print(
        f"V metadata rows : {len(vdf):,}"
    )

    print(
        f"Loser V rows    : {len(losers):,}"
    )

    print(
        f"Unique loser trades: {len(loser_trade_ids):,}"
    )

    print()

    # ---------------------------------------------------------------
    # Unprofitable V events among losers
    # ---------------------------------------------------------------

    events = choose_v_events(losers)

    print_header(
        "UNPROFITABLE V EVENTS INSIDE LOSING TRADES"
    )

    print(
        f"Qualifying events: {len(events):,}"
    )

    if events.empty:
        print()
        print(
            "NO UNPROFITABLE V EVENTS FOUND."
        )
        print()
        print(
            "This is a DATA RESULT, not a strategy result."
        )
        return

    # ---------------------------------------------------------------
    # Build forensic rows
    # ---------------------------------------------------------------

    output = []

    raw_groups = {
        str(k): g.sort_values("candle_utc").copy()
        for k, g in raw.groupby("case_id")
    }

    for _, event in events.iterrows():

        case_id = str(event["case_id"])

        raw_case = raw_groups.get(
            case_id,
            pd.DataFrame(),
        )

        event_time = event["event_time_utc"]

        raw_forward = get_forward_pnl(
            raw_case,
            event_time,
        )

        row = event.to_dict()

        # -----------------------------------------------------------
        # EXIT NOW
        # -----------------------------------------------------------

        row["exit_now_pnl_pct"] = num(
            event["pnl_at_v_pct"]
        )

        # -----------------------------------------------------------
        # STAY
        # -----------------------------------------------------------

        row["stay_final_pnl_pct"] = num(
            event["eventual_pnl_hindsight_pct"]
        )

        row["stay_minus_exit_pct"] = (
            row["stay_final_pnl_pct"]
            - row["exit_now_pnl_pct"]
        )

        if row["stay_minus_exit_pct"] > 0:
            row["decision_historically_better"] = "STAY"
        elif row["stay_minus_exit_pct"] < 0:
            row["decision_historically_better"] = "EXIT"
        else:
            row["decision_historically_better"] = "SAME"

        # -----------------------------------------------------------
        # Raw 5-minute causal trajectory
        # -----------------------------------------------------------

        row.update(raw_forward)

        # -----------------------------------------------------------
        # Existing V trajectory fields
        # -----------------------------------------------------------

        row["behavior_class"] = classify_immediate_path(
            event
        )

        # First available post-V P&L movement
        first_changes = []

        for c in [
            "change_from_v_after_5m_pct",
            "change_from_v_after_10m_pct",
            "change_from_v_after_15m_pct",
        ]:

            if c in event.index and pd.notna(event[c]):
                first_changes.append(
                    num(event[c])
                )

        if first_changes:
            row["first_post_v_pnl_change_pct"] = (
                first_changes[0]
            )
        else:
            row["first_post_v_pnl_change_pct"] = np.nan

        # Count post-V negative P&L checkpoints.
        negative_count = 0
        positive_count = 0

        for c in [
            "change_from_v_after_5m_pct",
            "change_from_v_after_10m_pct",
            "change_from_v_after_15m_pct",
            "change_from_v_after_30m_pct",
        ]:

            if c not in event.index:
                continue

            value = num(event[c])

            if not np.isfinite(value):
                continue

            if value < 0:
                negative_count += 1
            elif value > 0:
                positive_count += 1

        row["negative_post_v_checkpoints"] = negative_count
        row["positive_post_v_checkpoints"] = positive_count

        output.append(row)

    result = pd.DataFrame(output)

    # ---------------------------------------------------------------
    # Save detailed output
    # ---------------------------------------------------------------

    result.to_csv(
        EVENTS_OUT,
        index=False,
    )

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------

    summary_rows = []

    total = len(result)

    stay_better = (
        result["decision_historically_better"]
        == "STAY"
    ).sum()

    exit_better = (
        result["decision_historically_better"]
        == "EXIT"
    ).sum()

    same = (
        result["decision_historically_better"]
        == "SAME"
    ).sum()

    print_header(
        "CORE RESULT — LOSER FORENSICS"
    )

    print(
        f"Unprofitable V events : {total:,}"
    )

    print(
        f"STAY historically better : {stay_better:,}"
    )

    print(
        f"EXIT historically better : {exit_better:,}"
    )

    print(
        f"SAME : {same:,}"
    )

    print()

    print(
        "Average EXIT P&L : "
        + pct(result["exit_now_pnl_pct"].mean())
    )

    print(
        "Average STAY P&L : "
        + pct(result["stay_final_pnl_pct"].mean())
    )

    print(
        "Average STAY - EXIT : "
        + pct(result["stay_minus_exit_pct"].mean())
    )

    print(
        "Median STAY - EXIT : "
        + pct(result["stay_minus_exit_pct"].median())
    )

    print_header(
        "BEHAVIOR AT / AFTER UNPROFITABLE V"
    )

    behavior = (
        result
        .groupby("behavior_class")
        .agg(
            events=("case_id", "size"),
            trades=("trade_id", "nunique"),
            avg_exit_pnl=("exit_now_pnl_pct", "mean"),
            avg_stay_pnl=("stay_final_pnl_pct", "mean"),
            avg_stay_minus_exit=(
                "stay_minus_exit_pct",
                "mean",
            ),
            stay_better=(
                "decision_historically_better",
                lambda s: (s == "STAY").sum(),
            ),
            exit_better=(
                "decision_historically_better",
                lambda s: (s == "EXIT").sum(),
            ),
        )
        .reset_index()
    )

    print(
        behavior.to_string(
            index=False
        )
    )

    # ---------------------------------------------------------------
    # Loss depth groups — descriptive only
    # ---------------------------------------------------------------

    print_header(
        "LOSS DEPTH — DESCRIPTIVE ONLY"
    )

    result["loss_depth_abs_pct"] = (
        -result["exit_now_pnl_pct"]
    )

    result["loss_depth_group"] = pd.cut(
        result["loss_depth_abs_pct"],
        bins=[
            -np.inf,
            0.05,
            0.10,
            0.15,
            0.25,
            np.inf,
        ],
        labels=[
            "<=0.05%",
            "0.05-0.10%",
            "0.10-0.15%",
            "0.15-0.25%",
            ">0.25%",
        ],
    )

    depth = (
        result
        .groupby(
            "loss_depth_group",
            observed=False,
        )
        .agg(
            events=("case_id", "size"),
            trades=("trade_id", "nunique"),
            avg_stay_minus_exit=(
                "stay_minus_exit_pct",
                "mean",
            ),
            stay_better=(
                "decision_historically_better",
                lambda s: (s == "STAY").sum(),
            ),
            exit_better=(
                "decision_historically_better",
                lambda s: (s == "EXIT").sum(),
            ),
        )
        .reset_index()
    )

    print(
        depth.to_string(
            index=False
        )
    )

    # ---------------------------------------------------------------
    # Immediate post-V behavior
    # ---------------------------------------------------------------

    print_header(
        "IMMEDIATE POST-V P&L"
    )

    immediate = (
        result[
            [
                "case_id",
                "trade_id",
                "direction",
                "exit_now_pnl_pct",
                "first_post_v_pnl_change_pct",
                "negative_post_v_checkpoints",
                "positive_post_v_checkpoints",
                "stay_final_pnl_pct",
                "stay_minus_exit_pct",
                "decision_historically_better",
                "behavior_class",
            ]
        ]
        .sort_values(
            [
                "decision_historically_better",
                "stay_minus_exit_pct",
            ]
        )
    )

    print(
        immediate.to_string(
            index=False
        )
    )

    # ---------------------------------------------------------------
    # Save summary CSV
    # ---------------------------------------------------------------

    summary_rows.append(
        {
            "metric": "unprofitable_v_events",
            "value": total,
        }
    )

    summary_rows.append(
        {
            "metric": "stay_better",
            "value": stay_better,
        }
    )

    summary_rows.append(
        {
            "metric": "exit_better",
            "value": exit_better,
        }
    )

    summary_rows.append(
        {
            "metric": "same",
            "value": same,
        }
    )

    summary_rows.append(
        {
            "metric": "average_exit_pnl_pct",
            "value": result["exit_now_pnl_pct"].mean(),
        }
    )

    summary_rows.append(
        {
            "metric": "average_stay_pnl_pct",
            "value": result["stay_final_pnl_pct"].mean(),
        }
    )

    summary_rows.append(
        {
            "metric": "average_stay_minus_exit_pct",
            "value": result["stay_minus_exit_pct"].mean(),
        }
    )

    summary_rows.append(
        {
            "metric": "median_stay_minus_exit_pct",
            "value": result["stay_minus_exit_pct"].median(),
        }
    )

    summary = pd.DataFrame(summary_rows)

    summary.to_csv(
        SUMMARY_OUT,
        index=False,
    )

    # ---------------------------------------------------------------
    # Metadata
    # ---------------------------------------------------------------

    with open(META_OUT, "w") as f:

        f.write(
            "AIMn KISS — LOSER FORENSIC TEST\n"
        )

        f.write(
            "================================\n\n"
        )

        f.write(
            "Research only.\n"
        )

        f.write(
            "No production strategy changes.\n"
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
            f"Raw trajectory rows: {len(raw)}\n"
        )

        f.write(
            f"V metadata rows: {len(vdf)}\n"
        )

        f.write(
            f"Loser V rows: {len(losers)}\n"
        )

        f.write(
            f"Unprofitable loser V events: {total}\n"
        )

        f.write(
            f"STAY better: {stay_better}\n"
        )

        f.write(
            f"EXIT better: {exit_better}\n"
        )

        f.write(
            f"SAME: {same}\n"
        )

        f.write(
            "\nThe V is defined from the existing V metadata.\n"
        )

        f.write(
            "The raw 5-minute trajectory is used for the "
            "causal price-path forensic analysis.\n"
        )

    print_header("OUTPUTS")

    print(f"Events : {EVENTS_OUT}")
    print(f"Summary: {SUMMARY_OUT}")
    print(f"Meta   : {META_OUT}")

    print()
    print("DONE.")


if __name__ == "__main__":
    main()
