import pandas as pd
from pathlib import Path

f = (
    Path.home()
    / "aimn-trade-final"
    / "kiss"
    / "results"
    / "exp42_v_peak_divergence"
    / "nvda_v_peak_divergence_transitions.csv"
)

print("=" * 100)
print("CHECK ACTUAL EXPERIMENT #42 FILE")
print("=" * 100)

print("\nFILE:")
print(f)

df = pd.read_csv(f)

print("\nSHAPE:")
print(df.shape)

print("\nCOLUMNS 87-88:")
for i, c in enumerate(df.columns, 1):
    if i >= 80:
        print(f"{i:3d}: {repr(c)}")

print("\n" + "=" * 100)
print("pnl_peak_relationship — EXACT VALUES")
print("=" * 100)

if "pnl_peak_relationship" not in df.columns:
    print("ERROR: pnl_peak_relationship DOES NOT EXIST")
else:
    s = df["pnl_peak_relationship"]

    print("\nColumn name repr:")
    print(repr(s.name))

    print("\nValue counts:")
    print(s.value_counts(dropna=False).to_string())

    print("\nExact Python repr of every unique value:")
    for value in s.drop_duplicates().tolist():
        print(repr(value))

    print("\nRows where value contains PEAK:")
    mask = s.astype(str).str.contains(
        "PEAK",
        case=False,
        na=False
    )

    print(f"Count: {int(mask.sum())}")

    if mask.any():
        print(
            df.loc[
                mask,
                [
                    "case_id",
                    "trade_id",
                    "event_time_utc",
                    "v_number",
                    "pnl_peak_relationship",
                    "relationship_type",
                    "pnl_at_v_pct",
                    "prior_peak_change_from_previous_v_pct",
                    "pnl_change_from_previous_v_pct",
                    "eventual_pnl_hindsight_pct",
                ]
            ].to_string(index=False)
        )

print("\n" + "=" * 100)
print("relationship_type — EXACT VALUES")
print("=" * 100)

if "relationship_type" in df.columns:
    print(
        df["relationship_type"]
        .value_counts(dropna=False)
        .to_string()
    )

print("\n" + "=" * 100)
print("DIRECT TEST")
print("=" * 100)

if "pnl_peak_relationship" in df.columns:

    exact_count = int(
        (
            df["pnl_peak_relationship"]
            == "PEAK_FLAT"
        ).sum()
    )

    stripped_count = int(
        (
            df["pnl_peak_relationship"]
            .astype(str)
            .str.strip()
            == "PEAK_FLAT"
        ).sum()
    )

    contains_count = int(
        df["pnl_peak_relationship"]
        .astype(str)
        .str.contains(
            "PEAK_FLAT",
            case=False,
            na=False
        )
        .sum()
    )

    print(
        "Exact == 'PEAK_FLAT':",
        exact_count
    )

    print(
        "strip() == 'PEAK_FLAT':",
        stripped_count
    )

    print(
        "contains 'PEAK_FLAT':",
        contains_count
    )

print("\n" + "=" * 100)
print("END CHECK")
print("=" * 100)
