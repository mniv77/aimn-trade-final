#!/usr/bin/env python3
"""
AIMn KISS - Experiment #33: Raw V Geometry vs Trailing Entry Outcome

RESEARCH ONLY.

Purpose:
Connect the independent raw 5m V geometry from Experiment #32 to the
actual trailing-entry outcomes from Experiment #30 for the SAME transitions.

This asks:
1. What raw V shapes tend to produce an entry at each trail level?
2. Which raw shapes are filtered out as the entry trail increases?
3. Among trades that are filtered out, how many were winners vs losers?
4. Are depth, recovery speed, recovery time, dwell, and post-recovery
   behavior more informative than V depth alone?

Entry trails:
    0.25%, 0.50%, 0.75%, 1.00%, 1.25%, 1.50%

Exit trail:
    1.50% (from Experiment #30)

Matching key:
    symbol + transition_time_utc + direction

No production code is modified.
No live orders are placed.
No trading rule or threshold is promoted.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Dict, List

import pandas as pd


ROOT = Path.cwd()
EXP32_DIR = ROOT / "kiss" / "results" / "exp32_raw_candle_v_geometry"
EXP30_DIR = ROOT / "kiss" / "results" / "exp30_nvda_transition_match"

TRAILS = [
    ("025", 0.25),
    ("050", 0.50),
    ("075", 0.75),
    ("100", 1.00),
    ("125", 1.25),
    ("150", 1.50),
]


def norm_time(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce").astype("string")


def norm_key(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    required = ["symbol", "transition_time_utc", "direction"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f"Missing matching columns: {missing}")

    out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    out["direction"] = out["direction"].astype(str).str.upper().str.strip()
    out["transition_time_utc"] = norm_time(out["transition_time_utc"])
    out["MATCH_KEY"] = (
        out["symbol"]
        + "|"
        + out["transition_time_utc"]
        + "|"
        + out["direction"]
    )
    return out


def find_col(df: pd.DataFrame, candidates: List[str]) -> str | None:
    lower = {str(c).lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]

    for c in df.columns:
        lc = str(c).lower()
        if any(candidate.lower() in lc for candidate in candidates):
            return c

    return None


def load_trades(code: str) -> pd.DataFrame:
    path = EXP30_DIR / f"nvda_trades_entry_{code}.csv"

    if not path.exists():
        raise FileNotFoundError(
            f"Missing Experiment #30 file: {path}\n"
            "Run Experiment #30 first so all six trail CSVs exist."
        )

    df = pd.read_csv(path)

    # Experiment #30 originally saved NVDA-only trade files.  Experiment
    # #33 is therefore intentionally written to handle those files first.
    # If a future Experiment #30 file contains multiple symbols, the same
    # normalization still works.
    df = norm_key(df)

    pnl_col = find_col(df, ["P&L_%", "P&L", "pnl_pct", "pnl"])
    mfe_col = find_col(df, ["MFE_%", "MFE", "mfe_pct"])
    mae_col = find_col(df, ["MAE_%", "MAE", "mae_pct"])
    wait_col = find_col(df, ["WAIT_MIN", "wait_min", "time_to_entry_min"])
    reason_col = find_col(df, ["EXIT_REASON", "exit_reason"])

    rename = {}
    if pnl_col:
        rename[pnl_col] = f"TRAIL_{code}_PNL_PCT"
    if mfe_col:
        rename[mfe_col] = f"TRAIL_{code}_MFE_PCT"
    if mae_col:
        rename[mae_col] = f"TRAIL_{code}_MAE_PCT"
    if wait_col:
        rename[wait_col] = f"TRAIL_{code}_WAIT_MIN"
    if reason_col:
        rename[reason_col] = f"TRAIL_{code}_EXIT_REASON"

    df = df.rename(columns=rename)

    keep = ["MATCH_KEY", "symbol", "transition_time_utc", "direction"]
    keep += [c for c in rename.values() if c in df.columns]

    out = df[keep].copy()

    pnl = f"TRAIL_{code}_PNL_PCT"
    if pnl in out.columns:
        out[pnl] = pd.to_numeric(out[pnl], errors="coerce")
        out[f"TRAIL_{code}_OUTCOME"] = out[pnl].apply(
            lambda x: "WIN" if x > 0 else ("LOSS" if x < 0 else "FLAT")
            if pd.notna(x)
            else "NO_PNL"
        )

    out[f"TRAIL_{code}_PRESENT"] = True

    # A transition should appear at most once in one Experiment #30 file.
    out = out.drop_duplicates("MATCH_KEY", keep="first")

    return out


def load_raw_geometry() -> pd.DataFrame:
    path = EXP32_DIR / "raw_v_geometry.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing Experiment #32 output: {path}")

    df = pd.read_csv(path)
    df = norm_key(df)

    numeric = [
        "v_depth_pct",
        "time_to_extreme_min",
        "recovery_from_extreme_pct",
        "recovery_time_from_extreme_min",
        "recovery_speed_pct_per_min",
        "near_extreme_dwell_min",
        "max_post_recovery_favorable_pct",
        "max_favorable_from_transition_pct",
        "max_adverse_from_transition_pct",
        "candles_measured",
    ]

    for c in numeric:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    for c in ["reached_recovery", "reached_favorable"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.lower().map(
                {"true": True, "false": False}
            )

    df = df.drop_duplicates("MATCH_KEY", keep="first")
    return df


def classify_filtered(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    presence_cols = [f"TRAIL_{code}_PRESENT" for code, _ in TRAILS]

    out["TRAIL_COUNT_PRESENT"] = out[presence_cols].fillna(False).sum(axis=1)

    def first_present(row):
        for code, pct in TRAILS:
            if bool(row.get(f"TRAIL_{code}_PRESENT", False)):
                return pct
        return math.nan

    def last_present(row):
        found = math.nan
        for code, pct in TRAILS:
            if bool(row.get(f"TRAIL_{code}_PRESENT", False)):
                found = pct
        return found

    out["FIRST_ENTRY_TRAIL_PCT"] = out.apply(first_present, axis=1)
    out["LAST_ENTRY_TRAIL_PCT"] = out.apply(last_present, axis=1)

    return out


def summarize_level(df: pd.DataFrame, code: str, pct: float) -> Dict:
    present = df[df[f"TRAIL_{code}_PRESENT"] == True].copy()
    pnl_col = f"TRAIL_{code}_PNL_PCT"

    return {
        "trail_pct": pct,
        "transitions_with_entry": int(len(present)),
        "wins": int((present[pnl_col] > 0).sum()) if pnl_col in present else 0,
        "losses": int((present[pnl_col] < 0).sum()) if pnl_col in present else 0,
        "flats": int((present[pnl_col] == 0).sum()) if pnl_col in present.columns else 0,
        "avg_pnl_pct": (
            round(float(present[pnl_col].mean()), 6)
            if pnl_col in present and present[pnl_col].notna().any()
            else None
        ),
        "avg_v_depth_pct": round(float(present["v_depth_pct"].mean()), 6),
        "avg_recovery_speed_pct_per_min": (
            round(float(present["recovery_speed_pct_per_min"].mean()), 6)
            if "recovery_speed_pct_per_min" in present
            and present["recovery_speed_pct_per_min"].notna().any()
            else None
        ),
        "recovered": (
            int(present["reached_recovery"].sum())
            if "reached_recovery" in present
            else None
        ),
        "favorable_reached": (
            int(present["reached_favorable"].sum())
            if "reached_favorable" in present
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AIMn KISS Experiment #33"
    )
    parser.add_argument(
        "--output-dir",
        default="kiss/results/exp33_raw_v_vs_entry_outcome",
    )
    args = parser.parse_args()

    out_dir = ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 100)
    print("EXPERIMENT #33")
    print("RAW V GEOMETRY VS TRAILING ENTRY OUTCOME")
    print("=" * 100)
    print("RESEARCH ONLY")
    print()
    print("Entry trails: 0.25%, 0.50%, 0.75%, 1.00%, 1.25%, 1.50%")
    print("Exit trail : 1.50%")
    print()

    raw = load_raw_geometry()
    print(f"Experiment #32 raw transitions: {len(raw)}")

    merged = raw.copy()

    for code, pct in TRAILS:
        trades = load_trades(code)
        print(
            f"[LOAD] {code} ({pct:.2f}%): "
            f"{len(trades)} transition/trade rows"
        )

        cols = [
            c for c in trades.columns
            if c == "MATCH_KEY" or c.startswith("TRAIL_")
        ]
        merged = merged.merge(
            trades[cols],
            on="MATCH_KEY",
            how="left",
            suffixes=("", f"_{code}"),
        )

        present = merged[f"TRAIL_{code}_PRESENT"].fillna(False)
        merged[f"TRAIL_{code}_PRESENT"] = present.astype(bool)

    merged = classify_filtered(merged)

    # A transition is "filtered at X" when it is present at the immediately
    # smaller trail but absent at X.  This isolates the shape of the moves
    # being removed as the trail becomes stricter.
    filtered_rows = []

    for i in range(1, len(TRAILS)):
        prev_code, prev_pct = TRAILS[i - 1]
        code, pct = TRAILS[i]

        prev_present = merged[f"TRAIL_{prev_code}_PRESENT"].fillna(False)
        present = merged[f"TRAIL_{code}_PRESENT"].fillna(False)

        mask = prev_present & ~present
        subset = merged.loc[mask].copy()

        if subset.empty:
            continue

        subset["FILTERED_FROM_TRAIL_PCT"] = prev_pct
        subset["FILTERED_AT_TRAIL_PCT"] = pct
        subset["FILTERED_PREV_PNL_PCT"] = subset[
            f"TRAIL_{prev_code}_PNL_PCT"
        ]
        subset["FILTERED_PREV_OUTCOME"] = subset[
            f"TRAIL_{prev_code}_OUTCOME"
        ]

        filtered_rows.append(subset)

    filtered = (
        pd.concat(filtered_rows, ignore_index=True)
        if filtered_rows
        else pd.DataFrame()
    )

    # Exact transition table: one row per raw transition, all trail outcomes
    # side-by-side.
    comparison_path = out_dir / "raw_v_entry_trail_comparison.csv"
    merged.to_csv(comparison_path, index=False)

    if not filtered.empty:
        filtered_path = out_dir / "raw_v_filtered_by_trail.csv"
        filtered.to_csv(filtered_path, index=False)
    else:
        filtered_path = out_dir / "raw_v_filtered_by_trail.csv"
        filtered.to_csv(filtered_path, index=False)

    level_summary = [
        summarize_level(merged, code, pct)
        for code, pct in TRAILS
    ]

    filter_summary = []
    if not filtered.empty:
        for from_pct, at_pct in zip(
            [x[1] for x in TRAILS[:-1]],
            [x[1] for x in TRAILS[1:]],
        ):
            x = filtered[
                (filtered["FILTERED_FROM_TRAIL_PCT"] == from_pct)
                & (filtered["FILTERED_AT_TRAIL_PCT"] == at_pct)
            ]

            pnl = x["FILTERED_PREV_PNL_PCT"]

            filter_summary.append(
                {
                    "from_trail_pct": from_pct,
                    "at_trail_pct": at_pct,
                    "transitions_filtered": int(len(x)),
                    "previous_winners": int((pnl > 0).sum()),
                    "previous_losers": int((pnl < 0).sum()),
                    "avg_previous_pnl_pct": (
                        round(float(pnl.mean()), 6)
                        if pnl.notna().any()
                        else None
                    ),
                    "avg_v_depth_pct": (
                        round(float(x["v_depth_pct"].mean()), 6)
                        if len(x)
                        else None
                    ),
                    "avg_recovery_speed_pct_per_min": (
                        round(
                            float(
                                x[
                                    "recovery_speed_pct_per_min"
                                ].mean()
                            ),
                            6,
                        )
                        if x[
                            "recovery_speed_pct_per_min"
                        ].notna().any()
                        else None
                    ),
                    "recovered": (
                        int(x["reached_recovery"].sum())
                        if "reached_recovery" in x
                        else None
                    ),
                    "favorable_reached": (
                        int(x["reached_favorable"].sum())
                        if "reached_favorable" in x
                        else None
                    ),
                }
            )

    # Raw geometry buckets versus actual entry outcome.
    depth_bins = [-float("inf"), 0.25, 0.50, 1.00, 1.50, float("inf")]
    depth_labels = [
        "<0.25%",
        "0.25-0.50%",
        "0.50-1.00%",
        "1.00-1.50%",
        ">=1.50%",
    ]
    merged["DEPTH_BUCKET"] = pd.cut(
        merged["v_depth_pct"],
        bins=depth_bins,
        labels=depth_labels,
        right=False,
    )

    bucket_rows = []
    for bucket in depth_labels:
        x = merged[merged["DEPTH_BUCKET"] == bucket]
        row = {"depth_bucket": bucket, "transitions": int(len(x))}

        for code, pct in TRAILS:
            present = x[x[f"TRAIL_{code}_PRESENT"] == True]
            pnl = present.get(f"TRAIL_{code}_PNL_PCT", pd.Series(dtype=float))

            row[f"trail_{pct:.2f}_present"] = int(len(present))
            row[f"trail_{pct:.2f}_wins"] = int((pnl > 0).sum())
            row[f"trail_{pct:.2f}_losses"] = int((pnl < 0).sum())
            row[f"trail_{pct:.2f}_avg_pnl"] = (
                round(float(pnl.mean()), 6)
                if pnl.notna().any()
                else None
            )

        bucket_rows.append(row)

    bucket_df = pd.DataFrame(bucket_rows)
    bucket_path = out_dir / "raw_v_depth_bucket_vs_entry_outcome.csv"
    bucket_df.to_csv(bucket_path, index=False)

    summary = {
        "research_only": True,
        "experiment": "#33 Raw V Geometry vs Trailing Entry Outcome",
        "method": (
            "Exact-transition join of Experiment #32 raw 5m V geometry "
            "with Experiment #30 trailing-entry outcomes."
        ),
        "entry_trails_pct": [x[1] for x in TRAILS],
        "exit_trail_pct": 1.50,
        "raw_transition_count": int(len(raw)),
        "level_summary": level_summary,
        "filtered_transition_summary": filter_summary,
        "outputs": {
            "comparison": str(comparison_path),
            "filtered": str(filtered_path),
            "depth_buckets": str(bucket_path),
        },
    }

    import json

    summary_path = out_dir / "raw_v_vs_entry_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, allow_nan=True)

    print()
    print("=" * 100)
    print("EXPERIMENT #33 COMPLETE")
    print("=" * 100)
    print()
    print("LEVEL SUMMARY")
    print(pd.DataFrame(level_summary).to_string(index=False))
    print()
    print("FILTERED TRANSITIONS")
    if filter_summary:
        print(pd.DataFrame(filter_summary).to_string(index=False))
    else:
        print("None")
    print()
    print(f"Comparison : {comparison_path}")
    print(f"Filtered   : {filtered_path}")
    print(f"Buckets    : {bucket_path}")
    print(f"Summary    : {summary_path}")


if __name__ == "__main__":
    main()
