#!/usr/bin/env python3

"""
AIMn KISS — Experiment #48
UNPROFITABLE V: ADVERSE PERSISTENCE

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
We use the EXACT causal V reversal candle from Experiment #46:

    v_reversal_candle_utc

The raw 5-minute trajectory is then inspected FORWARD from that
exact completed candle.

No hindsight is used to define the V.

DATA
----
#46 event file:
    Contains the exact causal V event and the real trade outcome.

Raw 5-minute trajectory:
    Contains the actual price path after the transition.

WHAT WE MEASURE
---------------
At the V:
    P&L at V

After V:
    +5m
    +10m
    +15m
    +30m
    +60m

For each checkpoint:
    trade-relative price change
    adverse movement
    favorable movement

Also:
    first post-V movement
    second post-V movement
    third post-V movement
    number of consecutive adverse candles
    maximum adverse close movement
    maximum favorable close movement

DESCRIPTIVE PATH LABELS
-----------------------
These are observations only.

CONTINUING_REVERSAL
    Price continues moving against the trade over successive
    post-V candles.

IMMEDIATE_NOISE
    First post-V move is favorable to the trade.

NOISE_THEN_RECOVERY
    Price moves against the trade first, then turns back
    toward the trade.

MIXED
    Neither pattern is clean.

INSUFFICIENT
    Not enough post-V candles are available.

No percentage threshold is used for these labels.
"""

from pathlib import Path
import pandas as pd
import numpy as np


# =====================================================================
# PATHS
# =====================================================================

BASE = Path.home() / "aimn-trade-final"

EVENT_FILE = (
    BASE
    / "kiss"
    / "results"
    / "exp46_not_yet_profitable_v"
    / "nvda_not_yet_profitable_v_events.csv"
)

RAW_FILE = (
    BASE
    / "kiss"
    / "results"
    / "exp32_raw_candle_v_geometry"
    / "raw_v_trajectory.csv"
)

OUT_DIR = (
    BASE
    / "kiss"
    / "results"
    / "exp48_adverse_persistence"
)

OUT_DIR.mkdir(parents=True, exist_ok=True)

EVENT_OUTPUT = OUT_DIR / "nvda_adverse_persistence_events.csv"
SUMMARY_OUTPUT = OUT_DIR / "nvda_adverse_persistence_summary.csv"
PATH_OUTPUT = OUT_DIR / "nvda_adverse_persistence_path.csv"
META_OUTPUT = OUT_DIR / "exp48_metadata.txt"


# =====================================================================
# HELPERS
# =====================================================================

def pct_change(price, reference):
    if reference is None or pd.isna(reference) or reference == 0:
        return np.nan
    return (price / reference - 1.0) * 100.0


def trade_relative_change(direction, price, reference):
    """
    Positive = favorable to the existing trade.
    Negative = adverse to the existing trade.
    """
    raw = pct_change(price, reference)

    if pd.isna(raw):
        return np.nan

    direction = str(direction).upper().strip()

    if direction == "LONG":
        return raw

    if direction == "SHORT":
        return -raw

    return np.nan


def describe_directional_move(value):
    """
    Pure sign-based descriptive label.
    No magnitude threshold.
    """
    if pd.isna(value):
        return "MISSING"

    if value > 0:
        return "FAVORABLE"

    if value < 0:
        return "ADVERSE"

    return "FLAT"


def classify_path(values):
    """
    Descriptive classification based only on the sequence
    of post-V trade-relative close movements.

    No percentage threshold is used.
    """
    vals = [v for v in values if not pd.isna(v)]

    if len(vals) == 0:
        return "INSUFFICIENT"

    # First post-V movement.
    first = vals[0]

    # If first move is favorable, the V immediately behaves
    # like noise from the trade's perspective.
    if first > 0:
        return "IMMEDIATE_NOISE"

    # Need at least two points to study what happens next.
    if len(vals) < 2:
        return "INSUFFICIENT"

    # Look for a move back toward the trade after an adverse move.
    for later in vals[1:]:
        if later > vals[0]:
            return "NOISE_THEN_RECOVERY"

    # If every observed checkpoint is adverse or equal,
    # classify it as continuing reversal.
    non_improving = True

    for i in range(1, len(vals)):
        if vals[i] > vals[i - 1]:
            non_improving = False
            break

    if non_improving:
        return "CONTINUING_REVERSAL"

    return "MIXED"


def safe_mean(series):
    if len(series) == 0:
        return np.nan
    return series.mean()


def safe_median(series):
    if len(series) == 0:
        return np.nan
    return series.median()


# =====================================================================
# LOAD
# =====================================================================

def load_files():
    if not EVENT_FILE.exists():
        raise FileNotFoundError(
            f"EVENT FILE NOT FOUND:\n{EVENT_FILE}"
        )

    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"RAW TRAJECTORY FILE NOT FOUND:\n{RAW_FILE}"
        )

    events = pd.read_csv(EVENT_FILE)
    raw = pd.read_csv(RAW_FILE)

    print("=" * 110)
    print("SOURCE FILES")
    print("=" * 110)

    print(f"Events:")
    print(f"  {EVENT_FILE}")
    print(f"  Rows: {len(events):,}")

    print("\nRaw 5-minute trajectory:")
    print(f"  {RAW_FILE}")
    print(f"  Rows: {len(raw):,}")

    print("\nEvent columns:")
    print(list(events.columns))

    print("\nRaw trajectory columns:")
    print(list(raw.columns))

    return events, raw


# =====================================================================
# VALIDATE
# =====================================================================

def validate_columns(events, raw):

    required_event = [
        "case_id",
        "trade_id",
        "symbol",
        "direction",
        "v_reversal_candle_utc",
        "pnl_at_v_pct",
        "eventual_pnl_hindsight_pct",
    ]

    required_raw = [
        "case_id",
        "symbol",
        "direction",
        "candle_utc",
        "open",
        "high",
        "low",
        "close",
    ]

    missing_event = [
        c for c in required_event
        if c not in events.columns
    ]

    missing_raw = [
        c for c in required_raw
        if c not in raw.columns
    ]

    if missing_event:
        raise RuntimeError(
            "EVENT FILE IS MISSING REQUIRED COLUMNS:\n"
            + str(missing_event)
            + "\n\nActual columns:\n"
            + str(list(events.columns))
        )

    if missing_raw:
        raise RuntimeError(
            "RAW TRAJECTORY IS MISSING REQUIRED COLUMNS:\n"
            + str(missing_raw)
            + "\n\nActual columns:\n"
            + str(list(raw.columns))
        )


# =====================================================================
# NORMALIZE TIME
# =====================================================================

def normalize_times(events, raw):

    events = events.copy()
    raw = raw.copy()

    events["v_reversal_candle_utc"] = pd.to_datetime(
        events["v_reversal_candle_utc"],
        utc=True,
        errors="coerce",
    )

    raw["candle_utc"] = pd.to_datetime(
        raw["candle_utc"],
        utc=True,
        errors="coerce",
    )

    bad_event_times = events["v_reversal_candle_utc"].isna().sum()
    bad_raw_times = raw["candle_utc"].isna().sum()

    if bad_event_times:
        raise RuntimeError(
            f"Could not parse {bad_event_times} V timestamps."
        )

    if bad_raw_times:
        raise RuntimeError(
            f"Could not parse {bad_raw_times} raw candle timestamps."
        )

    return events, raw


# =====================================================================
# BUILD ONE EVENT
# =====================================================================

def build_event_analysis(event, raw_case):
    """
    raw_case contains the complete 5-minute trajectory for one case.

    The V candle is located by EXACT timestamp.

    Then we move strictly FORWARD from the V candle.
    """

    case_id = event["case_id"]
    trade_id = event["trade_id"]
    direction = str(event["direction"]).upper().strip()

    v_time = event["v_reversal_candle_utc"]

    raw_case = raw_case.sort_values("candle_utc").reset_index(drop=True)

    exact = raw_case[
        raw_case["candle_utc"] == v_time
    ]

    if exact.empty:
        return None, None

    # There should only be one exact candle.
    v_row = exact.iloc[0]

    v_close = float(v_row["close"])

    # Everything strictly after V.
    future = raw_case[
        raw_case["candle_utc"] > v_time
    ].copy()

    if future.empty:
        return None, None

    future = future.sort_values("candle_utc").reset_index(drop=True)

    # Keep up to the next 12 five-minute candles = 60 minutes.
    future = future.head(12).copy()

    # ---------------------------------------------------------------
    # Build forward path.
    # ---------------------------------------------------------------

    path_rows = []

    for i, row in future.iterrows():

        candle_time = row["candle_utc"]

        elapsed_minutes = (
            candle_time - v_time
        ).total_seconds() / 60.0

        close = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])

        close_change = trade_relative_change(
            direction,
            close,
            v_close,
        )

        high_change = trade_relative_change(
            direction,
            high,
            v_close,
        )

        low_change = trade_relative_change(
            direction,
            low,
            v_close,
        )

        # For a LONG, the LOW is the adverse side.
        # For a SHORT, the HIGH is the adverse side.
        if direction == "LONG":
            adverse_extreme_change = pct_change(
                low,
                v_close,
            )
            favorable_extreme_change = pct_change(
                high,
                v_close,
            )

        elif direction == "SHORT":
            adverse_extreme_change = -pct_change(
                high,
                v_close,
            )
            favorable_extreme_change = -pct_change(
                low,
                v_close,
            )

        else:
            adverse_extreme_change = np.nan
            favorable_extreme_change = np.nan

        path_rows.append(
            {
                "case_id": case_id,
                "trade_id": trade_id,
                "symbol": event["symbol"],
                "direction": direction,
                "v_time_utc": v_time,
                "candle_utc": candle_time,
                "post_v_candle_number": i + 1,
                "minutes_after_v": elapsed_minutes,
                "v_close": v_close,
                "close": close,
                "high": high,
                "low": low,
                "trade_relative_close_change_pct": close_change,
                "adverse_extreme_change_pct": adverse_extreme_change,
                "favorable_extreme_change_pct": favorable_extreme_change,
                "movement_label": describe_directional_move(
                    close_change
                ),
            }
        )

    path_df = pd.DataFrame(path_rows)

    # ---------------------------------------------------------------
    # Get first few post-V changes.
    # ---------------------------------------------------------------

    changes = list(
        path_df["trade_relative_close_change_pct"]
    )

    def nth_change(n):
        if len(changes) >= n:
            return changes[n - 1]
        return np.nan

    c1 = nth_change(1)
    c2 = nth_change(2)
    c3 = nth_change(3)

    # Checkpoints.
    def change_at_minutes(target):
        if path_df.empty:
            return np.nan

        rows = path_df[
            path_df["minutes_after_v"] == target
        ]

        if not rows.empty:
            return float(
                rows.iloc[0][
                    "trade_relative_close_change_pct"
                ]
            )

        return np.nan

    # Since this is a raw 5-minute sequence, use exact candle
    # numbers for the standard checkpoints.
    c5 = nth_change(1)
    c10 = nth_change(2)
    c15 = nth_change(3)
    c30 = nth_change(6)
    c60 = nth_change(12)

    # ---------------------------------------------------------------
    # Adverse persistence.
    # ---------------------------------------------------------------

    consecutive_adverse = 0

    for value in changes:
        if pd.notna(value) and value < 0:
            consecutive_adverse += 1
        else:
            break

    adverse_count_first_3 = sum(
        1
        for value in changes[:3]
        if pd.notna(value) and value < 0
    )

    adverse_count_first_6 = sum(
        1
        for value in changes[:6]
        if pd.notna(value) and value < 0
    )

    max_adverse_close = np.nan
    max_favorable_close = np.nan

    valid_changes = [
        v for v in changes
        if pd.notna(v)
    ]

    if valid_changes:
        max_adverse_close = min(valid_changes)
        max_favorable_close = max(valid_changes)

    path_class = classify_path(changes)

    # ---------------------------------------------------------------
    # Event-level row.
    # ---------------------------------------------------------------

    exit_now = float(event["pnl_at_v_pct"])
    stay = float(event["eventual_pnl_hindsight_pct"])

    stay_minus_exit = stay - exit_now

    event_row = {
        "case_id": case_id,
        "trade_id": trade_id,
        "symbol": event["symbol"],
        "direction": direction,

        "v_time_utc": v_time,
        "v_close": v_close,

        "exit_now_pnl_pct": exit_now,
        "stay_actual_pnl_pct": stay,
        "stay_minus_exit_pct": stay_minus_exit,

        "stay_better": (
            "STAY" if stay > exit_now
            else "EXIT" if stay < exit_now
            else "SAME"
        ),

        "post_v_5m_change_pct": c5,
        "post_v_10m_change_pct": c10,
        "post_v_15m_change_pct": c15,
        "post_v_30m_change_pct": c30,
        "post_v_60m_change_pct": c60,

        "first_post_v_change_pct": c1,
        "second_post_v_change_pct": c2,
        "third_post_v_change_pct": c3,

        "first_post_v_direction": describe_directional_move(c1),
        "second_post_v_direction": describe_directional_move(c2),
        "third_post_v_direction": describe_directional_move(c3),

        "consecutive_adverse_candles": consecutive_adverse,
        "adverse_candles_first_3": adverse_count_first_3,
        "adverse_candles_first_6": adverse_count_first_6,

        "max_adverse_close_change_pct": max_adverse_close,
        "max_favorable_close_change_pct": max_favorable_close,

        "path_class": path_class,

        "raw_post_v_candles_available": len(path_df),
    }

    return event_row, path_df


# =====================================================================
# SUMMARY
# =====================================================================

def print_summary(results):

    df = pd.DataFrame(results)

    print("\n" + "=" * 110)
    print("EXPERIMENT #48 — UNPROFITABLE V: ADVERSE PERSISTENCE")
    print("=" * 110)

    print(f"Events analyzed : {len(df)}")
    print(f"Unique trades   : {df['trade_id'].nunique()}")

    if df.empty:
        print("\nNo valid events were available.")
        return df

    print("\n" + "-" * 110)
    print("CASE-BY-CASE")
    print("-" * 110)

    display_cols = [
        "case_id",
        "trade_id",
        "direction",
        "exit_now_pnl_pct",
        "stay_actual_pnl_pct",
        "stay_minus_exit_pct",
        "stay_better",
        "first_post_v_change_pct",
        "second_post_v_change_pct",
        "third_post_v_change_pct",
        "consecutive_adverse_candles",
        "max_adverse_close_change_pct",
        "path_class",
    ]

    print(
        df[display_cols].to_string(index=False)
    )

    print("\n" + "=" * 110)
    print("PATH CLASS × STAY vs EXIT")
    print("=" * 110)

    grouped = (
        df.groupby("path_class", dropna=False)
        .agg(
            events=("trade_id", "count"),
            trades=("trade_id", "nunique"),
            avg_exit=("exit_now_pnl_pct", "mean"),
            avg_stay=("stay_actual_pnl_pct", "mean"),
            avg_stay_minus_exit=("stay_minus_exit_pct", "mean"),
            median_stay_minus_exit=("stay_minus_exit_pct", "median"),
            stay_better=(
                "stay_better",
                lambda s: int((s == "STAY").sum()),
            ),
            exit_better=(
                "stay_better",
                lambda s: int((s == "EXIT").sum()),
            ),
        )
        .reset_index()
    )

    print(grouped.to_string(index=False))

    print("\n" + "=" * 110)
    print("RAW POST-V BEHAVIOR")
    print("=" * 110)

    checkpoint_cols = [
        "post_v_5m_change_pct",
        "post_v_10m_change_pct",
        "post_v_15m_change_pct",
        "post_v_30m_change_pct",
        "post_v_60m_change_pct",
    ]

    for col in checkpoint_cols:
        if col not in df.columns:
            continue

        s = pd.to_numeric(
            df[col],
            errors="coerce",
        ).dropna()

        if s.empty:
            continue

        print(
            f"{col:32s}"
            f" n={len(s):2d}"
            f" avg={s.mean(): .4f}%"
            f" median={s.median(): .4f}%"
        )

    print("\n" + "=" * 110)
    print("ADVERSE PERSISTENCE")
    print("=" * 110)

    print(
        "Average consecutive adverse candles:",
        df["consecutive_adverse_candles"].mean(),
    )

    print(
        "Median consecutive adverse candles:",
        df["consecutive_adverse_candles"].median(),
    )

    print(
        "Average maximum adverse close:",
        f"{df['max_adverse_close_change_pct'].mean():.4f}%"
    )

    print(
        "Median maximum adverse close:",
        f"{df['max_adverse_close_change_pct'].median():.4f}%"
    )

    return grouped


# =====================================================================
# MAIN
# =====================================================================

def main():

    events, raw = load_files()

    validate_columns(events, raw)

    events, raw = normalize_times(events, raw)

    print("\n" + "=" * 110)
    print("EXACT CAUSAL V MATCH")
    print("=" * 110)

    print(
        "Using event column:"
        " v_reversal_candle_utc"
    )

    print(
        "Matching against raw column:"
        " candle_utc"
    )

    results = []
    all_paths = []

    raw_groups = {
        case_id: group.copy()
        for case_id, group
        in raw.groupby("case_id", sort=False)
    }

    matched = 0
    missing_case = 0
    missing_v_candle = 0

    for _, event in events.iterrows():

        case_id = event["case_id"]

        if case_id not in raw_groups:
            missing_case += 1
            continue

        matched_result, path_df = build_event_analysis(
            event,
            raw_groups[case_id],
        )

        if matched_result is None:
            missing_v_candle += 1
            continue

        results.append(matched_result)
        all_paths.append(path_df)
        matched += 1

    result_df = pd.DataFrame(results)

    if all_paths:
        path_df = pd.concat(
            all_paths,
            ignore_index=True,
        )
    else:
        path_df = pd.DataFrame()

    print(f"\nEvents in #46         : {len(events)}")
    print(f"Matched raw cases     : {matched}")
    print(f"Missing raw case      : {missing_case}")
    print(f"Missing exact V candle: {missing_v_candle}")

    summary_df = print_summary(
        results
    )

    # =================================================================
    # SAVE
    # =================================================================

    result_df.to_csv(
        EVENT_OUTPUT,
        index=False,
    )

    path_df.to_csv(
        PATH_OUTPUT,
        index=False,
    )

    if isinstance(summary_df, pd.DataFrame):
        summary_df.to_csv(
            SUMMARY_OUTPUT,
            index=False,
        )

    metadata = []

    metadata.append(
        "AIMn KISS — Experiment #48"
    )
    metadata.append(
        "UNPROFITABLE V: ADVERSE PERSISTENCE"
    )
    metadata.append("")
    metadata.append(
        "Research only."
    )
    metadata.append(
        "No production strategy changes."
    )
    metadata.append(
        "No orders."
    )
    metadata.append(
        "No AI training."
    )
    metadata.append(
        "No threshold promotion."
    )
    metadata.append(
        "No re-entry simulation."
    )
    metadata.append("")
    metadata.append(
        "CAUSAL EVENT COLUMN:"
    )
    metadata.append(
        "v_reversal_candle_utc"
    )
    metadata.append("")
    metadata.append(
        "RAW PRICE COLUMN:"
    )
    metadata.append(
        "candle_utc"
    )
    metadata.append("")
    metadata.append(
        f"Events supplied by #46: {len(events)}"
    )
    metadata.append(
        f"Raw cases matched: {matched}"
    )
    metadata.append(
        f"Missing raw cases: {missing_case}"
    )
    metadata.append(
        f"Missing exact V candles: {missing_v_candle}"
    )
    metadata.append("")
    metadata.append(
        "No percentage threshold was used to classify"
    )
    metadata.append(
        "post-V path behavior."
    )
    metadata.append("")
    metadata.append(
        "Outputs:"
    )
    metadata.append(
        str(EVENT_OUTPUT)
    )
    metadata.append(
        str(PATH_OUTPUT)
    )
    metadata.append(
        str(SUMMARY_OUTPUT)
    )

    META_OUTPUT.write_text(
        "\n".join(metadata),
        encoding="utf-8",
    )

    print("\n" + "=" * 110)
    print("OUTPUTS")
    print("=" * 110)

    print(f"Events : {EVENT_OUTPUT}")
    print(f"Path   : {PATH_OUTPUT}")
    print(f"Summary: {SUMMARY_OUTPUT}")
    print(f"Meta   : {META_OUTPUT}")

    print("\nDONE.")


if __name__ == "__main__":
    main()

cat > kiss/kiss_exp48_adverse_persistence.py <<'PY'
#!/usr/bin/env python3

"""
AIMn KISS — Experiment #48
UNPROFITABLE V: ADVERSE PERSISTENCE

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
We use the EXACT causal V reversal candle from Experiment #46:

    v_reversal_candle_utc

The raw 5-minute trajectory is then inspected FORWARD from that
exact completed candle.

No hindsight is used to define the V.

DATA
----
#46 event file:
    Contains the exact causal V event and the real trade outcome.

Raw 5-minute trajectory:
    Contains the actual price path after the transition.

WHAT WE MEASURE
---------------
At the V:
    P&L at V

After V:
    +5m
    +10m
    +15m
    +30m
    +60m

For each checkpoint:
    trade-relative price change
    adverse movement
    favorable movement

Also:
    first post-V movement
    second post-V movement
    third post-V movement
    number of consecutive adverse candles
    maximum adverse close movement
    maximum favorable close movement

DESCRIPTIVE PATH LABELS
-----------------------
These are observations only.

CONTINUING_REVERSAL
    Price continues moving against the trade over successive
    post-V candles.

IMMEDIATE_NOISE
    First post-V move is favorable to the trade.

NOISE_THEN_RECOVERY
    Price moves against the trade first, then turns back
    toward the trade.

MIXED
    Neither pattern is clean.

INSUFFICIENT
    Not enough post-V candles are available.

No percentage threshold is used for these labels.
"""

from pathlib import Path
import pandas as pd
import numpy as np


# =====================================================================
# PATHS
# =====================================================================

BASE = Path.home() / "aimn-trade-final"

EVENT_FILE = (
    BASE
    / "kiss"
    / "results"
    / "exp46_not_yet_profitable_v"
    / "nvda_not_yet_profitable_v_events.csv"
)

RAW_FILE = (
    BASE
    / "kiss"
    / "results"
    / "exp32_raw_candle_v_geometry"
    / "raw_v_trajectory.csv"
)

OUT_DIR = (
    BASE
    / "kiss"
    / "results"
    / "exp48_adverse_persistence"
)

OUT_DIR.mkdir(parents=True, exist_ok=True)

EVENT_OUTPUT = OUT_DIR / "nvda_adverse_persistence_events.csv"
SUMMARY_OUTPUT = OUT_DIR / "nvda_adverse_persistence_summary.csv"
PATH_OUTPUT = OUT_DIR / "nvda_adverse_persistence_path.csv"
META_OUTPUT = OUT_DIR / "exp48_metadata.txt"


# =====================================================================
# HELPERS
# =====================================================================

def pct_change(price, reference):
    if reference is None or pd.isna(reference) or reference == 0:
        return np.nan
    return (price / reference - 1.0) * 100.0


def trade_relative_change(direction, price, reference):
    """
    Positive = favorable to the existing trade.
    Negative = adverse to the existing trade.
    """
    raw = pct_change(price, reference)

    if pd.isna(raw):
        return np.nan

    direction = str(direction).upper().strip()

    if direction == "LONG":
        return raw

    if direction == "SHORT":
        return -raw

    return np.nan


def describe_directional_move(value):
    """
    Pure sign-based descriptive label.
    No magnitude threshold.
    """
    if pd.isna(value):
        return "MISSING"

    if value > 0:
        return "FAVORABLE"

    if value < 0:
        return "ADVERSE"

    return "FLAT"


def classify_path(values):
    """
    Descriptive classification based only on the sequence
    of post-V trade-relative close movements.

    No percentage threshold is used.
    """
    vals = [v for v in values if not pd.isna(v)]

    if len(vals) == 0:
        return "INSUFFICIENT"

    # First post-V movement.
    first = vals[0]

    # If first move is favorable, the V immediately behaves
    # like noise from the trade's perspective.
    if first > 0:
        return "IMMEDIATE_NOISE"

    # Need at least two points to study what happens next.
    if len(vals) < 2:
        return "INSUFFICIENT"

    # Look for a move back toward the trade after an adverse move.
    for later in vals[1:]:
        if later > vals[0]:
            return "NOISE_THEN_RECOVERY"

    # If every observed checkpoint is adverse or equal,
    # classify it as continuing reversal.
    non_improving = True

    for i in range(1, len(vals)):
        if vals[i] > vals[i - 1]:
            non_improving = False
            break

    if non_improving:
        return "CONTINUING_REVERSAL"

    return "MIXED"


def safe_mean(series):
    if len(series) == 0:
        return np.nan
    return series.mean()


def safe_median(series):
    if len(series) == 0:
        return np.nan
    return series.median()


# =====================================================================
# LOAD
# =====================================================================

def load_files():
    if not EVENT_FILE.exists():
        raise FileNotFoundError(
            f"EVENT FILE NOT FOUND:\n{EVENT_FILE}"
        )

    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"RAW TRAJECTORY FILE NOT FOUND:\n{RAW_FILE}"
        )

    events = pd.read_csv(EVENT_FILE)
    raw = pd.read_csv(RAW_FILE)

    print("=" * 110)
    print("SOURCE FILES")
    print("=" * 110)

    print(f"Events:")
    print(f"  {EVENT_FILE}")
    print(f"  Rows: {len(events):,}")

    print("\nRaw 5-minute trajectory:")
    print(f"  {RAW_FILE}")
    print(f"  Rows: {len(raw):,}")

    print("\nEvent columns:")
    print(list(events.columns))

    print("\nRaw trajectory columns:")
    print(list(raw.columns))

    return events, raw


# =====================================================================
# VALIDATE
# =====================================================================

def validate_columns(events, raw):

    required_event = [
        "case_id",
        "trade_id",
        "symbol",
        "direction",
        "v_reversal_candle_utc",
        "pnl_at_v_pct",
        "eventual_pnl_hindsight_pct",
    ]

    required_raw = [
        "case_id",
        "symbol",
        "direction",
        "candle_utc",
        "open",
        "high",
        "low",
        "close",
    ]

    missing_event = [
        c for c in required_event
        if c not in events.columns
    ]

    missing_raw = [
        c for c in required_raw
        if c not in raw.columns
    ]

    if missing_event:
        raise RuntimeError(
            "EVENT FILE IS MISSING REQUIRED COLUMNS:\n"
            + str(missing_event)
            + "\n\nActual columns:\n"
            + str(list(events.columns))
        )

    if missing_raw:
        raise RuntimeError(
            "RAW TRAJECTORY IS MISSING REQUIRED COLUMNS:\n"
            + str(missing_raw)
            + "\n\nActual columns:\n"
            + str(list(raw.columns))
        )


# =====================================================================
# NORMALIZE TIME
# =====================================================================

def normalize_times(events, raw):

    events = events.copy()
    raw = raw.copy()

    events["v_reversal_candle_utc"] = pd.to_datetime(
        events["v_reversal_candle_utc"],
        utc=True,
        errors="coerce",
    )

    raw["candle_utc"] = pd.to_datetime(
        raw["candle_utc"],
        utc=True,
        errors="coerce",
    )

    bad_event_times = events["v_reversal_candle_utc"].isna().sum()
    bad_raw_times = raw["candle_utc"].isna().sum()

    if bad_event_times:
        raise RuntimeError(
            f"Could not parse {bad_event_times} V timestamps."
        )

    if bad_raw_times:
        raise RuntimeError(
            f"Could not parse {bad_raw_times} raw candle timestamps."
        )

    return events, raw


# =====================================================================
# BUILD ONE EVENT
# =====================================================================

def build_event_analysis(event, raw_case):
    """
    raw_case contains the complete 5-minute trajectory for one case.

    The V candle is located by EXACT timestamp.

    Then we move strictly FORWARD from the V candle.
    """

    case_id = event["case_id"]
    trade_id = event["trade_id"]
    direction = str(event["direction"]).upper().strip()

    v_time = event["v_reversal_candle_utc"]

    raw_case = raw_case.sort_values("candle_utc").reset_index(drop=True)

    exact = raw_case[
        raw_case["candle_utc"] == v_time
    ]

    if exact.empty:
        return None, None

    # There should only be one exact candle.
    v_row = exact.iloc[0]

    v_close = float(v_row["close"])

    # Everything strictly after V.
    future = raw_case[
        raw_case["candle_utc"] > v_time
    ].copy()

    if future.empty:
        return None, None

    future = future.sort_values("candle_utc").reset_index(drop=True)

    # Keep up to the next 12 five-minute candles = 60 minutes.
    future = future.head(12).copy()

    # ---------------------------------------------------------------
    # Build forward path.
    # ---------------------------------------------------------------

    path_rows = []

    for i, row in future.iterrows():

        candle_time = row["candle_utc"]

        elapsed_minutes = (
            candle_time - v_time
        ).total_seconds() / 60.0

        close = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])

        close_change = trade_relative_change(
            direction,
            close,
            v_close,
        )

        high_change = trade_relative_change(
            direction,
            high,
            v_close,
        )

        low_change = trade_relative_change(
            direction,
            low,
            v_close,
        )

        # For a LONG, the LOW is the adverse side.
        # For a SHORT, the HIGH is the adverse side.
        if direction == "LONG":
            adverse_extreme_change = pct_change(
                low,
                v_close,
            )
            favorable_extreme_change = pct_change(
                high,
                v_close,
            )

        elif direction == "SHORT":
            adverse_extreme_change = -pct_change(
                high,
                v_close,
            )
            favorable_extreme_change = -pct_change(
                low,
                v_close,
            )

        else:
            adverse_extreme_change = np.nan
            favorable_extreme_change = np.nan

        path_rows.append(
            {
                "case_id": case_id,
                "trade_id": trade_id,
                "symbol": event["symbol"],
                "direction": direction,
                "v_time_utc": v_time,
                "candle_utc": candle_time,
                "post_v_candle_number": i + 1,
                "minutes_after_v": elapsed_minutes,
                "v_close": v_close,
                "close": close,
                "high": high,
                "low": low,
                "trade_relative_close_change_pct": close_change,
                "adverse_extreme_change_pct": adverse_extreme_change,
                "favorable_extreme_change_pct": favorable_extreme_change,
                "movement_label": describe_directional_move(
                    close_change
                ),
            }
        )

    path_df = pd.DataFrame(path_rows)

    # ---------------------------------------------------------------
    # Get first few post-V changes.
    # ---------------------------------------------------------------

    changes = list(
        path_df["trade_relative_close_change_pct"]
    )

    def nth_change(n):
        if len(changes) >= n:
            return changes[n - 1]
        return np.nan

    c1 = nth_change(1)
    c2 = nth_change(2)
    c3 = nth_change(3)

    # Checkpoints.
    def change_at_minutes(target):
        if path_df.empty:
            return np.nan

        rows = path_df[
            path_df["minutes_after_v"] == target
        ]

        if not rows.empty:
            return float(
                rows.iloc[0][
                    "trade_relative_close_change_pct"
                ]
            )

        return np.nan

    # Since this is a raw 5-minute sequence, use exact candle
    # numbers for the standard checkpoints.
    c5 = nth_change(1)
    c10 = nth_change(2)
    c15 = nth_change(3)
    c30 = nth_change(6)
    c60 = nth_change(12)

    # ---------------------------------------------------------------
    # Adverse persistence.
    # ---------------------------------------------------------------

    consecutive_adverse = 0

    for value in changes:
        if pd.notna(value) and value < 0:
            consecutive_adverse += 1
        else:
            break

    adverse_count_first_3 = sum(
        1
        for value in changes[:3]
        if pd.notna(value) and value < 0
    )

    adverse_count_first_6 = sum(
        1
        for value in changes[:6]
        if pd.notna(value) and value < 0
    )

    max_adverse_close = np.nan
    max_favorable_close = np.nan

    valid_changes = [
        v for v in changes
        if pd.notna(v)
    ]

    if valid_changes:
        max_adverse_close = min(valid_changes)
        max_favorable_close = max(valid_changes)

    path_class = classify_path(changes)

    # ---------------------------------------------------------------
    # Event-level row.
    # ---------------------------------------------------------------

    exit_now = float(event["pnl_at_v_pct"])
    stay = float(event["eventual_pnl_hindsight_pct"])

    stay_minus_exit = stay - exit_now

    event_row = {
        "case_id": case_id,
        "trade_id": trade_id,
        "symbol": event["symbol"],
        "direction": direction,

        "v_time_utc": v_time,
        "v_close": v_close,

        "exit_now_pnl_pct": exit_now,
        "stay_actual_pnl_pct": stay,
        "stay_minus_exit_pct": stay_minus_exit,

        "stay_better": (
            "STAY" if stay > exit_now
            else "EXIT" if stay < exit_now
            else "SAME"
        ),

        "post_v_5m_change_pct": c5,
        "post_v_10m_change_pct": c10,
        "post_v_15m_change_pct": c15,
        "post_v_30m_change_pct": c30,
        "post_v_60m_change_pct": c60,

        "first_post_v_change_pct": c1,
        "second_post_v_change_pct": c2,
        "third_post_v_change_pct": c3,

        "first_post_v_direction": describe_directional_move(c1),
        "second_post_v_direction": describe_directional_move(c2),
        "third_post_v_direction": describe_directional_move(c3),

        "consecutive_adverse_candles": consecutive_adverse,
        "adverse_candles_first_3": adverse_count_first_3,
        "adverse_candles_first_6": adverse_count_first_6,

        "max_adverse_close_change_pct": max_adverse_close,
        "max_favorable_close_change_pct": max_favorable_close,

        "path_class": path_class,

        "raw_post_v_candles_available": len(path_df),
    }

    return event_row, path_df


# =====================================================================
# SUMMARY
# =====================================================================

def print_summary(results):

    df = pd.DataFrame(results)

    print("\n" + "=" * 110)
    print("EXPERIMENT #48 — UNPROFITABLE V: ADVERSE PERSISTENCE")
    print("=" * 110)

    print(f"Events analyzed : {len(df)}")
    print(f"Unique trades   : {df['trade_id'].nunique()}")

    if df.empty:
        print("\nNo valid events were available.")
        return df

    print("\n" + "-" * 110)
    print("CASE-BY-CASE")
    print("-" * 110)

    display_cols = [
        "case_id",
        "trade_id",
        "direction",
        "exit_now_pnl_pct",
        "stay_actual_pnl_pct",
        "stay_minus_exit_pct",
        "stay_better",
        "first_post_v_change_pct",
        "second_post_v_change_pct",
        "third_post_v_change_pct",
        "consecutive_adverse_candles",
        "max_adverse_close_change_pct",
        "path_class",
    ]

    print(
        df[display_cols].to_string(index=False)
    )

    print("\n" + "=" * 110)
    print("PATH CLASS × STAY vs EXIT")
    print("=" * 110)

    grouped = (
        df.groupby("path_class", dropna=False)
        .agg(
            events=("trade_id", "count"),
            trades=("trade_id", "nunique"),
            avg_exit=("exit_now_pnl_pct", "mean"),
            avg_stay=("stay_actual_pnl_pct", "mean"),
            avg_stay_minus_exit=("stay_minus_exit_pct", "mean"),
            median_stay_minus_exit=("stay_minus_exit_pct", "median"),
            stay_better=(
                "stay_better",
                lambda s: int((s == "STAY").sum()),
            ),
            exit_better=(
                "stay_better",
                lambda s: int((s == "EXIT").sum()),
            ),
        )
        .reset_index()
    )

    print(grouped.to_string(index=False))

    print("\n" + "=" * 110)
    print("RAW POST-V BEHAVIOR")
    print("=" * 110)

    checkpoint_cols = [
        "post_v_5m_change_pct",
        "post_v_10m_change_pct",
        "post_v_15m_change_pct",
        "post_v_30m_change_pct",
        "post_v_60m_change_pct",
    ]

    for col in checkpoint_cols:
        if col not in df.columns:
            continue

        s = pd.to_numeric(
            df[col],
            errors="coerce",
        ).dropna()

        if s.empty:
            continue

        print(
            f"{col:32s}"
            f" n={len(s):2d}"
            f" avg={s.mean(): .4f}%"
            f" median={s.median(): .4f}%"
        )

    print("\n" + "=" * 110)
    print("ADVERSE PERSISTENCE")
    print("=" * 110)

    print(
        "Average consecutive adverse candles:",
        df["consecutive_adverse_candles"].mean(),
    )

    print(
        "Median consecutive adverse candles:",
        df["consecutive_adverse_candles"].median(),
    )

    print(
        "Average maximum adverse close:",
        f"{df['max_adverse_close_change_pct'].mean():.4f}%"
    )

    print(
        "Median maximum adverse close:",
        f"{df['max_adverse_close_change_pct'].median():.4f}%"
    )

    return grouped


# =====================================================================
# MAIN
# =====================================================================

def main():

    events, raw = load_files()

    validate_columns(events, raw)

    events, raw = normalize_times(events, raw)

    print("\n" + "=" * 110)
    print("EXACT CAUSAL V MATCH")
    print("=" * 110)

    print(
        "Using event column:"
        " v_reversal_candle_utc"
    )

    print(
        "Matching against raw column:"
        " candle_utc"
    )

    results = []
    all_paths = []

    raw_groups = {
        case_id: group.copy()
        for case_id, group
        in raw.groupby("case_id", sort=False)
    }

    matched = 0
    missing_case = 0
    missing_v_candle = 0

    for _, event in events.iterrows():

        case_id = event["case_id"]

        if case_id not in raw_groups:
            missing_case += 1
            continue

        matched_result, path_df = build_event_analysis(
            event,
            raw_groups[case_id],
        )

        if matched_result is None:
            missing_v_candle += 1
            continue

        results.append(matched_result)
        all_paths.append(path_df)
        matched += 1

    result_df = pd.DataFrame(results)

    if all_paths:
        path_df = pd.concat(
            all_paths,
            ignore_index=True,
        )
    else:
        path_df = pd.DataFrame()

    print(f"\nEvents in #46         : {len(events)}")
    print(f"Matched raw cases     : {matched}")
    print(f"Missing raw case      : {missing_case}")
    print(f"Missing exact V candle: {missing_v_candle}")

    summary_df = print_summary(
        results
    )

    # =================================================================
    # SAVE
    # =================================================================

    result_df.to_csv(
        EVENT_OUTPUT,
        index=False,
    )

    path_df.to_csv(
        PATH_OUTPUT,
        index=False,
    )

    if isinstance(summary_df, pd.DataFrame):
        summary_df.to_csv(
            SUMMARY_OUTPUT,
            index=False,
        )

    metadata = []

    metadata.append(
        "AIMn KISS — Experiment #48"
    )
    metadata.append(
        "UNPROFITABLE V: ADVERSE PERSISTENCE"
    )
    metadata.append("")
    metadata.append(
        "Research only."
    )
    metadata.append(
        "No production strategy changes."
    )
    metadata.append(
        "No orders."
    )
    metadata.append(
        "No AI training."
    )
    metadata.append(
        "No threshold promotion."
    )
    metadata.append(
        "No re-entry simulation."
    )
    metadata.append("")
    metadata.append(
        "CAUSAL EVENT COLUMN:"
    )
    metadata.append(
        "v_reversal_candle_utc"
    )
    metadata.append("")
    metadata.append(
        "RAW PRICE COLUMN:"
    )
    metadata.append(
        "candle_utc"
    )
    metadata.append("")
    metadata.append(
        f"Events supplied by #46: {len(events)}"
    )
    metadata.append(
        f"Raw cases matched: {matched}"
    )
    metadata.append(
        f"Missing raw cases: {missing_case}"
    )
    metadata.append(
        f"Missing exact V candles: {missing_v_candle}"
    )
    metadata.append("")
    metadata.append(
        "No percentage threshold was used to classify"
    )
    metadata.append(
        "post-V path behavior."
    )
    metadata.append("")
    metadata.append(
        "Outputs:"
    )
    metadata.append(
        str(EVENT_OUTPUT)
    )
    metadata.append(
        str(PATH_OUTPUT)
    )
    metadata.append(
        str(SUMMARY_OUTPUT)
    )

    META_OUTPUT.write_text(
        "\n".join(metadata),
        encoding="utf-8",
    )

    print("\n" + "=" * 110)
    print("OUTPUTS")
    print("=" * 110)

    print(f"Events : {EVENT_OUTPUT}")
    print(f"Path   : {PATH_OUTPUT}")
    print(f"Summary: {SUMMARY_OUTPUT}")
    print(f"Meta   : {META_OUTPUT}")

    print("\nDONE.")


if __name__ == "__main__":
    main()
