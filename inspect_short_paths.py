import pandas as pd

p = "kiss/results/exp37_nvda_causal/nvda_causal_path.csv"
df = pd.read_csv(p)
df["direction"] = df["direction"].astype(str).str.upper()
shorts = df[df["direction"] == "SHORT"].copy()

print("SHORT path rows:", len(shorts))
print("Unique SHORT cases:", shorts["case_id"].nunique())
print("\nFIRST 15 SHORT CANDLE ROWS")

cols = [
    "case_id", "trade_id", "candle_utc",
    "minutes_after_known", "open", "high", "low", "close",
    "favorable_from_transition_pct",
    "adverse_from_transition_pct",
    "developing_adverse_depth_pct",
    "pullback_from_favorable_extreme_pct",
    "trade_started", "minutes_from_entry",
    "current_net_pnl_pct"
]
cols = [c for c in cols if c in shorts.columns]
print(shorts[cols].head(15).to_string(index=False))
