
#!/usr/bin/env python3
"""
AIMn — STEP 59F-5H-43K-54

TWO-CANDLE RECOVERY × BEARISH STRUCTURE
INTERACTION AUDIT

NVDA SHORT — 5-minute candles

READ-ONLY OBSERVATIONAL RESEARCH

Uses the established Step 53 calculations.
Does not alter the trading engine, entries,
exits, parameters, or production files.

Questions:
1. Does two-bar direction help distinguish
   continuation from protective exits?
2. Does bearish structural integrity add
   useful information?
3. Does their combination work in both
   research and validation?
4. Which trades contradict the hypothesis?
5. Is the evidence sufficient to justify
   further testing?

No trading rules are approved here.
"""

import sys
from pathlib import Path
from collections import defaultdict

LAB = Path("kiss/visual_research")
sys.path.insert(0, str(LAB.resolve()))

import step59f_5h_43k_53 as previous
import step59f_5h43c_flat_long_replay as engine


PARAMS = dict(previous.PARAMS)
DATASETS = previous.DATASETS

EXPECTED_TRADES = 36
EXPECTED_NET = 8.984294
EXPECTED_V_PROFIT = 31
TOLERANCE = 0.000002

CONTINUATION = "CONTINUATION_CANDIDATE"
PROTECTION = "PROTECTION_CANDIDATE"

OTHER_LABELS = (
    "INCONCLUSIVE",
    "TWO_SIDED_RISK",
    "NO_FUTURE_DATA",
)


def two_bar_direction(value):
    if value > 0:
        return "TWO_BAR_UP"

    if value < 0:
        return "TWO_BAR_DOWN"

    return "TWO_BAR_FLAT"


def structure_state(pre):
    if pre["swing_break"]:
        return "SWING_HIGH_BROKEN"

    if (
        pre["lower_highs"] >= 3
        and pre["lower_lows"] >= 3
    ):
        return "BEARISH_INTACT"

    return "STRUCTURE_WEAKENED"


def interaction_label(record):
    return (
        record["two_bar_group"]
        + " | "
        + record["structure_group"]
    )


def classify_outcome(quality):
    if quality == CONTINUATION:
        return "CONT"

    if quality == PROTECTION:
        return "PROTECT"

    return "OTHER"


def load_dataset(name, config):
    rows = previous.load_rows(config["path"])

    candles = previous.regular_candles(rows)

    result = engine.run(
        rows=rows,
        **PARAMS,
    )

    assert (
        result["trade_count"]
        == config["trades"]
    ), f"{name}: baseline trade count changed"

    assert abs(
        result["net_pnl_pct"]
        - config["net"]
    ) < TOLERANCE, (
        f"{name}: baseline net changed"
    )

    trades = sorted(
        result["trades"],
        key=lambda trade: previous.parse_time(
            trade["entry_time"]
        ),
    )

    records = []

    for index, trade in enumerate(trades):
        if trade.get("exit_reason") != "V_PROFIT":
            continue

        entry_time = previous.parse_time(
            trade["entry_time"]
        )

        exit_time = previous.parse_time(
            trade["exit_time"]
        )

        next_entry = None

        if index + 1 < len(trades):
            next_entry = previous.parse_time(
                trades[index + 1]["entry_time"]
            )

        pre = previous.pre_exit_evidence(
            candles,
            exit_time,
        )

        assert pre is not None, (
            f"{name}: missing pre-exit evidence "
            f"at {exit_time}"
        )

        future = previous.post_exit_evidence(
            candles,
            exit_time,
            next_entry,
        )

        two_bar = two_bar_direction(
            pre["last_two_change"]
        )

        structure = structure_state(pre)

        record = {
            "dataset": name,
            "entry": entry_time,
            "exit": exit_time,
            "net": float(
                trade["net_pnl_pct"]
            ),
            "quality": future["quality"],
            "outcome": classify_outcome(
                future["quality"]
            ),
            "future_down": future["down"],
            "future_up": future["up"],
            "future_close": future["close"],
            "future_bars": future["bars"],
            "two_bar": pre["last_two_change"],
            "two_bar_group": two_bar,
            "structure_group": structure,
            "recovery": pre["recovery"],
            "acceleration": pre["acceleration"],
            "last_change": pre["last_change"],
            "five_bar": pre["five_candle_change"],
            "lower_highs": pre["lower_highs"],
            "lower_lows": pre["lower_lows"],
            "bullish": pre["bullish"],
            "bearish": pre["bearish"],
            "swing_break": pre["swing_break"],
            "pre_structure": pre["structure"],
            "consecutive_bullish":
                pre["consecutive_bullish"],
        }

        record["interaction"] = (
            interaction_label(record)
        )

        records.append(record)

    assert len(records) == config["v_profit"], (
        f"{name}: V_PROFIT count changed"
    )

    return result, records


def count_outcomes(records):
    return {
        "CONT": sum(
            r["outcome"] == "CONT"
            for r in records
        ),
        "PROTECT": sum(
            r["outcome"] == "PROTECT"
            for r in records
        ),
        "OTHER": sum(
            r["outcome"] == "OTHER"
            for r in records
        ),
    }


def print_group_table(records, key):
    groups = defaultdict(list)

    for record in records:
        groups[record[key]].append(record)

    print()
    print(key.upper())
    print("-" * 105)

    for label, group in sorted(groups.items()):
        counts = count_outcomes(group)

        avg_two_bar = sum(
            r["two_bar"]
            for r in group
        ) / len(group)

        avg_recovery = sum(
            r["recovery"]
            for r in group
        ) / len(group)

        print(
            f"{label:46s} "
            f"N={len(group):2d} "
            f"CONT={counts['CONT']:2d} "
            f"PROTECT={counts['PROTECT']:2d} "
            f"OTHER={counts['OTHER']:2d} "
            f"AVG_2BAR={avg_two_bar:+.4f}% "
            f"AVG_REC={avg_recovery:+.4f}%"
        )


def print_interaction(records, title):
    print()
    print("=" * 115)
    print(title)
    print("=" * 115)

    print_group_table(
        records,
        "two_bar_group",
    )

    print_group_table(
        records,
        "structure_group",
    )

    print_group_table(
        records,
        "interaction",
    )


def fmt(value):
    if value is None:
        return "NA"

    return f"{value:+.4f}%"


def audit_record(record):
    print(
        f'{record["dataset"]} '
        f'ENTRY={record["entry"]} '
        f'EXIT={record["exit"]} '
        f'NET={record["net"]:+.6f}% '
        f'QUALITY={record["quality"]} '
        f'TWO_BAR={fmt(record["two_bar"])} '
        f'STRUCTURE={record["structure_group"]} '
        f'LH={record["lower_highs"]} '
        f'LL={record["lower_lows"]} '
        f'BEAR={record["bearish"]} '
        f'BULL={record["bullish"]} '
        f'RECOVERY={fmt(record["recovery"])} '
        f'ACCEL={record["acceleration"]:+.4f}pp '
        f'FIVE_BAR={fmt(record["five_bar"])} '
        f'FUTURE_DOWN={fmt(record["future_down"])} '
        f'FUTURE_UP={fmt(record["future_up"])} '
        f'FUTURE_CLOSE={fmt(record["future_close"])} '
        f'FUTURE_BARS={record["future_bars"]}'
    )


def print_counterexamples(records):
    print()
    print("=" * 115)
    print("COUNTEREXAMPLE AUDIT")
    print("=" * 115)

    cases = {
        "TWO_BAR_DOWN_BUT_PROTECTION": [],
        "TWO_BAR_UP_BUT_CONTINUATION": [],
        "BEARISH_INTACT_BUT_PROTECTION": [],
        "STRUCTURE_WEAKENED_BUT_CONTINUATION": [],
    }

    for record in records:
        if (
            record["two_bar_group"] == "TWO_BAR_DOWN"
            and record["outcome"] == "PROTECT"
        ):
            cases[
                "TWO_BAR_DOWN_BUT_PROTECTION"
            ].append(record)

        if (
            record["two_bar_group"] == "TWO_BAR_UP"
            and record["outcome"] == "CONT"
        ):
            cases[
                "TWO_BAR_UP_BUT_CONTINUATION"
            ].append(record)

        if (
            record["structure_group"] == "BEARISH_INTACT"
            and record["outcome"] == "PROTECT"
        ):
            cases[
                "BEARISH_INTACT_BUT_PROTECTION"
            ].append(record)

        if (
            record["structure_group"]
            == "STRUCTURE_WEAKENED"
            and record["outcome"] == "CONT"
        ):
            cases[
                "STRUCTURE_WEAKENED_BUT_CONTINUATION"
            ].append(record)

    for label, group in cases.items():
        print()
        print(
            f"{label}: N={len(group)}"
        )

        for record in group:
            audit_record(record)


def print_candidate_audit(records):
    print()
    print("=" * 115)
    print("ALL CONTINUATION AND PROTECTION CASES")
    print("=" * 115)

    selected = [
        record
        for record in records
        if record["outcome"] in (
            "CONT",
            "PROTECT",
        )
    ]

    for record in selected:
        audit_record(record)


def print_cross_validation(records):
    print()
    print("=" * 115)
    print("RESEARCH VS VALIDATION — INTERACTION")
    print("=" * 115)

    labels = sorted(
        set(
            r["interaction"]
            for r in records
        )
    )

    for label in labels:
        print()
        print(label)

        for dataset in DATASETS:
            group = [
                r for r in records
                if (
                    r["dataset"] == dataset
                    and r["interaction"] == label
                )
            ]

            counts = count_outcomes(group)

            print(
                f"{dataset:12s} "
                f"N={len(group):2d} "
                f"CONT={counts['CONT']:2d} "
                f"PROTECT={counts['PROTECT']:2d} "
                f"OTHER={counts['OTHER']:2d}"
            )


def print_coverage(records):
    print()
    print("=" * 115)
    print("EVIDENCE COVERAGE")
    print("=" * 115)

    for dataset in DATASETS:
        group = [
            r for r in records
            if r["dataset"] == dataset
        ]

        counts = count_outcomes(group)

        decisive = (
            counts["CONT"]
            + counts["PROTECT"]
        )

        print(
            f"{dataset}: "
            f"V_PROFIT={len(group)} "
            f"CONT={counts['CONT']} "
            f"PROTECT={counts['PROTECT']} "
            f"OTHER={counts['OTHER']} "
            f"DECISIVE={decisive}"
        )

    print()
    print(
        "OTHER includes inconclusive, "
        "two-sided-risk and missing-future "
        "observations."
    )

    print(
        "These are descriptive outcome groups, "
        "not validated trade signals."
    )


def main():
    print("AIMn — STEP 59F-5H-43K-54")
    print(
        "TWO-CANDLE RECOVERY × "
        "BEARISH STRUCTURE INTERACTION"
    )
    print("NVDA SHORT 5m")
    print("READ-ONLY OBSERVATIONAL RESEARCH")

    all_records = []
    total_trades = 0
    total_net = 0.0

    for name, config in DATASETS.items():
        result, records = load_dataset(
            name,
            config,
        )

        total_trades += result["trade_count"]
        total_net += result["net_pnl_pct"]

        print_interaction(
            records,
            name,
        )

        all_records.extend(records)

    assert total_trades == EXPECTED_TRADES, (
        "Combined baseline trade count changed"
    )

    assert abs(
        total_net - EXPECTED_NET
    ) < TOLERANCE, (
        "Combined baseline net changed"
    )

    assert (
        len(all_records)
        == EXPECTED_V_PROFIT
    ), (
        "Combined V_PROFIT count changed"
    )

    print_interaction(
        all_records,
        "COMBINED — DESCRIPTIVE ONLY",
    )

    print_cross_validation(all_records)

    print_coverage(all_records)

    print_candidate_audit(all_records)

    print_counterexamples(all_records)

    print()
    print("=" * 115)
    print("BASELINE INTEGRITY")
    print("=" * 115)

    print(
        f"TRADES={total_trades}"
    )

    print(
        f"NET_PNL={total_net:+.6f}%"
    )

    print(
        f"V_PROFIT={len(all_records)}"
    )

    print()
    print("LIMITATIONS")

    print(
        "All decision-time features use "
        "completed candles strictly before "
        "the recorded exit timestamp."
    )

    print(
        "Future observations exclude "
        "the exit-timestamp candle."
    )

    print(
        "Future price reference is the "
        "first subsequent candle open, "
        "not an actual execution fill."
    )

    print(
        "Candle timestamp convention "
        "and execution timing remain "
        "unverified."
    )

    print(
        "Three subsequent candles may "
        "not always be available."
    )

    print(
        "Intrabar high-low ordering "
        "is unknown."
    )

    print(
        "Small samples and selected "
        "V_PROFIT exits limit inference."
    )

    print(
        "Hindsight outcomes cannot "
        "be used as trading inputs."
    )

    print(
        "No thresholds optimized."
    )

    print(
        "No filters approved."
    )

    print(
        "No file writes."
    )

    print(
        "V18 unchanged."
    )

    print()
    print("STEP 59F-5H-43K-54: PASS")


if __name__ == "__main__":
    main()
