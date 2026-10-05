"""
Experiment #37 — NVDA Causal Price Behavior + P&L + Costs

Research only.
No production changes.
No live orders.
No parameter promotion.

Purpose:
    Walk forward through completed 5-minute candles after each NVDA
    major transition and record only information that would have been
    available at that candle.

Primary questions:
    1. How does price behave after the major transition?
    2. How does the developing V evolve?
    3. What is the current unrealized P&L at each point?
    4. When is the trade actually profitable enough to cover cost?
    5. What happened to MFE / MAE as the trade developed?
    6. Compare the causal path to the eventual trade result only as
       explicitly labeled hindsight/reference information.

Important:
    - No minor/medium/major V classification is imposed here.
    - No exit rule is invented.
    - No EXIT + RE-ENTER simulation is performed yet.
    - Future candles are never used to create a past decision.

Inputs:
    kiss/results/exp32_raw_candle_v_geometry/raw_v_trajectory.csv
    kiss/results/exp32_raw_candle_v_geometry/raw_v_geometry.csv
    kiss/results/exp30_nvda_transition_match/nvda_trades_entry_025.csv

Outputs:
    kiss/results/exp37_nvda_causal/nvda_causal_path.csv
    kiss/results/exp37_nvda_causal/nvda_causal_summary.csv
    kiss/results/exp37_nvda_causal/exp37_metadata.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

TRAJECTORY_FILE = Path(
    "kiss/results/exp32_raw_candle_v_geometry/raw_v_trajectory.csv"
)

GEOMETRY_FILE = Path(
    "kiss/results/exp32_raw_candle_v_geometry/raw_v_geometry.csv"
)

TRADES_FILE = Path(
    "kiss/results/exp30_nvda_transition_match/nvda_trades_entry_025.csv"
)

OUTPUT_DIR = Path("kiss/results/exp37_nvda_causal")

PATH_OUTPUT = OUTPUT_DIR / "nvda_causal_path.csv"
SUMMARY_OUTPUT = OUTPUT_DIR / "nvda_causal_summary.csv"
METADATA_OUTPUT = OUTPUT_DIR / "exp37_metadata.txt"


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")


def normalize_direction(value) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip().upper()

    if text in {"LONG", "BUY", "LONG_ENTRY", "ENTER_LONG"}:
        return "LONG"

    if text in {"SHORT", "SELL", "SHORT_ENTRY", "ENTER_SHORT"}:
        return "SHORT"

    return text


def first_existing(df: pd.DataFrame, names: Iterable[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def numeric(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")


def parse_utc(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col],
                errors="coerce",
                utc=True,
            )


def safe_pct(numerator: float, denominator: float) -> float:
    if denominator is None:
        return np.nan

    try:
        denominator = float(denominator)
    except (TypeError, ValueError):
        return np.nan

    if denominator == 0 or np.isnan(denominator):
        return np.nan

    return (float(numerator) / denominator - 1.0) * 100.0


def trade_gross_pnl_pct(direction: str, entry_price: float, current_price: float) -> float:
    if not np.isfinite(entry_price) or not np.isfinite(current_price):
        return np.nan

    if entry_price == 0:
        return np.nan

    if direction == "LONG":
        return (current_price / entry_price - 1.0) * 100.0

    if direction == "SHORT":
        return (entry_price / current_price - 1.0) * 100.0

    return np.nan


def trade_mfe_pct(direction: str, entry_price: float, candle_high: float, candle_low: float) -> float:
    if (
        not np.isfinite(entry_price)
        or not np.isfinite(candle_high)
        or not np.isfinite(candle_low)
        or entry_price == 0
    ):
        return np.nan

    if direction == "LONG":
        return (candle_high / entry_price - 1.0) * 100.0

    if direction == "SHORT":
        return (entry_price / candle_low - 1.0) * 100.0

    return np.nan


def trade_mae_pct(direction: str, entry_price: float, candle_high: float, candle_low: float) -> float:
    if (
        not np.isfinite(entry_price)
        or not np.isfinite(candle_high)
        or not np.isfinite(candle_low)
        or entry_price == 0
    ):
        return np.nan

    if direction == "LONG":
        return (candle_low / entry_price - 1.0) * 100.0

    if direction == "SHORT":
        return (entry_price / candle_high - 1.0) * 100.0

    return np.nan


def current_directional_move_pct(
    direction: str,
    transition_close: float,
    close: float,
) -> float:
    """
    Positive = movement in the major-transition direction.
    Negative = movement against the major-transition direction.
    """

    if (
        not np.isfinite(transition_close)
        or not np.isfinite(close)
        or transition_close == 0
    ):
        return np.nan

    if direction == "LONG":
        return (close / transition_close - 1.0) * 100.0

    if direction == "SHORT":
        return (transition_close / close - 1.0) * 100.0

    return np.nan


def favorable_from_transition_pct(
    direction: str,
    transition_close: float,
    high: float,
    low: float,
) -> float:
    if (
        not np.isfinite(transition_close)
        or not np.isfinite(high)
        or not np.isfinite(low)
        or transition_close == 0
    ):
        return np.nan

    if direction == "LONG":
        return (high / transition_close - 1.0) * 100.0

    if direction == "SHORT":
        return (transition_close / low - 1.0) * 100.0

    return np.nan


def adverse_from_transition_pct(
    direction: str,
    transition_close: float,
    high: float,
    low: float,
) -> float:
    if (
        not np.isfinite(transition_close)
        or not np.isfinite(high)
        or not np.isfinite(low)
        or transition_close == 0
    ):
        return np.nan

    if direction == "LONG":
        return (low / transition_close - 1.0) * 100.0

    if direction == "SHORT":
        return (transition_close / high - 1.0) * 100.0

    return np.nan


# ---------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    require_file(TRAJECTORY_FILE)
    require_file(GEOMETRY_FILE)
    require_file(TRADES_FILE)

    trajectory = pd.read_csv(TRAJECTORY_FILE)
    geometry = pd.read_csv(GEOMETRY_FILE)
    trades = pd.read_csv(TRADES_FILE)

    return trajectory, geometry, trades


# ---------------------------------------------------------------------
# Prepare data
# ---------------------------------------------------------------------

def prepare_trajectory(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    required = [
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

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            "raw_v_trajectory.csv is missing required columns: "
            + ", ".join(missing)
        )

    df["direction"] = df["direction"].map(normalize_direction)

    parse_utc(
        df,
        [
            "transition_known_utc",
            "candle_utc",
        ],
    )

    numeric(
        df,
        [
            "minutes_after_known",
            "open",
            "high",
            "low",
            "close",
            "adverse_from_transition_pct",
            "favorable_from_transition_pct",
            "recovery_from_raw_extreme_pct",
        ],
    )

    df["symbol"] = df["symbol"].astype(str).str.upper()

    df = df[df["symbol"] == "NVDA"].copy()

    df = df.dropna(
        subset=[
            "case_id",
            "direction",
            "transition_known_utc",
            "candle_utc",
            "close",
        ]
    )

    df = df.sort_values(
        [
            "case_id",
            "candle_utc",
        ]
    ).reset_index(drop=True)

    return df


def prepare_geometry(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "case_id" not in df.columns:
        raise ValueError(
            "raw_v_geometry.csv does not contain case_id."
        )

    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.upper()
        df = df[df["symbol"] == "NVDA"].copy()

    if "direction" in df.columns:
        df["direction"] = df["direction"].map(normalize_direction)

    parse_utc(
        df,
        [
            "transition_known_utc",
            "transition_known_utc",
            "extreme_time_utc",
        ],
    )

    numeric(
        df,
        [
            "v_depth_pct",
            "time_to_extreme_minutes",
            "recovery_pct",
            "recovery_minutes",
            "max_favorable_pct",
            "max_adverse_pct",
            "transition_close",
        ],
    )

    # Keep one geometry record per case where possible.
    df = (
        df.sort_values(["case_id"])
        .drop_duplicates("case_id", keep="first")
        .reset_index(drop=True)
    )

    return df


def prepare_trades(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    required = [
        "trade_id",
        "symbol",
        "direction",
        "transition_known_utc",
        "entry_time_utc",
        "entry_price",
        "exit_time_utc",
        "exit_price",
        "pnl_pct",
        "max_favorable_pct",
        "max_adverse_pct",
        "exit_reason",
        "entry_wait_minutes",
        "trade_minutes",
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            "NVDA trade file is missing required columns: "
            + ", ".join(missing)
        )

    df["direction"] = df["direction"].map(normalize_direction)
    df["symbol"] = df["symbol"].astype(str).str.upper()

    parse_utc(
        df,
        [
            "transition_known_utc",
            "transition_known_utc",
            "entry_extreme_time_utc",
            "entry_trigger_time_utc",
            "entry_time_utc",
            "exit_extreme_time_utc",
            "exit_time_utc",
        ],
    )

    numeric(
        df,
        [
            "entry_price",
            "exit_price",
            "pnl_pct",
            "max_favorable_pct",
            "max_adverse_pct",
            "entry_wait_minutes",
            "trade_minutes",
        ],
    )

    df = df[df["symbol"] == "NVDA"].copy()

    df = df.dropna(
        subset=[
            "trade_id",
            "direction",
            "transition_known_utc",
            "entry_time_utc",
            "entry_price",
        ]
    )

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------
# Geometry merge
# ---------------------------------------------------------------------

def merge_geometry(
    trajectory: pd.DataFrame,
    geometry: pd.DataFrame,
) -> pd.DataFrame:

    if geometry.empty:
        return trajectory

    keep_cols = ["case_id"]

    preferred = [
        "v_depth_pct",
        "time_to_extreme_minutes",
        "recovery_pct",
        "recovery_minutes",
        "max_favorable_pct",
        "max_adverse_pct",
        "transition_close",
        "transition_known_utc",
    ]

    for col in preferred:
        if col in geometry.columns:
            keep_cols.append(col)

    geo = geometry[keep_cols].copy()

    merged = trajectory.merge(
        geo,
        on="case_id",
        how="left",
        suffixes=("", "_geometry"),
    )

    # Do not let a missing geometry transition_close break the analysis.
    if "transition_close" not in merged.columns:
        merged["transition_close"] = np.nan

    return merged


# ---------------------------------------------------------------------
# Build causal path
# ---------------------------------------------------------------------

def build_causal_path(
    trajectory: pd.DataFrame,
    trades: pd.DataFrame,
    round_trip_cost_pct: float,
) -> pd.DataFrame:

    # Match the actual #30 trade population to its exact transition.
    trade_cols = [
        "trade_id",
        "symbol",
        "direction",
        "transition_known_utc",
        "entry_time_utc",
        "entry_price",
        "exit_time_utc",
        "exit_price",
        "pnl_pct",
        "max_favorable_pct",
        "max_adverse_pct",
        "exit_reason",
        "entry_wait_minutes",
        "trade_minutes",
    ]

    trade_match = trades[trade_cols].copy()

    merged = trajectory.merge(
        trade_match,
        on=[
            "symbol",
            "direction",
            "transition_known_utc",
        ],
        how="left",
        suffixes=("", "_trade"),
    )

    rows: list[pd.DataFrame] = []

    for case_id, case_df in merged.groupby("case_id", sort=True):

        case_df = case_df.sort_values("candle_utc").copy()

        if case_df.empty:
            continue

        direction = str(case_df["direction"].iloc[0])

        transition_close = np.nan

        if "transition_close" in case_df.columns:
            vals = pd.to_numeric(
                case_df["transition_close"],
                errors="coerce",
            ).dropna()

            if not vals.empty:
                transition_close = float(vals.iloc[0])

        if not np.isfinite(transition_close):
            transition_close = float(case_df["close"].iloc[0])

        # Actual matched trade.
        trade_id = (
            case_df["trade_id"].dropna().iloc[0]
            if case_df["trade_id"].notna().any()
            else np.nan
        )

        entry_time = (
            case_df["entry_time_utc"].dropna().iloc[0]
            if case_df["entry_time_utc"].notna().any()
            else pd.NaT
        )

        entry_price = (
            float(case_df["entry_price"].dropna().iloc[0])
            if case_df["entry_price"].notna().any()
            else np.nan
        )

        eventual_pnl = (
            float(case_df["pnl_pct"].dropna().iloc[0])
            if case_df["pnl_pct"].notna().any()
            else np.nan
        )

        eventual_winner = (
            bool(eventual_pnl > 0)
            if np.isfinite(eventual_pnl)
            else np.nan
        )

        # Causal state variables.
        running_favorable = 0.0
        running_adverse = 0.0

        favorable_prices: list[float] = []
        adverse_prices: list[float] = []

        path_rows = []

        for _, row in case_df.iterrows():

            candle_time = row["candle_utc"]
            candle_open = float(row["open"]) if np.isfinite(row["open"]) else np.nan
            candle_high = float(row["high"]) if np.isfinite(row["high"]) else np.nan
            candle_low = float(row["low"]) if np.isfinite(row["low"]) else np.nan
            candle_close = float(row["close"]) if np.isfinite(row["close"]) else np.nan

            # ---------------------------------------------------------
            # Transition-relative movement
            # ---------------------------------------------------------

            directional_close_move = current_directional_move_pct(
                direction,
                transition_close,
                candle_close,
            )

            favorable_move = favorable_from_transition_pct(
                direction,
                transition_close,
                candle_high,
                candle_low,
            )

            adverse_move = adverse_from_transition_pct(
                direction,
                transition_close,
                candle_high,
                candle_low,
            )

            # Raw favorable/adverse progression.
            if np.isfinite(favorable_move):
                running_favorable = max(
                    running_favorable,
                    favorable_move,
                )

            if np.isfinite(adverse_move):
                # adverse_move is naturally <= 0 for the losing side.
                running_adverse = min(
                    running_adverse,
                    adverse_move,
                )

            # ---------------------------------------------------------
            # Developing V measurements
            # ---------------------------------------------------------

            if direction == "LONG":

                # A developing LONG V begins with a downward/adverse move.
                raw_adverse_depth = min(
                    0.0,
                    adverse_move if np.isfinite(adverse_move) else 0.0,
                )

                adverse_depth_abs = abs(raw_adverse_depth)

                # Current recovery from the lowest point seen so far.
                if np.isfinite(candle_low):
                    adverse_prices.append(candle_low)

                running_adverse_low = (
                    min(adverse_prices)
                    if adverse_prices
                    else np.nan
                )

                recovery_from_adverse_low = (
                    safe_pct(
                        candle_close,
                        running_adverse_low,
                    )
                    if np.isfinite(running_adverse_low)
                    else np.nan
                )

                # Positive directional recovery from the adverse low.
                developing_recovery_pct = (
                    max(0.0, recovery_from_adverse_low)
                    if np.isfinite(recovery_from_adverse_low)
                    else np.nan
                )

            else:

                # A developing SHORT V begins with an upward/adverse move.
                raw_adverse_depth = max(
                    0.0,
                    adverse_move if np.isfinite(adverse_move) else 0.0,
                )

                adverse_depth_abs = abs(raw_adverse_depth)

                if np.isfinite(candle_high):
                    adverse_prices.append(candle_high)

                running_adverse_high = (
                    max(adverse_prices)
                    if adverse_prices
                    else np.nan
                )

                if np.isfinite(running_adverse_high):
                    recovery_from_adverse_low = (
                        safe_pct(
                            running_adverse_high,
                            candle_close,
                        )
                    )
                else:
                    recovery_from_adverse_low = np.nan

                developing_recovery_pct = (
                    max(0.0, recovery_from_adverse_low)
                    if np.isfinite(recovery_from_adverse_low)
                    else np.nan
                )

            # ---------------------------------------------------------
            # Actual trade causal P&L
            # ---------------------------------------------------------

            trade_started = (
                pd.notna(entry_time)
                and pd.notna(candle_time)
                and candle_time >= entry_time
                and np.isfinite(entry_price)
            )

            current_gross_pnl = np.nan
            current_net_pnl = np.nan
            current_mfe = np.nan
            current_mae = np.nan
            minutes_from_entry = np.nan
            cost_covered = np.nan
            cost_buffer = np.nan

            if trade_started:

                current_gross_pnl = trade_gross_pnl_pct(
                    direction,
                    entry_price,
                    candle_close,
                )

                current_mfe = trade_mfe_pct(
                    direction,
                    entry_price,
                    candle_high,
                    candle_low,
                )

                current_mae = trade_mae_pct(
                    direction,
                    entry_price,
                    candle_high,
                    candle_low,
                )

                minutes_from_entry = (
                    candle_time - entry_time
                ).total_seconds() / 60.0

                current_net_pnl = (
                    current_gross_pnl - round_trip_cost_pct
                )

                cost_covered = (
                    bool(
                        np.isfinite(current_gross_pnl)
                        and current_gross_pnl >= round_trip_cost_pct
                    )
                )

                cost_buffer = current_gross_pnl - round_trip_cost_pct

            # ---------------------------------------------------------
            # Explicitly descriptive pullback checkpoints
            #
            # These are observations only.
            # They are NOT exit rules.
            # ---------------------------------------------------------

            if direction == "LONG":
                current_favorable_price = (
                    max(favorable_prices)
                    if favorable_prices
                    else np.nan
                )

                if np.isfinite(candle_high):
                    favorable_prices.append(candle_high)

                current_favorable_price = (
                    max(favorable_prices)
                    if favorable_prices
                    else np.nan
                )

                pullback_from_favorable_top = (
                    safe_pct(
                        candle_close,
                        current_favorable_price,
                    )
                    if np.isfinite(current_favorable_price)
                    else np.nan
                )

                pullback_abs = (
                    abs(pullback_from_favorable_top)
                    if np.isfinite(pullback_from_favorable_top)
                    else np.nan
                )

            else:
                current_favorable_price = (
                    min(favorable_prices)
                    if favorable_prices
                    else np.nan
                )

                if np.isfinite(candle_low):
                    favorable_prices.append(candle_low)

                current_favorable_price = (
                    min(favorable_prices)
                    if favorable_prices
                    else np.nan
                )

                pullback_from_favorable_top = (
                    safe_pct(
                        current_favorable_price,
                        candle_close,
                    )
                    if np.isfinite(current_favorable_price)
                    else np.nan
                )

                pullback_abs = (
                    abs(pullback_from_favorable_top)
                    if np.isfinite(pullback_from_favorable_top)
                    else np.nan
                )

            path_rows.append(
                {
                    "case_id": case_id,
                    "symbol": "NVDA",
                    "direction": direction,
                    "transition_known_utc": row["transition_known_utc"],
                    "candle_utc": candle_time,
                    "minutes_after_known": row["minutes_after_known"],

                    "open": candle_open,
                    "high": candle_high,
                    "low": candle_low,
                    "close": candle_close,

                    "transition_close": transition_close,

                    # Major-direction behavior.
                    "directional_close_move_pct": directional_close_move,
                    "favorable_from_transition_pct": favorable_move,
                    "adverse_from_transition_pct": adverse_move,
                    "running_favorable_pct": running_favorable,
                    "running_adverse_pct": running_adverse,

                    # Developing V.
                    "developing_adverse_depth_pct": adverse_depth_abs,
                    "developing_recovery_from_adverse_extreme_pct":
                        developing_recovery_pct,
                    "pullback_from_favorable_extreme_pct":
                        pullback_abs,

                    # Actual #30 trade reference.
                    "trade_id": trade_id,
                    "entry_time_utc": entry_time,
                    "entry_price": entry_price,

                    # Causal current trade values.
                    "trade_started": trade_started,
                    "minutes_from_entry": minutes_from_entry,
                    "current_gross_pnl_pct": current_gross_pnl,
                    "current_net_pnl_pct": current_net_pnl,
                    "current_mfe_pct": current_mfe,
                    "current_mae_pct": current_mae,
                    "cost_covered": cost_covered,
                    "cost_buffer_pct": cost_buffer,

                    # Hindsight/reference only.
                    "eventual_trade_pnl_pct_hindsight":
                        eventual_pnl,
                    "eventual_trade_winner_hindsight":
                        eventual_winner,

                    # Descriptive checkpoint flags only.
                    "pullback_ge_0_05_pct":
                        bool(
                            np.isfinite(pullback_abs)
                            and pullback_abs >= 0.05
                        ),
                    "pullback_ge_0_10_pct":
                        bool(
                            np.isfinite(pullback_abs)
                            and pullback_abs >= 0.10
                        ),
                    "pullback_ge_0_25_pct":
                        bool(
                            np.isfinite(pullback_abs)
                            and pullback_abs >= 0.25
                        ),
                    "pullback_ge_0_50_pct":
                        bool(
                            np.isfinite(pullback_abs)
                            and pullback_abs >= 0.50
                        ),
                }
            )

        if path_rows:
            rows.append(pd.DataFrame(path_rows))

    if not rows:
        return pd.DataFrame()

    result = pd.concat(rows, ignore_index=True)

    result = result.sort_values(
        [
            "case_id",
            "candle_utc",
        ]
    ).reset_index(drop=True)

    return result


# ---------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------

def build_summary(
    path: pd.DataFrame,
    trades: pd.DataFrame,
    round_trip_cost_pct: float,
) -> pd.DataFrame:

    if path.empty:
        return pd.DataFrame()

    summary_rows: list[dict] = []

    checkpoint_values = [0.05, 0.10, 0.25, 0.50]

    for case_id, case_df in path.groupby("case_id", sort=True):

        case_df = case_df.sort_values("candle_utc").copy()

        first = case_df.iloc[0]

        trade_rows = case_df[
            case_df["trade_started"] == True
        ].copy()

        has_trade = not trade_rows.empty

        eventual_pnl = (
            float(first["eventual_trade_pnl_pct_hindsight"])
            if pd.notna(first["eventual_trade_pnl_pct_hindsight"])
            else np.nan
        )

        eventual_winner = (
            bool(first["eventual_trade_winner_hindsight"])
            if pd.notna(first["eventual_trade_winner_hindsight"])
            else np.nan
        )

        row = {
            "case_id": case_id,
            "symbol": "NVDA",
            "direction": first["direction"],
            "transition_known_utc": first["transition_known_utc"],

            "path_rows": len(case_df),

            "trade_matched": has_trade,

            "trade_id": (
                first["trade_id"]
                if pd.notna(first["trade_id"])
                else np.nan
            ),

            "entry_time_utc": (
                first["entry_time_utc"]
                if pd.notna(first["entry_time_utc"])
                else pd.NaT
            ),

            "entry_price": (
                first["entry_price"]
                if pd.notna(first["entry_price"])
                else np.nan
            ),

            "eventual_trade_pnl_pct_hindsight": eventual_pnl,
            "eventual_trade_winner_hindsight": eventual_winner,

            "max_developing_adverse_depth_pct": (
                case_df["developing_adverse_depth_pct"].max()
            ),

            "max_running_favorable_pct": (
                case_df["running_favorable_pct"].max()
            ),

            "max_pullback_from_favorable_extreme_pct": (
                case_df["pullback_from_favorable_extreme_pct"].max()
            ),
        }

        if has_trade:

            positive_pnl = trade_rows[
                trade_rows["current_gross_pnl_pct"] > 0
            ]

            cost_covered = trade_rows[
                trade_rows["cost_covered"] == True
            ]

            row["first_positive_pnl_utc"] = (
                positive_pnl["candle_utc"].iloc[0]
                if not positive_pnl.empty
                else pd.NaT
            )

            row["first_cost_covered_utc"] = (
                cost_covered["candle_utc"].iloc[0]
                if not cost_covered.empty
                else pd.NaT
            )

            row["first_positive_minutes_from_entry"] = (
                float(
                    positive_pnl["minutes_from_entry"].iloc[0]
                )
                if not positive_pnl.empty
                else np.nan
            )

            row["first_cost_covered_minutes_from_entry"] = (
                float(
                    cost_covered[
                        "minutes_from_entry"
                    ].iloc[0]
                )
                if not cost_covered.empty
                else np.nan
            )

            row["max_current_gross_pnl_pct"] = (
                trade_rows["current_gross_pnl_pct"].max()
            )

            row["min_current_gross_pnl_pct"] = (
                trade_rows["current_gross_pnl_pct"].min()
            )

            row["max_current_mfe_pct"] = (
                trade_rows["current_mfe_pct"].max()
            )

            row["min_current_mae_pct"] = (
                trade_rows["current_mae_pct"].min()
            )

            row["cost_covered_at_any_point"] = (
                not cost_covered.empty
            )

            # First occurrence of each descriptive pullback level.
            for level in checkpoint_values:
                flag_col = (
                    "pullback_ge_"
                    + str(level).replace(".", "_")
                    + "_pct"
                )

                # Actual column names are 0.05 -> 0_05 etc.
                if level == 0.05:
                    flag_col = "pullback_ge_0_05_pct"
                elif level == 0.10:
                    flag_col = "pullback_ge_0_10_pct"
                elif level == 0.25:
                    flag_col = "pullback_ge_0_25_pct"
                elif level == 0.50:
                    flag_col = "pullback_ge_0_50_pct"

                reached = trade_rows[
                    trade_rows[flag_col] == True
                ]

                if not reached.empty:
                    first_reached = reached.iloc[0]

                    row[
                        f"first_pullback_{level:.2f}_utc"
                    ] = first_reached["candle_utc"]

                    row[
                        f"pnl_at_pullback_{level:.2f}_pct"
                    ] = first_reached["current_gross_pnl_pct"]

                    row[
                        f"net_at_pullback_{level:.2f}_pct"
                    ] = first_reached["current_net_pnl_pct"]

                else:
                    row[
                        f"first_pullback_{level:.2f}_utc"
                    ] = pd.NaT

                    row[
                        f"pnl_at_pullback_{level:.2f}_pct"
                    ] = np.nan

                    row[
                        f"net_at_pullback_{level:.2f}_pct"
                    ] = np.nan

        else:

            row["first_positive_pnl_utc"] = pd.NaT
            row["first_cost_covered_utc"] = pd.NaT

            row["first_positive_minutes_from_entry"] = np.nan
            row["first_cost_covered_minutes_from_entry"] = np.nan

            row["max_current_gross_pnl_pct"] = np.nan
            row["min_current_gross_pnl_pct"] = np.nan
            row["max_current_mfe_pct"] = np.nan
            row["min_current_mae_pct"] = np.nan
            row["cost_covered_at_any_point"] = np.nan

            for level in checkpoint_values:
                row[
                    f"first_pullback_{level:.2f}_utc"
                ] = pd.NaT

                row[
                    f"pnl_at_pullback_{level:.2f}_pct"
                ] = np.nan

                row[
                    f"net_at_pullback_{level:.2f}_pct"
                ] = np.nan

        summary_rows.append(row)

    summary = pd.DataFrame(summary_rows)

    # Match a few aggregate trade population facts.
    actual_trade_ids = (
        path["trade_id"]
        .dropna()
        .astype(str)
        .unique()
    )

    summary["matched_trade_count"] = len(actual_trade_ids)

    summary["round_trip_cost_assumption_pct"] = (
        round_trip_cost_pct
    )

    # Keep one summary row per case.
    return summary.sort_values(
        "case_id"
    ).reset_index(drop=True)


# ---------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------

def print_report(
    trajectory: pd.DataFrame,
    path: pd.DataFrame,
    summary: pd.DataFrame,
    trades: pd.DataFrame,
    round_trip_cost_pct: float,
) -> None:

    print()
    print("=" * 78)
    print("EXPERIMENT #37 — NVDA CAUSAL PRICE + P&L + COSTS")
    print("=" * 78)
    print()

    transition_count = (
        trajectory["case_id"]
        .nunique()
        if not trajectory.empty
        else 0
    )

    matched_trade_count = (
        path["trade_id"].dropna().nunique()
        if not path.empty
        else 0
    )

    print(f"NVDA transition cases:        {transition_count}")
    print(f"NVDA path rows:               {len(path)}")
    print(f"NVDA matched #30 trades:      {matched_trade_count}")
    print(f"#30 NVDA source trade rows:   {len(trades)}")
    print(
        f"Round-trip cost assumption:   "
        f"{round_trip_cost_pct:.4f}%"
    )
    print()

    if path.empty:
        print("No causal path rows produced.")
        print()
        return

    # -------------------------------------------------------------
    # Trade-level observations
    # -------------------------------------------------------------

    trade_path = path[
        path["trade_started"] == True
    ].copy()

    print("-" * 78)
    print("CAUSAL TRADE OBSERVATIONS")
    print("-" * 78)

    if trade_path.empty:
        print("No actual trade entry points were matched.")
        print()
    else:
        first_positive = (
            trade_path[
                trade_path["current_gross_pnl_pct"] > 0
            ]
            .groupby("trade_id")
            .first()
        )

        first_cost = (
            trade_path[
                trade_path["cost_covered"] == True
            ]
            .groupby("trade_id")
            .first()
        )

        print(
            f"Trades with some positive gross P&L: "
            f"{len(first_positive)} / {matched_trade_count}"
        )

        print(
            f"Trades that covered cost at some point: "
            f"{len(first_cost)} / {matched_trade_count}"
        )

        print()

        print(
            "Current gross P&L across causal post-entry observations:"
        )
        print(
            f"  median: "
            f"{trade_path['current_gross_pnl_pct'].median():.4f}%"
        )
        print(
            f"  mean:   "
            f"{trade_path['current_gross_pnl_pct'].mean():.4f}%"
        )
        print()

    # -------------------------------------------------------------
    # Pullback checkpoints
    # -------------------------------------------------------------

    print("-" * 78)
    print("PULLBACK CHECKPOINT OBSERVATIONS")
    print("-" * 78)

    checkpoint_map = {
        0.05: "pullback_ge_0_05_pct",
        0.10: "pullback_ge_0_10_pct",
        0.25: "pullback_ge_0_25_pct",
        0.50: "pullback_ge_0_50_pct",
    }

    for level, flag_col in checkpoint_map.items():

        if trade_path.empty:
            print(
                f"{level:.2f}% pullback: no post-entry observations"
            )
            continue

        reached = trade_path[
            trade_path[flag_col] == True
        ].copy()

        if reached.empty:
            print(
                f"{level:.2f}% pullback: no observations reached"
            )
            continue

        first_per_trade = (
            reached
            .sort_values(["trade_id", "candle_utc"])
            .groupby("trade_id")
            .first()
        )

        pnl = first_per_trade[
            "current_gross_pnl_pct"
        ].dropna()

        net = first_per_trade[
            "current_net_pnl_pct"
        ].dropna()

        print(
            f"{level:.2f}% pullback: "
            f"{len(first_per_trade)} trades reached"
        )

        if not pnl.empty:
            print(
                f"    gross P&L at first reach: "
                f"mean={pnl.mean():.4f}%  "
                f"median={pnl.median():.4f}%"
            )

        if not net.empty:
            print(
                f"    net after assumed cost: "
                f"mean={net.mean():.4f}%  "
                f"median={net.median():.4f}%"
            )

    print()

    # -------------------------------------------------------------
    # Eventual result distribution — clearly labeled hindsight
    # -------------------------------------------------------------

    print("-" * 78)
    print("EVENTUAL TRADE RESULT — HINDSIGHT REFERENCE ONLY")
    print("-" * 78)

    eventual = (
        summary["eventual_trade_pnl_pct_hindsight"]
        .dropna()
    )

    if eventual.empty:
        print("No eventual trade results matched.")
    else:
        winners = int((eventual > 0).sum())
        losers = int((eventual <= 0).sum())

        print(f"Matched eventual trades: {len(eventual)}")
        print(f"Winners (>0%):            {winners}")
        print(f"Non-winners (<=0%):       {losers}")
        print(f"Total eventual P&L:      {eventual.sum():.4f}%")
        print(f"Average eventual P&L:    {eventual.mean():.4f}%")
        print(f"Median eventual P&L:     {eventual.median():.4f}%")

    print()

    # -------------------------------------------------------------
    # V behavior
    # -------------------------------------------------------------

    print("-" * 78)
    print("DEVELOPING V OBSERVATIONS")
    print("-" * 78)

    if summary.empty:
        print("No summary rows.")
    else:
        depth = summary[
            "max_developing_adverse_depth_pct"
        ].dropna()

        pullback = summary[
            "max_pullback_from_favorable_extreme_pct"
        ].dropna()

        favorable = summary[
            "max_running_favorable_pct"
        ].dropna()

        if not depth.empty:
            print(
                f"Max developing adverse depth: "
                f"mean={depth.mean():.4f}%  "
                f"median={depth.median():.4f}%"
            )

        if favorable is not None and not favorable.empty:
            print(
                f"Max favorable movement: "
                f"mean={favorable.mean():.4f}%  "
                f"median={favorable.median():.4f}%"
            )

        if pullback is not None and not pullback.empty:
            print(
                f"Max pullback from favorable extreme: "
                f"mean={pullback.mean():.4f}%  "
                f"median={pullback.median():.4f}%"
            )

    print()

    print("=" * 78)
    print("END EXPERIMENT #37")
    print("=" * 78)
    print()


# ---------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------

def write_metadata(
    round_trip_cost_pct: float,
    trajectory: pd.DataFrame,
    path: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with METADATA_OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as f:

        f.write("Experiment #37 — NVDA Causal Price + P&L + Costs\n")
        f.write("=" * 68 + "\n\n")

        f.write("Purpose\n")
        f.write(
            "Walk forward through completed 5-minute candles and "
            "record causal price behavior and actual trade P&L.\n\n"
        )

        f.write("Research rules\n")
        f.write(
            "- Completed candles only.\n"
            "- No future information for causal fields.\n"
            "- No minor/medium/major V classification imposed.\n"
            "- No exit rule tested.\n"
            "- No EXIT + RE-ENTER simulation.\n"
            "- Eventual trade result is hindsight/reference only.\n"
            "- Round-trip cost is an explicit scenario parameter.\n\n"
        )

        f.write("Inputs\n")
        f.write(f"- {TRAJECTORY_FILE}\n")
        f.write(f"- {GEOMETRY_FILE}\n")
        f.write(f"- {TRADES_FILE}\n\n")

        f.write("Outputs\n")
        f.write(f"- {PATH_OUTPUT}\n")
        f.write(f"- {SUMMARY_OUTPUT}\n")
        f.write(f"- {METADATA_OUTPUT}\n\n")

        f.write(
            f"Round-trip cost assumption: "
            f"{round_trip_cost_pct:.6f}%\n"
        )

        f.write(
            f"NVDA transition cases: "
            f"{trajectory['case_id'].nunique() if not trajectory.empty else 0}\n"
        )

        f.write(
            f"Causal path rows: "
            f"{len(path)}\n"
        )

        f.write(
            f"Summary cases: "
            f"{len(summary)}\n"
        )

        f.write(
            "\nNo production files were modified by this experiment.\n"
        )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Experiment #37: NVDA causal price behavior, "
            "P&L, MFE/MAE, and cost coverage."
        )
    )

    parser.add_argument(
        "--round-trip-cost-pct",
        type=float,
        default=0.0,
        help=(
            "Assumed total round-trip trading cost in percent. "
            "Default: 0.0"
        ),
    )

    args = parser.parse_args()

    if args.round_trip_cost_pct < 0:
        raise ValueError(
            "round-trip cost cannot be negative."
        )

    print()
    print("Loading Experiment #37 inputs...")
    print()

    trajectory_raw, geometry_raw, trades_raw = load_inputs()

    print(
        f"Loaded trajectory rows: {len(trajectory_raw)}"
    )
    print(
        f"Loaded geometry rows:   {len(geometry_raw)}"
    )
    print(
        f"Loaded trade rows:      {len(trades_raw)}"
    )
    print()

    trajectory = prepare_trajectory(
        trajectory_raw
    )

    geometry = prepare_geometry(
        geometry_raw
    )

    trades = prepare_trades(
        trades_raw
    )

    print(
        f"NVDA trajectory rows: {len(trajectory)}"
    )
    print(
        f"NVDA geometry rows:   {len(geometry)}"
    )
    print(
        f"NVDA trade rows:      {len(trades)}"
    )
    print()

    trajectory = merge_geometry(
        trajectory,
        geometry,
    )

    path = build_causal_path(
        trajectory,
        trades,
        args.round_trip_cost_pct,
    )

    if path.empty:
        raise RuntimeError(
            "Experiment #37 produced no causal path rows."
        )

    summary = build_summary(
        path,
        trades,
        args.round_trip_cost_pct,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.to_csv(
        PATH_OUTPUT,
        index=False,
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
    )

    write_metadata(
        args.round_trip_cost_pct,
        trajectory,
        path,
        summary,
    )

    print_report(
        trajectory,
        path,
        summary,
        trades,
        args.round_trip_cost_pct,
    )

    print("Files written:")
    print(f"  {PATH_OUTPUT}")
    print(f"  {SUMMARY_OUTPUT}")
    print(f"  {METADATA_OUTPUT}")
    print()


if __name__ == "__main__":
    main()
