import pandas as pd

base = "kiss/results/exp37_nvda_causal/"
path = pd.read_csv(base + "nvda_causal_path.csv")
summary = pd.read_csv(base + "nvda_causal_summary.csv")

path["direction"] = path["direction"].astype(str).str.upper()
summary["direction"] = summary["direction"].astype(str).str.upper()

summary["winner"] = (
    summary["eventual_trade_winner_hindsight"]
    .astype(str).str.strip().str.lower()
    .map({"true": True, "false": False})
)

labels = summary.loc[
    summary["direction"] == "SHORT", ["case_id", "winner"]
].drop_duplicates("case_id")

shorts = path[
    (path["direction"] == "SHORT") &
    (pd.to_numeric(path["minutes_after_known"], errors="coerce") <= 30)
].copy()

shorts = shorts.merge(labels, on="case_id", how="left")

features = [
    "favorable_from_transition_pct",
    "adverse_from_transition_pct",
    "developing_adverse_depth_pct",
    "pullback_from_favorable_extreme_pct"
]

print("=== SHORT PRICE PATH: FIRST 30 MINUTES ===")

for name, group in [
    ("LOSERS", shorts[shorts["winner"] == False]),
    ("WINNERS", shorts[shorts["winner"] == True])
]:
    print(f"\n{name}: {group['case_id'].nunique()} cases")
    for col in features:
        values = pd.to_numeric(group[col], errors="coerce").dropna()
        if len(values):
            print(
                f"{col}: median={values.median():.4f}%, "
                f"mean={values.mean():.4f}%, "
                f"rows={len(values)}"
            )
