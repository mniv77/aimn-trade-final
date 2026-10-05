#!/usr/bin/env python3

import re
import sys
import shutil
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path.cwd()
SOURCE = ROOT / "kiss" / "kiss_trailing_entry_exit_backtest.py"
RESULTS = ROOT / "kiss" / "results"
EXP_DIR = RESULTS / "exp30_nvda_transition_match"

ENTRY_LEVELS = [
    ("025", 0.0025, "0.25%"),
    ("050", 0.0050, "0.50%"),
    ("075", 0.0075, "0.75%"),
    ("100", 0.0100, "1.00%"),
    ("125", 0.0125, "1.25%"),
    ("150", 0.0150, "1.50%"),
]

EXIT_TRAIL = 0.0150


def die(message):
    print()
    print("=" * 100)
    print("ERROR")
    print("=" * 100)
    print(message)
    print()
    sys.exit(1)


def find_trail_lines(text):
    """
    Find lines containing entry/exit + trail + numeric assignment.

    This deliberately does NOT assume a particular variable name.
    """

    entry_candidates = []
    exit_candidates = []

    for line_no, line in enumerate(text.splitlines(), 1):

        low = line.lower()

        if "entry" in low and "trail" in low and "=" in line:
            if re.search(r"=\s*[0-9]+(?:\.[0-9]+)?", line):
                entry_candidates.append((line_no, line))

        if "exit" in low and "trail" in low and "=" in line:
            if re.search(r"=\s*[0-9]+(?:\.[0-9]+)?", line):
                exit_candidates.append((line_no, line))

    return entry_candidates, exit_candidates


def patch_numeric_assignment(line, new_value):
    """
    Replace the numeric value on an assignment line while preserving
    the variable name and surrounding code.
    """

    pattern = r"(=\s*)([-+]?[0-9]+(?:\.[0-9]+)?)(\s*(?:#.*)?$)"

    replacement = rf"\g<1>{new_value}\g<3>"

    patched, count = re.subn(
        pattern,
        replacement,
        line,
        count=1,
    )

    if count != 1:
        raise RuntimeError(
            f"Could not replace numeric assignment:\n{line}"
        )

    return patched


def make_temp_source(level_code, entry_value):
    original = SOURCE.read_text(encoding="utf-8")

    entry_candidates, exit_candidates = find_trail_lines(original)

    if len(entry_candidates) != 1:
        print()
        print("ENTRY TRAIL CANDIDATES FOUND:")
        for n, line in entry_candidates:
            print(f"  {n}: {line}")

        die(
            "I could not safely identify exactly ONE entry-trail "
            "assignment in the existing backtest source."
        )

    if len(exit_candidates) != 1:
        print()
        print("EXIT TRAIL CANDIDATES FOUND:")
        for n, line in exit_candidates:
            print(f"  {n}: {line}")

        die(
            "I could not safely identify exactly ONE exit-trail "
            "assignment in the existing backtest source."
        )

    entry_line_no, entry_line = entry_candidates[0]
    exit_line_no, exit_line = exit_candidates[0]

    print(
        f"Detected entry trail source line {entry_line_no}: "
        f"{entry_line.strip()}"
    )
    print(
        f"Detected exit trail source line  {exit_line_no}: "
        f"{exit_line.strip()}"
    )

    lines = original.splitlines(keepends=True)

    newline_entry = "\n" if lines[entry_line_no - 1].endswith("\n") else ""

    newline_exit = "\n" if lines[exit_line_no - 1].endswith("\n") else ""

    lines[entry_line_no - 1] = (
        patch_numeric_assignment(
            lines[entry_line_no - 1].rstrip("\r\n"),
            entry_value,
        )
        + newline_entry
    )

    lines[exit_line_no - 1] = (
        patch_numeric_assignment(
            lines[exit_line_no - 1].rstrip("\r\n"),
            EXIT_TRAIL,
        )
        + newline_exit
    )

    modified = "".join(lines)

    temp = ROOT / "kiss" / f".exp30_backtest_{level_code}.py"

    temp.write_text(modified, encoding="utf-8")

    return temp


def run_one(level_code, entry_value, label):
    print()
    print("=" * 100)
    print(f"RUNNING ENTRY TRAIL {label}   EXIT TRAIL 1.50%")
    print("=" * 100)

    temp = make_temp_source(level_code, entry_value)

    try:
        result = subprocess.run(
            [sys.executable, str(temp)],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
        )

        if result.stdout:
            print(result.stdout)

        if result.returncode != 0:
            if result.stderr:
                print()
                print("BACKTEST STDERR:")
                print(result.stderr)

            die(
                f"Backtest failed for entry trail {label}."
            )

        source_csv = RESULTS / "kiss_trailing_entry_exit_trades.csv"

        if not source_csv.exists():
            die(
                "The backtest finished but did not create:\n"
                f"{source_csv}"
            )

        destination = (
            EXP_DIR /
            f"nvda_trades_entry_{level_code}.csv"
        )

        shutil.copy2(
            source_csv,
            destination,
        )

        print(f"SAVED: {destination}")

    finally:
        if temp.exists():
            temp.unlink()


def load_nvda(level_code, label):
    path = (
        EXP_DIR /
        f"nvda_trades_entry_{level_code}.csv"
    )

    df = pd.read_csv(path)

    if "symbol" not in df.columns:
        die(
            f"'symbol' column missing from {path}"
        )

    df = df[
        df["symbol"].astype(str).str.upper() == "NVDA"
    ].copy()

    if df.empty:
        return df

    required = [
        "symbol",
        "direction",
        "transition_time_utc",
        "transition_from",
        "transition_to",
        "entry_price",
        "exit_price",
        "pnl_pct",
        "max_favorable_pct",
        "max_adverse_pct",
        "exit_reason",
        "entry_wait_minutes",
        "trade_minutes",
    ]

    missing = [
        x for x in required
        if x not in df.columns
    ]

    if missing:
        die(
            f"Missing columns in {path}: {missing}"
        )

    df["MATCH_KEY"] = (
        df["symbol"].astype(str)
        + "|"
        + df["transition_time_utc"].astype(str)
        + "|"
        + df["direction"].astype(str)
        + "|"
        + df["transition_from"].astype(str)
        + "|"
        + df["transition_to"].astype(str)
    )

    duplicates = df["MATCH_KEY"].duplicated().sum()

    if duplicates:
        print(
            f"WARNING: {label}: {duplicates} duplicate "
            "transition keys. Keeping first."
        )

        df = df.drop_duplicates(
            "MATCH_KEY",
            keep="first",
        )

    df["ENTRY_LEVEL"] = label

    return df


def main():

    if not SOURCE.exists():
        die(
            f"Backtest source not found:\n{SOURCE}"
        )

    RESULTS.mkdir(
        parents=True,
        exist_ok=True,
    )

    if EXP_DIR.exists():
        for item in EXP_DIR.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    else:
        EXP_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

    print()
    print("=" * 100)
    print("EXPERIMENT #30")
    print("NVDA TRANSITION MATCHING ACROSS ENTRY TRAILS")
    print("=" * 100)
    print()
    print(f"SOURCE: {SOURCE}")
    print()
    print("ENTRY TRAILS:")
    for _, _, label in ENTRY_LEVELS:
        print(f"  {label}")
    print()
    print("EXIT TRAIL: 1.50%")
    print()
    print("MATCH KEY:")
    print("  symbol")
    print("  transition_time_utc")
    print("  direction")
    print("  transition_from")
    print("  transition_to")
    print()
    print("ORIGINAL SOURCE WILL NOT BE MODIFIED.")
    print()

    datasets = []

    for level_code, entry_value, label in ENTRY_LEVELS:

        run_one(
            level_code,
            entry_value,
            label,
        )

        df = load_nvda(
            level_code,
            label,
        )

        datasets.append(
            (
                level_code,
                label,
                df,
            )
        )

    # ------------------------------------------------------------
    # MASTER TRANSITION SET
    # ------------------------------------------------------------

    all_keys = set()

    for _, _, df in datasets:
        if not df.empty:
            all_keys.update(
                df["MATCH_KEY"].tolist()
            )

    if not all_keys:
        die(
            "No NVDA trades found in any experiment."
        )

    def sort_key(key):
        parts = key.split("|")
        return parts[1] if len(parts) > 1 else key

    master = pd.DataFrame(
        {
            "MATCH_KEY": sorted(
                all_keys,
                key=sort_key,
            )
        }
    )

    merged = master.copy()

    fields = [
        "direction",
        "transition_time_utc",
        "transition_from",
        "transition_to",
        "entry_price",
        "exit_price",
        "pnl_pct",
        "max_favorable_pct",
        "max_adverse_pct",
        "exit_reason",
        "entry_wait_minutes",
        "trade_minutes",
    ]

    for level_code, label, df in datasets:

        if df.empty:
            continue

        keep = [
            "MATCH_KEY"
        ] + fields

        temp = df[keep].copy()

        temp = temp.rename(
            columns={
                c: f"{c}_{level_code}"
                for c in fields
            }
        )

        merged = merged.merge(
            temp,
            on="MATCH_KEY",
            how="left",
        )

    # ------------------------------------------------------------
    # PRESENCE / STATUS
    # ------------------------------------------------------------

    def present(row, code):
        value = row.get(
            f"pnl_pct_{code}"
        )
        return pd.notna(value)

    def status_for(row):

        states = [
            present(row, code)
            for code, _, _ in ENTRY_LEVELS
        ]

        count = sum(states)

        if count == len(states):
            return "PRESENT_ALL_LEVELS"

        if count == 0:
            return "ABSENT_ALL_LEVELS"

        removed = any(
            states[i] and not states[i + 1]
            for i in range(len(states) - 1)
        )

        reappears = any(
            not states[i] and states[i + 1]
            for i in range(len(states) - 1)
        )

        if removed and reappears:
            return "REMOVED_AND_REAPPEARS"

        if removed:
            return "REMOVED_BY_LARGER_TRAIL"

        if reappears:
            return "APPEARS_AT_LARGER_TRAIL"

        return "SEQUENCE_CHANGE"

    merged["STATUS"] = merged.apply(
        status_for,
        axis=1,
    )

    def trail_presence(row):

        parts = []

        for code, _, label in ENTRY_LEVELS:

            if present(row, code):
                parts.append(label)
            else:
                parts.append("--")

        return " | ".join(parts)

    merged["TRAIL_PRESENCE"] = merged.apply(
        trail_presence,
        axis=1,
    )

    # ------------------------------------------------------------
    # SAVE COMPLETE MASTER TABLE
    # ------------------------------------------------------------

    full_csv = (
        EXP_DIR /
        "nvda_transition_match_full.csv"
    )

    merged.to_csv(
        full_csv,
        index=False,
    )

    # ------------------------------------------------------------
    # PERFORMANCE SUMMARY
    # ------------------------------------------------------------

    print()
    print()
    print("=" * 120)
    print("NVDA PERFORMANCE BY ENTRY TRAIL")
    print("=" * 120)

    rows = []

    for code, label, df in datasets:

        if df.empty:
            rows.append(
                [
                    label,
                    0,
                    0,
                    0.0,
                    0.0,
                    0.0,
                ]
            )
            continue

        pnl = pd.to_numeric(
            df["pnl_pct"],
            errors="coerce",
        ).dropna()

        winners = int(
            (pnl > 0).sum()
        )

        rows.append(
            [
                label,
                len(pnl),
                winners,
                round(
                    winners / len(pnl) * 100,
                    2,
                ),
                round(
                    pnl.sum(),
                    4,
                ),
                round(
                    pnl.mean(),
                    4,
                ),
            ]
        )

    perf = pd.DataFrame(
        rows,
        columns=[
            "ENTRY_TRAIL",
            "TRADES",
            "WINNERS",
            "WIN_RATE_%",
            "TOTAL_PNL_%",
            "AVG_PNL_%",
        ],
    )

    print(
        perf.to_string(
            index=False
        )
    )

    # ------------------------------------------------------------
    # REMOVED TRADES
    # ------------------------------------------------------------

    print()
    print()
    print("=" * 120)
    print("TRADES REMOVED BY A LARGER ENTRY TRAIL")
    print("=" * 120)

    removed = []

    for _, row in merged.iterrows():

        states = [
            present(row, code)
            for code, _, _ in ENTRY_LEVELS
        ]

        removal_points = []

        for i in range(
            len(states) - 1
        ):

            if (
                states[i]
                and not states[i + 1]
            ):
                removal_points.append(
                    ENTRY_LEVELS[i + 1][2]
                )

        if not removal_points:
            continue

        first_present = None

        for i, state in enumerate(states):

            if state:
                first_present = (
                    ENTRY_LEVELS[i]
                )
                break

        if first_present is None:
            continue

        first_code = first_present[0]
        first_label = first_present[2]

        removed.append(
            [
                row["MATCH_KEY"],
                first_label,
                ", ".join(removal_points),
                row.get(
                    f"pnl_pct_{first_code}"
                ),
                row.get(
                    f"max_favorable_pct_{first_code}"
                ),
                row.get(
                    f"max_adverse_pct_{first_code}"
                ),
                row.get(
                    f"entry_wait_minutes_{first_code}"
                ),
                row.get(
                    f"exit_reason_{first_code}"
                ),
                row["TRAIL_PRESENCE"],
            ]
        )

    removed_df = pd.DataFrame(
        removed,
        columns=[
            "MATCH_KEY",
            "LAST_PRESENT_TRAIL",
            "REMOVED_AT",
            "P&L_%",
            "MFE_%",
            "MAE_%",
            "WAIT_MIN",
            "EXIT_REASON",
            "TRAIL_PRESENCE",
        ],
    )

    if removed_df.empty:

        print(
            "No transitions were removed "
            "as entry trail increased."
        )

    else:

        removed_df = removed_df.sort_values(
            "P&L_%",
            na_position="last",
        )

        print(
            removed_df.to_string(
                index=False,
                max_colwidth=35,
            )
        )

        pnl = pd.to_numeric(
            removed_df["P&L_%"],
            errors="coerce",
        ).dropna()

        winners = pnl[pnl > 0]
        losers = pnl[pnl <= 0]

        print()
        print("-" * 100)
        print("REMOVED TRADE P&L")
        print("-" * 100)
        print(
            f"Removed trades:       {len(pnl)}"
        )
        print(
            f"Removed winners:      {len(winners)}"
        )
        print(
            f"Removed losers:       {len(losers)}"
        )
        print(
            f"Removed winners P&L:  {winners.sum():+.4f}%"
        )
        print(
            f"Removed losers P&L:   {losers.sum():+.4f}%"
        )
        print(
            f"Removed total P&L:    {pnl.sum():+.4f}%"
        )

        removed_df.to_csv(
            EXP_DIR /
            "nvda_removed_transitions.csv",
            index=False,
        )

    # ------------------------------------------------------------
    # SPECIAL 0.50 -> 0.75
    # ------------------------------------------------------------

    print()
    print()
    print("=" * 120)
    print("SPECIAL CHECK: 0.50% -> 0.75%")
    print("=" * 120)

    special = merged[
        merged["pnl_pct_050"].notna()
        &
        merged["pnl_pct_075"].isna()
    ].copy()

    if special.empty:

        print(
            "No transitions disappeared specifically "
            "between 0.50% and 0.75%."
        )

    else:

        special_rows = []

        for _, row in special.iterrows():

            special_rows.append(
                [
                    row["MATCH_KEY"],
                    row["pnl_pct_050"],
                    row["max_favorable_pct_050"],
                    row["max_adverse_pct_050"],
                    row["entry_wait_minutes_050"],
                    row["exit_reason_050"],
                    row["TRAIL_PRESENCE"],
                ]
            )

        special_df = pd.DataFrame(
            special_rows,
            columns=[
                "MATCH_KEY",
                "P&L_0.50%",
                "MFE_0.50%",
                "MAE_0.50%",
                "WAIT_MIN",
                "EXIT_REASON",
                "TRAIL_PRESENCE",
            ],
        )

        print(
            special_df.to_string(
                index=False,
                max_colwidth=45,
            )
        )

        pnl = pd.to_numeric(
            special_df["P&L_0.50%"],
            errors="coerce",
        ).dropna()

        print()
        print(
            f"Transitions removed: {len(pnl)}"
        )
        print(
            f"Removed winners:     {(pnl > 0).sum()}"
        )
        print(
            f"Removed losers:      {(pnl <= 0).sum()}"
        )
        print(
            f"Removed winners P&L: "
            f"{pnl[pnl > 0].sum():+.4f}%"
        )
        print(
            f"Removed losers P&L:  "
            f"{pnl[pnl <= 0].sum():+.4f}%"
        )
        print(
            f"Removed total P&L:   "
            f"{pnl.sum():+.4f}%"
        )

        special_df.to_csv(
            EXP_DIR /
            "nvda_removed_050_to_075.csv",
            index=False,
        )

    # ------------------------------------------------------------
    # FULL COMPACT COMPARISON
    # ------------------------------------------------------------

    print()
    print()
    print("=" * 140)
    print("FULL NVDA TRANSITION-BY-TRANSITION COMPARISON")
    print("=" * 140)

    compact = []

    for _, row in merged.iterrows():

        key_parts = row[
            "MATCH_KEY"
        ].split("|")

        transition_time = key_parts[1]
        direction = key_parts[2]
        transition = (
            key_parts[3]
            + "->"
            + key_parts[4]
        )

        result = [
            transition_time,
            direction,
            transition,
            row["STATUS"],
        ]

        for code, _, label in ENTRY_LEVELS:

            pnl = row.get(
                f"pnl_pct_{code}"
            )

            mfe = row.get(
                f"max_favorable_pct_{code}"
            )

            mae = row.get(
                f"max_adverse_pct_{code}"
            )

            if pd.isna(pnl):

                result.extend(
                    [
                        "--",
                        "--",
                        "--",
                    ]
                )

            else:

                result.extend(
                    [
                        f"{float(pnl):+.3f}",
                        f"{float(mfe):+.3f}",
                        f"{float(mae):+.3f}",
                    ]
                )

        compact.append(result)

    columns = [
        "TransitionUTC",
        "Dir",
        "State",
        "Status",
    ]

    for _, _, label in ENTRY_LEVELS:

        short = label.replace(
            "%",
            "",
        )

        columns.extend(
            [
                f"{short}_PnL",
                f"{short}_MFE",
                f"{short}_MAE",
            ]
        )

    compact_df = pd.DataFrame(
        compact,
        columns=columns,
    )

    print(
        compact_df.to_string(
            index=False,
            max_rows=None,
        )
    )

    compact_df.to_csv(
        EXP_DIR /
        "nvda_transition_comparison_compact.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # FINAL
    # ------------------------------------------------------------

    print()
    print()
    print("=" * 120)
    print("EXPERIMENT #30 COMPLETE")
    print("=" * 120)
    print()
    print(
        f"Complete comparison:\n"
        f"  {full_csv}"
    )
    print()
    print(
        "Compact comparison:\n"
        f"  {EXP_DIR / 'nvda_transition_comparison_compact.csv'}"
    )
    print()
    print(
        "Removed-transition analysis:\n"
        f"  {EXP_DIR / 'nvda_removed_transitions.csv'}"
    )
    print()
    print(
        "0.50% -> 0.75% analysis:\n"
        f"  {EXP_DIR / 'nvda_removed_050_to_075.csv'}"
    )
    print()
    print("ORIGINAL BACKTEST SOURCE WAS NOT MODIFIED.")
    print("RESEARCH ONLY.")
    print()


if __name__ == "__main__":
    main()
