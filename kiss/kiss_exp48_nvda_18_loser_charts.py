#!/usr/bin/env python3

"""
AIMn KISS — Experiment #48
NVDA 18-LOSER CHART BOOK

RESEARCH ONLY
=============

No production strategy changes.
No orders.
No AI training.
No parameter promotion.
No re-entry simulation.

QUESTION
========

We have an NVDA KISS backtest containing approximately:

    31 trades
    13 winners
    18 losers

We want to see the ACTUAL price path of every losing trade.

For every losing trade:

    1. Find the real trade metadata.
    2. Find the real 5-minute OHLC candles.
    3. Plot the complete trade path.
    4. Mark entry.
    5. Mark exit.
    6. Mark transition-known time when available.
    7. Mark recorded V events when available.
    8. Calculate:
         - maximum favorable excursion
         - maximum adverse excursion
         - whether trade was ever profitable
         - maximum unrealized P&L
         - minimum unrealized P&L
         - time of maximum favorable excursion
         - time of maximum adverse excursion
    9. Produce a summary CSV.

IMPORTANT
=========

This experiment does NOT decide what the strategy should do.

It only answers:

    "Where did each losing trade actually go wrong?"

That is the information we need before changing STAY / EXIT logic.
"""

from __future__ import annotations

import math
import os
import re
import sys
import traceback
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


# =============================================================================
# PATHS
# =============================================================================

ROOT = Path.home() / "aimn-trade-final"

RESULTS_DIR = ROOT / "kiss" / "results"

OUTPUT_DIR = RESULTS_DIR / "exp48_nvda_18_loser_charts"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# SETTINGS
# =============================================================================

SYMBOL = "NVDA"

TARGET_TOTAL_TRADES = 31
TARGET_LOSERS = 18

# Minutes before entry and after exit shown on the chart.
CHART_PADDING_MINUTES = 30

# Maximum CSV file size we will inspect deeply.
MAX_FILE_MB = 250

# Do not accidentally read our generated files as source.
OUTPUT_NAMES = {
    "nvda_18_loser_summary.csv",
    "nvda_18_loser_trades.csv",
}


# =============================================================================
# COLUMN NORMALIZATION
# =============================================================================

def norm_col(name: str) -> str:
    """
    Normalize a column name so different naming conventions can be matched.
    """
    s = str(name).strip().lower()
    s = s.replace("%", "pct")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def normalized_columns(df: pd.DataFrame) -> dict[str, str]:
    """
    Map normalized column name -> original column name.
    """
    result: dict[str, str] = {}

    for col in df.columns:
        result[norm_col(col)] = col

    return result


def first_existing(
    cmap: dict[str, str],
    candidates: list[str],
) -> Optional[str]:

    for candidate in candidates:

        if candidate in cmap:
            return cmap[candidate]

    return None


# =============================================================================
# TIME COLUMN DISCOVERY
# =============================================================================

TIME_CANDIDATES = [
    "timestamp_utc",
    "candle_utc",
    "datetime_utc",
    "time_utc",
    "date_utc",
    "event_time_utc",
    "entry_time_utc",
    "exit_time_utc",
    "timestamp",
    "datetime",
    "time",
    "date",
]


def find_time_column(
    cmap: dict[str, str],
) -> Optional[str]:

    # Prefer candle / timestamp columns over event times.
    preferred = [
        "timestamp_utc",
        "candle_utc",
        "datetime_utc",
        "time_utc",
        "timestamp",
        "datetime",
        "time",
        "date",
    ]

    col = first_existing(cmap, preferred)

    if col:
        return col

    for candidate in TIME_CANDIDATES:

        col = first_existing(cmap, [candidate])

        if col:
            return col

    return None


# =============================================================================
# TRADE METADATA DISCOVERY
# =============================================================================

def trade_file_score(
    path: Path,
    header: list[str],
) -> int:

    cmap = {norm_col(c): c for c in header}

    score = 0

    has_symbol = first_existing(
        cmap,
        ["symbol", "ticker"],
    )

    has_direction = first_existing(
        cmap,
        ["direction", "side", "position_side", "trade_direction"],
    )

    has_entry_time = first_existing(
        cmap,
        [
            "entry_time_utc",
            "entry_time",
            "entry_timestamp_utc",
            "entry_timestamp",
            "open_time_utc",
            "open_time",
        ],
    )

    has_exit_time = first_existing(
        cmap,
        [
            "exit_time_utc",
            "exit_time",
            "exit_timestamp_utc",
            "exit_timestamp",
            "close_time_utc",
            "close_time",
        ],
    )

    has_entry_price = first_existing(
        cmap,
        [
            "entry_price",
            "buy_price",
            "entry",
            "open_price",
        ],
    )

    has_exit_price = first_existing(
        cmap,
        [
            "exit_price",
            "sell_price",
            "exit",
            "close_price",
        ],
    )

    has_pnl = first_existing(
        cmap,
        [
            "pnl_pct",
            "pnl_percent",
            "return_pct",
            "return_percent",
            "profit_pct",
            "profit_percent",
            "trade_pnl_pct",
            "net_pnl_pct",
            "gross_pnl_pct",
            "pnl",
        ],
    )

    has_trade_id = first_existing(
        cmap,
        [
            "trade_id",
            "id",
            "trade",
        ],
    )

    if has_symbol:
        score += 40

    if has_direction:
        score += 30

    if has_entry_time:
        score += 50

    if has_exit_time:
        score += 50

    if has_entry_price:
        score += 25

    if has_exit_price:
        score += 25

    if has_pnl:
        score += 50

    if has_trade_id:
        score += 25

    name = path.name.lower()

    if "trade" in name:
        score += 20

    if "backtest" in name:
        score += 20

    if "result" in name:
        score += 10

    if "summary" in name:
        score += 5

    # Penalize known trajectory/event files.
    if "trajectory" in name:
        score -= 60

    if "v_" in name:
        score -= 40

    if "events" in name:
        score -= 40

    return score


# =============================================================================
# CANDLE DATA DISCOVERY
# =============================================================================

def candle_file_score(
    path: Path,
    header: list[str],
) -> int:

    cmap = {norm_col(c): c for c in header}

    score = 0

    timestamp = first_existing(
        cmap,
        [
            "timestamp_utc",
            "candle_utc",
            "datetime_utc",
            "time_utc",
            "timestamp",
            "datetime",
            "time",
        ],
    )

    symbol = first_existing(
        cmap,
        [
            "symbol",
            "ticker",
        ],
    )

    open_col = first_existing(
        cmap,
        ["open", "o"],
    )

    high_col = first_existing(
        cmap,
        ["high", "h"],
    )

    low_col = first_existing(
        cmap,
        ["low", "l"],
    )

    close_col = first_existing(
        cmap,
        ["close", "c"],
    )

    volume_col = first_existing(
        cmap,
        ["volume", "vol", "v"],
    )

    if timestamp:
        score += 50

    if symbol:
        score += 30

    if open_col:
        score += 25

    if high_col:
        score += 25

    if low_col:
        score += 25

    if close_col:
        score += 25

    if volume_col:
        score += 5

    name = path.name.lower()

    if "5m" in name or "5_min" in name or "5minute" in name:
        score += 50

    if "candles" in name:
        score += 20

    if "ohlc" in name:
        score += 20

    if "market" in name:
        score += 10

    # The transition-relative raw trajectory is useful research data,
    # but it is NOT preferred as the full trade candle source.
    if "raw_v_trajectory" in name:
        score -= 100

    if "trajectory" in name:
        score -= 40

    return score


# =============================================================================
# CSV HEADER DISCOVERY
# =============================================================================

def discover_csv_files() -> list[Path]:

    files: list[Path] = []

    for path in RESULTS_DIR.rglob("*.csv"):

        if not path.is_file():
            continue

        if path.name in OUTPUT_NAMES:
            continue

        try:
            size_mb = path.stat().st_size / (1024 * 1024)

            if size_mb > MAX_FILE_MB:
                continue

        except OSError:
            continue

        files.append(path)

    return files


def read_header(path: Path) -> list[str]:

    try:

        df = pd.read_csv(
            path,
            nrows=0,
            encoding="utf-8",
        )

        return list(df.columns)

    except Exception:

        return []


# =============================================================================
# DISCOVER BEST SOURCE FILES
# =============================================================================

def discover_sources():

    print("=" * 110)
    print("AIMn KISS — EXPERIMENT #48")
    print("NVDA 18-LOSER CHART BOOK")
    print("=" * 110)

    print()
    print("Research only.")
    print("No production strategy changes.")
    print("No orders.")
    print("No AI.")
    print("No parameter promotion.")
    print()

    print("-" * 110)
    print("SOURCE DISCOVERY")
    print("-" * 110)

    files = discover_csv_files()

    print(f"CSV files inspected: {len(files)}")

    trade_candidates = []
    candle_candidates = []

    for path in files:

        header = read_header(path)

        if not header:
            continue

        tscore = trade_file_score(path, header)
        cscore = candle_file_score(path, header)

        if tscore > 100:
            trade_candidates.append(
                (tscore, path, header)
            )

        if cscore > 100:
            candle_candidates.append(
                (cscore, path, header)
            )

    trade_candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    candle_candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    print()
    print("TOP TRADE METADATA CANDIDATES")
    print()

    for score, path, header in trade_candidates[:10]:

        print(
            f"score={score:4d} "
            f"rows=? "
            f"{path}"
        )

    print()
    print("TOP 5-MINUTE CANDLE CANDIDATES")
    print()

    for score, path, header in candle_candidates[:10]:

        print(
            f"score={score:4d} "
            f"rows=? "
            f"{path}"
        )

    if not trade_candidates:

        raise RuntimeError(
            "Could not find a trade metadata CSV. "
            "Need a CSV containing entry time, exit time, direction "
            "and P&L or entry/exit prices."
        )

    if not candle_candidates:

        raise RuntimeError(
            "Could not find a 5-minute OHLC candle CSV."
        )

    trade_path = trade_candidates[0][1]
    trade_header = trade_candidates[0][2]

    candle_path = candle_candidates[0][1]
    candle_header = candle_candidates[0][2]

    print()
    print("-" * 110)
    print("SELECTED SOURCES")
    print("-" * 110)

    print(f"Trade metadata:")
    print(f"  {trade_path}")

    print()
    print(f"5-minute candles:")
    print(f"  {candle_path}")

    return (
        trade_path,
        trade_header,
        candle_path,
        candle_header,
    )


# =============================================================================
# LOAD TRADE METADATA
# =============================================================================

def load_trade_metadata(path: Path) -> pd.DataFrame:

    print()
    print("-" * 110)
    print("LOADING TRADE METADATA")
    print("-" * 110)

    df = pd.read_csv(path)

    print(f"Rows loaded: {len(df):,}")

    cmap = normalized_columns(df)

    symbol_col = first_existing(
        cmap,
        ["symbol", "ticker"],
    )

    direction_col = first_existing(
        cmap,
        [
            "direction",
            "side",
            "position_side",
            "trade_direction",
        ],
    )

    trade_id_col = first_existing(
        cmap,
        [
            "trade_id",
            "id",
            "trade",
        ],
    )

    entry_time_col = first_existing(
        cmap,
        [
            "entry_time_utc",
            "entry_time",
            "entry_timestamp_utc",
            "entry_timestamp",
            "open_time_utc",
            "open_time",
        ],
    )

    exit_time_col = first_existing(
        cmap,
        [
            "exit_time_utc",
            "exit_time",
            "exit_timestamp_utc",
            "exit_timestamp",
            "close_time_utc",
            "close_time",
        ],
    )

    entry_price_col = first_existing(
        cmap,
        [
            "entry_price",
            "buy_price",
            "entry",
            "open_price",
        ],
    )

    exit_price_col = first_existing(
        cmap,
        [
            "exit_price",
            "sell_price",
            "exit",
            "close_price",
        ],
    )

    pnl_col = first_existing(
        cmap,
        [
            "pnl_pct",
            "pnl_percent",
            "return_pct",
            "return_percent",
            "profit_pct",
            "profit_percent",
            "trade_pnl_pct",
            "net_pnl_pct",
            "gross_pnl_pct",
            "pnl",
        ],
    )

    transition_col = first_existing(
        cmap,
        [
            "transition_known_utc",
            "transition_time_utc",
            "transition_utc",
            "transition_time",
            "transition_timestamp_utc",
        ],
    )

    print()
    print("Column mapping:")

    print(f"  symbol       = {symbol_col}")
    print(f"  direction    = {direction_col}")
    print(f"  trade_id     = {trade_id_col}")
    print(f"  entry time   = {entry_time_col}")
    print(f"  exit time    = {exit_time_col}")
    print(f"  entry price  = {entry_price_col}")
    print(f"  exit price   = {exit_price_col}")
    print(f"  P&L          = {pnl_col}")
    print(f"  transition   = {transition_col}")

    required = [
        ("symbol", symbol_col),
        ("direction", direction_col),
        ("entry_time", entry_time_col),
        ("exit_time", exit_time_col),
    ]

    missing = [
        name
        for name, col in required
        if col is None
    ]

    if missing:

        raise RuntimeError(
            "Trade metadata missing required fields: "
            + ", ".join(missing)
        )

    # Rename into a stable internal structure.
    out = pd.DataFrame()

    out["symbol"] = df[symbol_col].astype(str).str.upper().str.strip()

    out["direction"] = (
        df[direction_col]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    if trade_id_col:

        out["trade_id"] = (
            df[trade_id_col]
            .astype(str)
            .str.strip()
        )

    else:

        out["trade_id"] = [
            f"TRADE-{i + 1:03d}"
            for i in range(len(df))
        ]

    out["entry_time"] = pd.to_datetime(
        df[entry_time_col],
        utc=True,
        errors="coerce",
    )

    out["exit_time"] = pd.to_datetime(
        df[exit_time_col],
        utc=True,
        errors="coerce",
    )

    if entry_price_col:

        out["entry_price"] = pd.to_numeric(
            df[entry_price_col],
            errors="coerce",
        )

    else:

        out["entry_price"] = np.nan

    if exit_price_col:

        out["exit_price"] = pd.to_numeric(
            df[exit_price_col],
            errors="coerce",
        )

    else:

        out["exit_price"] = np.nan

    if pnl_col:

        out["pnl_pct"] = pd.to_numeric(
            df[pnl_col],
            errors="coerce",
        )

    else:

        out["pnl_pct"] = np.nan

    if transition_col:

        out["transition_time"] = pd.to_datetime(
            df[transition_col],
            utc=True,
            errors="coerce",
        )

    else:

        out["transition_time"] = pd.NaT

    # Keep only actual NVDA.
    out = out[
        out["symbol"].eq(SYMBOL)
    ].copy()

    # Remove rows without usable times.
    out = out[
        out["entry_time"].notna()
        & out["exit_time"].notna()
    ].copy()

    # Calculate P&L from prices if necessary.
    def calc_price_pnl(row):

        if pd.notna(row["pnl_pct"]):
            return float(row["pnl_pct"])

        entry = row["entry_price"]
        exit_ = row["exit_price"]

        if not np.isfinite(entry) or not np.isfinite(exit_):
            return np.nan

        direction = row["direction"]

        if "SHORT" in direction:

            return (
                (entry - exit_) / entry
            ) * 100.0

        return (
            (exit_ - entry) / entry
        ) * 100.0

    out["pnl_pct"] = out.apply(
        calc_price_pnl,
        axis=1,
    )

    # Determine loser/winner using available P&L.
    out["is_loser"] = out["pnl_pct"] < 0

    out["is_winner"] = out["pnl_pct"] > 0

    out = out.sort_values(
        ["entry_time", "exit_time"]
    ).reset_index(drop=True)

    print()
    print("NVDA trade count:")
    print(f"  Total:   {len(out)}")
    print(
        f"  Winners: {(out['pnl_pct'] > 0).sum()}"
    )
    print(
        f"  Losers:  {(out['pnl_pct'] < 0).sum()}"
    )
    print(
        f"  Flat:    {(out['pnl_pct'] == 0).sum()}"
    )

    return out


# =============================================================================
# LOAD CANDLES
# =============================================================================

def load_candles(
    path: Path,
) -> pd.DataFrame:

    print()
    print("-" * 110)
    print("LOADING 5-MINUTE CANDLES")
    print("-" * 110)

    df = pd.read_csv(path)

    print(f"Rows loaded: {len(df):,}")

    cmap = normalized_columns(df)

    time_col = first_existing(
        cmap,
        [
            "timestamp_utc",
            "candle_utc",
            "datetime_utc",
            "time_utc",
            "timestamp",
            "datetime",
            "time",
        ],
    )

    symbol_col = first_existing(
        cmap,
        [
            "symbol",
            "ticker",
        ],
    )

    open_col = first_existing(
        cmap,
        ["open", "o"],
    )

    high_col = first_existing(
        cmap,
        ["high", "h"],
    )

    low_col = first_existing(
        cmap,
        ["low", "l"],
    )

    close_col = first_existing(
        cmap,
        ["close", "c"],
    )

    volume_col = first_existing(
        cmap,
        ["volume", "vol", "v"],
    )

    if not time_col:

        raise RuntimeError(
            f"5-minute candle file has no timestamp column: {path}"
        )

    required = {
        "open": open_col,
        "high": high_col,
        "low": low_col,
        "close": close_col,
    }

    missing = [
        k
        for k, v in required.items()
        if v is None
    ]

    if missing:

        raise RuntimeError(
            "5-minute candle file missing OHLC columns: "
            + ", ".join(missing)
        )

    out = pd.DataFrame()

    out["timestamp"] = pd.to_datetime(
        df[time_col],
        utc=True,
        errors="coerce",
    )

    if symbol_col:

        out["symbol"] = (
            df[symbol_col]
            .astype(str)
            .str.upper()
            .str.strip()
        )

    else:

        out["symbol"] = SYMBOL

    out["open"] = pd.to_numeric(
        df[open_col],
        errors="coerce",
    )

    out["high"] = pd.to_numeric(
        df[high_col],
        errors="coerce",
    )

    out["low"] = pd.to_numeric(
        df[low_col],
        errors="coerce",
    )

    out["close"] = pd.to_numeric(
        df[close_col],
        errors="coerce",
    )

    if volume_col:

        out["volume"] = pd.to_numeric(
            df[volume_col],
            errors="coerce",
        )

    out = out[
        out["timestamp"].notna()
        & np.isfinite(out["open"])
        & np.isfinite(out["high"])
        & np.isfinite(out["low"])
        & np.isfinite(out["close"])
    ].copy()

    out = out[
        out["symbol"].eq(SYMBOL)
    ].copy()

    out = out.sort_values(
        "timestamp"
    ).drop_duplicates(
        "timestamp",
        keep="last",
    ).reset_index(drop=True)

    print(f"Usable NVDA candles: {len(out):,}")

    if len(out) >= 10:

        diffs = (
            out["timestamp"]
            .diff()
            .dropna()
            .dt.total_seconds()
            .div(60)
        )

        median_minutes = diffs.median()

        print(
            f"Median candle spacing: "
            f"{median_minutes:.2f} minutes"
        )

    return out


# =============================================================================
# #42 V EVENTS
# =============================================================================

def load_v_events() -> pd.DataFrame:

    candidates = [
        RESULTS_DIR
        / "exp42_v_peak_divergence"
        / "nvda_v_peak_divergence_transitions.csv",

        RESULTS_DIR
        / "exp46_not_yet_profitable_v"
        / "nvda_not_yet_profitable_v_events.csv",
    ]

    selected = None

    for path in candidates:

        if path.exists():

            selected = path
            break

    if selected is None:

        print()
        print("No #42/#46 V-event file found.")
        return pd.DataFrame()

    print()
    print("-" * 110)
    print("LOADING V EVENTS")
    print("-" * 110)

    print(selected)

    try:

        df = pd.read_csv(selected)

    except Exception as exc:

        print(
            f"Could not load V events: {exc}"
        )

        return pd.DataFrame()

    cmap = normalized_columns(df)

    trade_id_col = first_existing(
        cmap,
        [
            "trade_id",
            "id",
            "trade",
        ],
    )

    event_time_col = first_existing(
        cmap,
        [
            "event_time_utc",
            "event_time",
            "v_time_utc",
            "v_time",
        ],
    )

    if (
        trade_id_col is None
        or event_time_col is None
    ):

        print(
            "V-event file does not have "
            "trade_id + event_time."
        )

        return pd.DataFrame()

    out = pd.DataFrame()

    out["trade_id"] = (
        df[trade_id_col]
        .astype(str)
        .str.strip()
    )

    out["event_time"] = pd.to_datetime(
        df[event_time_col],
        utc=True,
        errors="coerce",
    )

    out = out[
        out["event_time"].notna()
    ].copy()

    print(
        f"V events loaded: {len(out):,}"
    )

    return out


# =============================================================================
# TRANSITION MATCHING
# =============================================================================

def attach_transition_times(
    trades: pd.DataFrame,
    v_events: pd.DataFrame,
) -> pd.DataFrame:

    trades = trades.copy()

    # First use transition directly from trade metadata.
    # Then fall back to the earliest V event for that trade,
    # which is useful for visual context only.

    if len(v_events) == 0:

        return trades

    first_v = (
        v_events
        .sort_values("event_time")
        .groupby("trade_id", as_index=False)
        .first()
    )

    first_v = first_v[
        ["trade_id", "event_time"]
    ].rename(
        columns={
            "event_time":
                "first_v_time"
        }
    )

    trades = trades.merge(
        first_v,
        on="trade_id",
        how="left",
    )

    return trades


# =============================================================================
# P&L PATH
# =============================================================================

def calculate_trade_path(
    candles: pd.DataFrame,
    trade: pd.Series,
) -> Optional[pd.DataFrame]:

    entry_time = trade["entry_time"]
    exit_time = trade["exit_time"]
    direction = str(
        trade["direction"]
    ).upper()

    if pd.isna(entry_time) or pd.isna(exit_time):
        return None

    # Include a little context around the actual trade.
    start = (
        entry_time
        - pd.Timedelta(
            minutes=CHART_PADDING_MINUTES
        )
    )

    end = (
        exit_time
        + pd.Timedelta(
            minutes=CHART_PADDING_MINUTES
        )
    )

    path = candles[
        candles["timestamp"].between(
            start,
            end,
        )
    ].copy()

    if len(path) == 0:
        return None

    entry_price = trade["entry_price"]

    if not np.isfinite(entry_price):

        # Find nearest close before/at entry.
        idx = (
            np.abs(
                (
                    path["timestamp"]
                    - entry_time
                ).dt.total_seconds()
            )
        ).argmin()

        entry_price = float(
            path.iloc[idx]["close"]
        )

    if not np.isfinite(entry_price):
        return None

    if "SHORT" in direction:

        path["pnl_pct_path"] = (
            (
                entry_price
                - path["close"]
            )
            / entry_price
            * 100.0
        )

    else:

        path["pnl_pct_path"] = (
            (
                path["close"]
                - entry_price
            )
            / entry_price
            * 100.0
        )

    return path


# =============================================================================
# MFE / MAE
# =============================================================================

def excursion_stats(
    path: pd.DataFrame,
    trade: pd.Series,
):

    entry_time = trade["entry_time"]
    exit_time = trade["exit_time"]

    direction = str(
        trade["direction"]
    ).upper()

    entry_price = trade["entry_price"]

    if not np.isfinite(entry_price):

        # Use closest candle to entry.
        idx = (
            np.abs(
                (
                    path["timestamp"]
                    - entry_time
                ).dt.total_seconds()
            )
        ).argmin()

        entry_price = float(
            path.iloc[idx]["close"]
        )

    trade_candles = path[
        path["timestamp"].between(
            entry_time,
            exit_time,
        )
    ].copy()

    if len(trade_candles) == 0:

        return {
            "mfe_pct": np.nan,
            "mae_pct": np.nan,
            "mfe_time": pd.NaT,
            "mae_time": pd.NaT,
            "ever_positive": False,
            "first_positive_time": pd.NaT,
            "time_to_mfe_min": np.nan,
            "time_to_mae_min": np.nan,
        }

    if "SHORT" in direction:

        trade_candles["high_pnl_pct"] = (
            (
                entry_price
                - trade_candles["low"]
            )
            / entry_price
            * 100.0
        )

        trade_candles["low_pnl_pct"] = (
            (
                entry_price
                - trade_candles["high"]
            )
            / entry_price
            * 100.0
        )

    else:

        trade_candles["high_pnl_pct"] = (
            (
                trade_candles["high"]
                - entry_price
            )
            / entry_price
            * 100.0
        )

        trade_candles["low_pnl_pct"] = (
            (
                trade_candles["low"]
                - entry_price
            )
            / entry_price
            * 100.0
        )

    mfe_idx = (
        trade_candles["high_pnl_pct"]
        .idxmax()
    )

    mae_idx = (
        trade_candles["low_pnl_pct"]
        .idxmin()
    )

    mfe = float(
        trade_candles.loc[
            mfe_idx,
            "high_pnl_pct",
        ]
    )

    mae = float(
        trade_candles.loc[
            mae_idx,
            "low_pnl_pct",
        ]
    )

    mfe_time = trade_candles.loc[
        mfe_idx,
        "timestamp",
    ]

    mae_time = trade_candles.loc[
        mae_idx,
        "timestamp",
    ]

    positive_rows = trade_candles[
        trade_candles["pnl_pct_path"] > 0
    ]

    if len(positive_rows):

        first_positive_time = (
            positive_rows.iloc[0]["timestamp"]
        )

        ever_positive = True

    else:

        first_positive_time = pd.NaT
        ever_positive = False

    time_to_mfe = (
        mfe_time - entry_time
    ).total_seconds() / 60.0

    time_to_mae = (
        mae_time - entry_time
    ).total_seconds() / 60.0

    return {
        "mfe_pct": mfe,
        "mae_pct": mae,
        "mfe_time": mfe_time,
        "mae_time": mae_time,
        "ever_positive": ever_positive,
        "first_positive_time":
            first_positive_time,
        "time_to_mfe_min":
            time_to_mfe,
        "time_to_mae_min":
            time_to_mae,
    }


# =============================================================================
# CANDLE DRAWING
# =============================================================================

def draw_candles(
    ax,
    path: pd.DataFrame,
):

    if len(path) == 0:
        return

    timestamps = path["timestamp"]

    x = np.arange(len(path))

    width = 0.65

    for i, row in enumerate(
        path.itertuples(index=False)
    ):

        o = float(row.open)
        h = float(row.high)
        l = float(row.low)
        c = float(row.close)

        # Use default matplotlib colors.
        rising = c >= o

        body_low = min(o, c)
        body_high = max(o, c)
        body_height = body_high - body_low

        if body_height == 0:
            body_height = max(
                abs(c) * 0.00001,
                1e-8,
            )

        # Wick
        ax.plot(
            [i, i],
            [l, h],
            linewidth=0.8,
            alpha=0.8,
        )

        # Body
        rect = Rectangle(
            (
                i - width / 2,
                body_low,
            ),
            width,
            body_height,
            fill=rising,
            alpha=0.65,
        )

        ax.add_patch(rect)

    ax.set_xlim(
        -1,
        len(path),
    )


# =============================================================================
# FORMAT TIME AXIS
# =============================================================================

def format_time_axis(
    ax,
    path: pd.DataFrame,
):

    if len(path) == 0:
        return

    # Use a manageable number of labels.
    n = len(path)

    if n <= 20:
        step = 1
    elif n <= 60:
        step = 5
    elif n <= 120:
        step = 10
    else:
        step = max(
            1,
            n // 12,
        )

    indices = list(
        range(
            0,
            n,
            step,
        )
    )

    labels = []

    for i in indices:

        t = path.iloc[i]["timestamp"]

        labels.append(
            t.strftime(
                "%m-%d\n%H:%M"
            )
        )

    ax.set_xticks(indices)
    ax.set_xticklabels(
        labels,
        rotation=0,
        fontsize=8,
    )


# =============================================================================
# SINGLE LOSER CHART
# =============================================================================

def create_loser_chart(
    trade: pd.Series,
    path: pd.DataFrame,
    stats: dict,
    v_events: pd.DataFrame,
    output_path: Path,
):

    fig, ax = plt.subplots(
        figsize=(15, 8)
    )

    draw_candles(
        ax,
        path,
    )

    # -------------------------------------------------
    # Entry / exit positions
    # -------------------------------------------------

    timestamps = path["timestamp"]

    def nearest_x(timestamp):

        differences = (
            np.abs(
                (
                    timestamps
                    - timestamp
                ).dt.total_seconds()
            )
        )

        return int(
            differences.idxmin()
        ) if len(differences) else None

    entry_x = nearest_x(
        trade["entry_time"]
    )

    exit_x = nearest_x(
        trade["exit_time"]
    )

    if entry_x is not None:

        ax.axvline(
            entry_x,
            linewidth=2.0,
            linestyle="--",
        )

        y_entry = float(
            path["high"].max()
        )

        ax.annotate(
            "ENTRY",
            xy=(
                entry_x,
                y_entry,
            ),
            xytext=(
                entry_x,
                y_entry,
            ),
            rotation=90,
            va="top",
            fontsize=9,
        )

    if exit_x is not None:

        ax.axvline(
            exit_x,
            linewidth=2.0,
            linestyle="--",
        )

        y_exit = float(
            path["low"].min()
        )

        ax.annotate(
            "EXIT",
            xy=(
                exit_x,
                y_exit,
            ),
            xytext=(
                exit_x,
                y_exit,
            ),
            rotation=90,
            va="bottom",
            fontsize=9,
        )

    # -------------------------------------------------
    # Transition / first V
    # -------------------------------------------------

    transition_time = trade.get(
        "transition_time",
        pd.NaT,
    )

    if pd.notna(transition_time):

        transition_x = nearest_x(
            transition_time
        )

        if transition_x is not None:

            ax.axvline(
                transition_x,
                linewidth=1.5,
                linestyle=":",
                alpha=0.8,
            )

            ax.annotate(
                "TRANSITION",
                xy=(
                    transition_x,
                    float(path["high"].max()),
                ),
                rotation=90,
                va="top",
                fontsize=8,
            )

    # -------------------------------------------------
    # V events
    # -------------------------------------------------

    trade_id = str(
        trade["trade_id"]
    )

    if len(v_events):

        own_events = v_events[
            v_events["trade_id"]
            .astype(str)
            .eq(trade_id)
        ].sort_values(
            "event_time"
        )

    else:

        own_events = pd.DataFrame()

    for number, event in enumerate(
        own_events.itertuples(
            index=False
        ),
        start=1,
    ):

        vx = nearest_x(
            event.event_time
        )

        if vx is None:
            continue

        # Avoid overpowering the chart.
        ax.axvline(
            vx,
            linewidth=1.0,
            linestyle="-.",
            alpha=0.55,
        )

        ax.annotate(
            f"V{number}",
            xy=(
                vx,
                float(path["high"].max()),
            ),
            rotation=90,
            va="top",
            fontsize=8,
        )

    # -------------------------------------------------
    # MFE / MAE markers
    # -------------------------------------------------

    mfe_x = nearest_x(
        stats["mfe_time"]
    )

    mae_x = nearest_x(
        stats["mae_time"]
    )

    if mfe_x is not None:

        mfe_price = float(
            path.iloc[mfe_x]["high"]
        )

        ax.scatter(
            [mfe_x],
            [mfe_price],
            s=70,
            marker="^",
            zorder=5,
        )

        ax.annotate(
            f"MFE {stats['mfe_pct']:.3f}%",
            (
                mfe_x,
                mfe_price,
            ),
            xytext=(
                8,
                8,
            ),
            textcoords="offset points",
            fontsize=9,
        )

    if mae_x is not None:

        mae_price = float(
            path.iloc[mae_x]["low"]
        )

        ax.scatter(
            [mae_x],
            [mae_price],
            s=70,
            marker="v",
            zorder=5,
        )

        ax.annotate(
            f"MAE {stats['mae_pct']:.3f}%",
            (
                mae_x,
                mae_price,
            ),
            xytext=(
                8,
                -15,
            ),
            textcoords="offset points",
            fontsize=9,
        )

    # -------------------------------------------------
    # Title
    # -------------------------------------------------

    direction = str(
        trade["direction"]
    ).upper()

    final_pnl = float(
        trade["pnl_pct"]
    )

    ever_positive = (
        "YES"
        if stats["ever_positive"]
        else "NO"
    )

    title = (
        f"NVDA LOSS — {trade_id} — {direction}\n"
        f"Final P&L {final_pnl:+.3f}%   |   "
        f"MFE {stats['mfe_pct']:+.3f}%   |   "
        f"MAE {stats['mae_pct']:+.3f}%   |   "
        f"Ever profitable: {ever_positive}"
    )

    ax.set_title(
        title,
        fontsize=13,
        pad=12,
    )

    ax.set_ylabel(
        "NVDA Price"
    )

    ax.set_xlabel(
        "UTC"
    )

    format_time_axis(
        ax,
        path,
    )

    ax.grid(
        True,
        alpha=0.25,
    )

    fig.tight_layout()

    fig.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight",
    )

    plt.close(fig)


# =============================================================================
# MAIN ANALYSIS
# =============================================================================

def main():

    try:

        (
            trade_path,
            _trade_header,
            candle_path,
            _candle_header,
        ) = discover_sources()

        trades = load_trade_metadata(
            trade_path
        )

        candles = load_candles(
            candle_path
        )

        v_events = load_v_events()

        trades = attach_transition_times(
            trades,
            v_events,
        )

        # -------------------------------------------------
        # Select losing trades.
        # -------------------------------------------------

        losers = trades[
            trades["is_loser"]
        ].copy()

        losers = losers.sort_values(
            "pnl_pct"
        ).reset_index(drop=True)

        print()
        print("=" * 110)
        print("NVDA LOSER SET")
        print("=" * 110)

        print(
            f"Total trades discovered : {len(trades)}"
        )

        print(
            f"Losers discovered        : {len(losers)}"
        )

        print(
            f"Target losers            : {TARGET_LOSERS}"
        )

        print()

        # -------------------------------------------------
        # Process every loser.
        # -------------------------------------------------

        rows = []

        chart_count = 0

        for loser_number, (_, trade) in enumerate(
            losers.iterrows(),
            start=1,
        ):

            print(
                f"[{loser_number:02d}/{len(losers):02d}] "
                f"{trade['trade_id']} "
                f"{trade['direction']} "
                f"P&L={trade['pnl_pct']:+.4f}%"
            )

            path = calculate_trade_path(
                candles,
                trade,
            )

            if path is None:

                print(
                    "    NO CANDLE DATA"
                )

                rows.append(
                    {
                        "trade_id":
                            trade["trade_id"],
                        "direction":
                            trade["direction"],
                        "entry_time_utc":
                            trade["entry_time"],
                        "exit_time_utc":
                            trade["exit_time"],
                        "final_pnl_pct":
                            trade["pnl_pct"],
                        "mfe_pct":
                            np.nan,
                        "mae_pct":
                            np.nan,
                        "ever_profitable":
                            False,
                        "first_positive_time_utc":
                            pd.NaT,
                        "mfe_time_utc":
                            pd.NaT,
                        "mae_time_utc":
                            pd.NaT,
                        "time_to_mfe_min":
                            np.nan,
                        "time_to_mae_min":
                            np.nan,
                        "chart_created":
                            False,
                    }
                )

                continue

            stats = excursion_stats(
                path,
                trade,
            )

            output_name = (
                f"{loser_number:02d}_"
                f"{trade['trade_id']}_"
                f"{str(trade['direction']).upper()}_"
                f"LOSS.png"
            )

            output_path = (
                OUTPUT_DIR
                / output_name
            )

            try:

                create_loser_chart(
                    trade=trade,
                    path=path,
                    stats=stats,
                    v_events=v_events,
                    output_path=output_path,
                )

                chart_created = True
                chart_count += 1

                print(
                    f"    MFE={stats['mfe_pct']:+.4f}% "
                    f"MAE={stats['mae_pct']:+.4f}% "
                    f"EverProfit={stats['ever_positive']}"
                )

                print(
                    f"    Chart: {output_path.name}"
                )

            except Exception as exc:

                chart_created = False

                print(
                    f"    CHART ERROR: {exc}"
                )

            rows.append(
                {
                    "trade_id":
                        trade["trade_id"],
                    "direction":
                        trade["direction"],
                    "entry_time_utc":
                        trade["entry_time"],
                    "exit_time_utc":
                        trade["exit_time"],
                    "transition_time_utc":
                        trade.get(
                            "transition_time",
                            pd.NaT,
                        ),
                    "first_v_time_utc":
                        trade.get(
                            "first_v_time",
                            pd.NaT,
                        ),
                    "entry_price":
                        trade["entry_price"],
                    "exit_price":
                        trade["exit_price"],
                    "final_pnl_pct":
                        trade["pnl_pct"],
                    "mfe_pct":
                        stats["mfe_pct"],
                    "mae_pct":
                        stats["mae_pct"],
                    "ever_profitable":
                        stats["ever_positive"],
                    "first_positive_time_utc":
                        stats[
                            "first_positive_time"
                        ],
                    "mfe_time_utc":
                        stats["mfe_time"],
                    "mae_time_utc":
                        stats["mae_time"],
                    "time_to_mfe_min":
                        stats["time_to_mfe_min"],
                    "time_to_mae_min":
                        stats["time_to_mae_min"],
                    "chart_created":
                        chart_created,
                }
            )

        # -------------------------------------------------
        # Summary
        # -------------------------------------------------

        summary = pd.DataFrame(rows)

        summary_path = (
            OUTPUT_DIR
            / "nvda_18_loser_summary.csv"
        )

        summary.to_csv(
            summary_path,
            index=False,
        )

        # -------------------------------------------------
        # Human-readable loss report.
        # -------------------------------------------------

        report_lines = []

        report_lines.append(
            "AIMn KISS — EXPERIMENT #48"
        )

        report_lines.append(
            "NVDA 18-LOSER CHART BOOK"
        )

        report_lines.append(
            ""
        )

        report_lines.append(
            f"Total trades discovered: {len(trades)}"
        )

        report_lines.append(
            f"Winners: {(trades['pnl_pct'] > 0).sum()}"
        )

        report_lines.append(
            f"Losers: {(trades['pnl_pct'] < 0).sum()}"
        )

        report_lines.append(
            ""
        )

        if len(summary):

            finite_mfe = summary[
                np.isfinite(
                    summary["mfe_pct"]
                )
            ]

            finite_mae = summary[
                np.isfinite(
                    summary["mae_pct"]
                )
            ]

            report_lines.append(
                f"Average final loss: "
                f"{summary['final_pnl_pct'].mean():+.4f}%"
            )

            report_lines.append(
                f"Median final loss: "
                f"{summary['final_pnl_pct'].median():+.4f}%"
            )

            if len(finite_mfe):

                report_lines.append(
                    f"Average MFE: "
                    f"{finite_mfe['mfe_pct'].mean():+.4f}%"
                )

            if len(finite_mae):

                report_lines.append(
                    f"Average MAE: "
                    f"{finite_mae['mae_pct'].mean():+.4f}%"
                )

            report_lines.append(
                f"Ever profitable: "
                f"{int(summary['ever_profitable'].sum())}"
                f"/{len(summary)}"
            )

            report_lines.append(
                ""
            )

            report_lines.append(
                "LOSER-BY-LOSER"
            )

            report_lines.append(
                "-" * 90
            )

            for _, row in summary.iterrows():

                report_lines.append(
                    f"{row['trade_id']:12s} "
                    f"{str(row['direction']):5s} "
                    f"FINAL={row['final_pnl_pct']:+.3f}% "
                    f"MFE={row['mfe_pct']:+.3f}% "
                    f"MAE={row['mae_pct']:+.3f}% "
                    f"EVER_PROFIT="
                    f"{bool(row['ever_profitable'])}"
                )

        report_path = (
            OUTPUT_DIR
            / "exp48_loss_report.txt"
        )

        report_path.write_text(
            "\n".join(report_lines),
            encoding="utf-8",
        )

        # -------------------------------------------------
        # Final output.
        # -------------------------------------------------

        print()
        print("=" * 110)
        print("EXPERIMENT #48 COMPLETE")
        print("=" * 110)

        print()
        print(
            f"Trades discovered : {len(trades)}"
        )

        print(
            f"Losers processed   : {len(losers)}"
        )

        print(
            f"Charts created     : {chart_count}"
        )

        print()
        print("OUTPUTS")
        print("-" * 110)

        print(
            f"Chart directory:"
        )

        print(
            f"  {OUTPUT_DIR}"
        )

        print()
        print(
            f"Summary:"
        )

        print(
            f"  {summary_path}"
        )

        print()
        print(
            f"Report:"
        )

        print(
            f"  {report_path}"
        )

        print()
        print(
            "IMPORTANT:"
        )

        print(
            "This experiment does not choose an exit rule."
        )

        print(
            "It shows where the 18 losing trades actually moved "
            "between ENTRY and EXIT."
        )

        print()

        # A very useful final diagnostic:
        # how many losers were ever green?
        if len(summary):

            ever_green = int(
                summary[
                    "ever_profitable"
                ].sum()
            )

            never_green = (
                len(summary)
                - ever_green
            )

            print(
                f"Losers that were EVER profitable: "
                f"{ever_green}"
            )

            print(
                f"Losers that NEVER became profitable: "
                f"{never_green}"
            )

            if never_green:

                print()
                print(
                    "The NEVER-PROFITABLE losers are especially important "
                    "for our STAY-vs-EXIT problem."
                )


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print(
            "Interrupted."
        )

        sys.exit(130)

    except Exception as exc:

        print()
        print("=" * 110)
        print("ERROR")
        print("=" * 110)

        print(
            str(exc)
        )

        print()
        traceback.print_exc()

        sys.exit(1)
