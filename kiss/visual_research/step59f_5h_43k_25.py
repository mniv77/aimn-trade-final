
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# AIMn Step 59F-5H-43K-25
# Opening Reversal vs Exhausted Opening Decline
# Read-only V18 research experiment

LAB = Path("kiss/visual_research")
sys.path.insert(0, str(LAB.resolve()))
import step59f_5h43c_flat_long_replay as engine

PARAMS = dict(
    entry_cutoff="15:45",
    commission_pct=0.01,
    entry_slippage_pct=0.02,
    exit_slippage_pct=0.02,
    trailing_minus_pct=1.5,
    rsi_rescue_short=80.0,
    atr_exhaustion_filter=True,
    flat_long_filter=True,
)

DATASETS = {
    "RESEARCH": (
        LAB / "aimn_nvda_candles.json", 22, 6.764673
    ),
    "VALIDATION": (
        LAB / "nvda_sep_oct_2026_validation.json", 14, 2.219621
    ),
}

def dt(value):
    return datetime.fromisoformat(str(value))

def pct(a, b):
    return (a / b - 1) * 100

def load(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["candles"] if isinstance(data, dict) else data
    rows = sorted(rows, key=lambda r: dt(r["timestamp"]))
    assert len({dt(r["timestamp"]) for r in rows}) == len(rows)
    return rows

def classify(prior):
    if len(prior) < 3:
        return "INSUFFICIENT_5M", None

    closes = [float(r["close"]) for r in prior]
    moves = [
        pct(closes[i], closes[i - 1])
        for i in range(1, len(closes))
    ]

    streak = 0
    for change in reversed(moves):
        if change < 0:
            streak += 1
        else:
            break

    if streak == 1 and moves[-2] > 0:
        return "FRESH_DOWN_TURN", streak
    if streak >= 2:
        return "CONTINUED_DECLINE", streak
    if streak == 0:
        return "NOT_CURRENTLY_FALLING", streak
    return "UNCONFIRMED_DOWN", streak

def audit(name, records):
    print("\n" + "=" * 100)
    print(name)
    print("=" * 100)

    for key in ("shape", "open_move", "location", "joint"):
        print("\n" + key.upper())

        for value in sorted({r[key] for r in records}):
            group = [
                r for r in records if r[key] == value
            ]
            wins = sum(r["net"] > 0 for r in group)
            losses = sum(r["net"] < 0 for r in group)
            net = sum(r["net"] for r in group)

            print(
                f"{value:58s} "
                f"N={len(group):2d} "
                f"W={wins:2d} L={losses:2d} "
                f"NET={net:+.6f}%"
            )

    print("\nTRADE AUDIT")
    for r in records:
        print(
            f'{r["time"]} NET={r["net"]:+.6f}% '
            f'SHAPE={r["shape"]} '
            f'STREAK={r["streak"]} '
            f'PRIOR={r["count"]} '
            f'OPEN_TO_LAST={r["open_change"]:+.4f}% '
            f'FROM_HIGH={r["below_high"]:+.4f}% '
            f'ABOVE_LOW={r["above_low"]:+.4f}% '
            f'REBOUND={r["rebound"]:+.4f}% '
            f'LOCATION={r["location"]}'
        )

def main():
    print("AIMn — STEP 59F-5H-43K-25")
    print("OPENING REVERSAL VS EXHAUSTED OPENING DECLINE")
    print("READ-ONLY OBSERVATIONAL AUDIT")

    combined = []
    total = 0.0

    for name, (path, count, expected_net) in DATASETS.items():
        rows = load(path)
        result = engine.run(rows=rows, **PARAMS)

        assert result["trade_count"] == count
        assert abs(
            result["net_pnl_pct"] - expected_net
        ) < 0.000002

        by_time = {
            dt(r["timestamp"]): i
            for i, r in enumerate(rows)
        }
        records = []

        for trade in result["trades"]:
            entry = dt(trade["entry_time"])
            i = by_time[entry]
            day = entry.date()

            # Exclude the entry candle and all future candles.
            prior = [
                r for r in rows[:i]
                if dt(r["timestamp"]).date() == day
                and dt(r["timestamp"]) + timedelta(minutes=5)
                    <= entry
            ]

            first = next(
                (
                    r for r in prior
                    if dt(r["timestamp"]).hour == 9
                    and dt(r["timestamp"]).minute == 30
                ),
                None
            )

            if first is None:
                raise AssertionError(
                    f"Missing completed 09:30 opening candle: {entry}"
                )

            open_price = float(first["open"])
            last = float(prior[-1]["close"])
            high = max(float(r["high"]) for r in prior)
            low = min(float(r["low"]) for r in prior)

            assert high >= low > 0

            change = pct(last, open_price)
            below_high = pct(high, last)
            above_low = pct(last, low)
            rebound = pct(last, low)

            shape, streak = classify(prior)

            if change < 0:
                open_move = "OPEN_DOWN"
            elif change > 0:
                open_move = "OPEN_UP"
            else:
                open_move = "OPEN_FLAT"

            midpoint = (high + low) / 2

            if last < midpoint:
                location = "LOWER_HALF"
            elif last > midpoint:
                location = "UPPER_HALF"
            else:
                location = "MIDPOINT"

            execution = float(trade["entry_price"])
            entry_open = float(rows[i]["open"])

            assert abs(
                (1 - execution / entry_open) * 100
                - PARAMS["entry_slippage_pct"]
            ) < 0.0001

            records.append({
                "time": str(entry),
                "net": float(trade["net_pnl_pct"]),
                "shape": shape,
                "streak": streak,
                "count": len(prior),
                "open_change": change,
                "below_high": below_high,
                "above_low": above_low,
                "rebound": rebound,
                "open_move": open_move,
                "location": location,
                "joint": shape + " / " + location,
            })

        assert len(records) == count
        audit(name, records)
        combined.extend(records)
        total += result["net_pnl_pct"]

    assert len(combined) == 36
    assert abs(total - 8.984294) < 0.000002

    audit("COMBINED — DESCRIPTIVE ONLY", combined)

    print("\nIMPORTANT LIMITATIONS:")
    print("Opening high and low are pre-entry observations.")
    print("Their order does not establish a confirmed reversal.")
    print("Only completed 5m candles before entry are used.")
    print("No entry candle, future data, or new filters.")
    print("V18 unchanged. No files written.")
    print("STEP 59F-5H-43K-25: PASS")

if __name__ == "__main__":
    main()
