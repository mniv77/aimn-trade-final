import pandas as pd

BASE = "kiss/results/exp37_nvda_causal/"

summary = pd.read_csv(BASE + "nvda_causal_summary.csv")
context = pd.read_csv(BASE + "nvda_short_trend_context.csv")

df = context.merge(
    summary[["case_id", "eventual_trade_winner_hindsight"]],
    on="case_id",
    how="left"
)

cols = ["trend_30m_pct", "trend_60m_pct", "trend_120m_pct"]

for col in cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df["outcome"] = df["eventual_trade_winner_hindsight"].map(
    {True: "WINNER", False: "LOSER"}
).fillna("UNKNOWN")

df["pattern"] = "OTHER MIXED"

df.loc[(df[cols] < 0).all(axis=1), "pattern"] = (
    "ALL THREE NEGATIVE"
)

df.loc[
    (df["trend_30m_pct"] > 0)
    & (df["trend_60m_pct"] < 0)
    & (df["trend_120m_pct"] < 0),
    "pattern"
] = "30M UP, LONGER DOWN"

df.loc[
    (df["trend_30m_pct"] < 0)
    & (df["trend_120m_pct"] > 0),
    "pattern"
] = "30M DOWN, 120M UP"

df.loc[(df[cols] > 0).all(axis=1), "pattern"] = (
    "ALL THREE POSITIVE"
)

print("=== NVDA SHORT PATTERN COUNTS ===")
print(pd.crosstab(
    df["pattern"], df["outcome"], margins=True
).to_string())

print()
print("=== CASE DETAILS ===")
print(
    df[["case_id"] + cols + ["pattern", "outcome"]]
    .to_string(index=False)
)