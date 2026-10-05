"""
AIMn / KISS V13.17
SECOND-NEGATIVE COUNTEREXAMPLE AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING
NO THRESHOLD PROMOTION

Purpose
-------
Study every trajectory that reaches a SECOND CONSECUTIVE NEGATIVE
return-change interval.

The causal features are measured only at the second-negative
checkpoint.

The eventual PF / NO_PF label is kept separate as the research
outcome.

This audit specifically asks:

    What distinguishes the second-negative cases that eventually
    become persistent failure from the cases that recover?

No trading rule is created.
"""

from pathlib import Path
import sys

# ----------------------------------------------------------------------
# Import the existing V13.17 research path builder.
# ----------------------------------------------------------------------

from kiss.kiss_transition_detector_v5_6_12_13_17_case_aware_validation import (
    build_v1317_research_paths,
)


STATE_PF = "PERSISTENT_FAILURE"


def outcome_of(path):
    """
    Established V13.17-style final-checkpoint outcome.

    A temporary PF earlier in the trajectory does not qualify.
    The final available checkpoint must be PF.
    """
    if path.points and path.points[-1].state == STATE_PF:
        return "LATER_PF_BY_60"

    return "NO_PF_BY_60"


def get_second_negative(path):
    """
    Find the second consecutive negative return-change interval.

    Return the destination StatePoint and the causal delta features.

    A feature is calculated only from the current point and the
    immediately preceding completed checkpoint.
    """

    points = path.points

    negative_run = 0

    for i in range(1, len(points)):

        prev = points[i - 1]
        cur = points[i]

        d_return = cur.return_pct - prev.return_pct

        if d_return < 0:
            negative_run += 1
        else:
            negative_run = 0

        if negative_run == 2:

            return {
                "prev": prev,
                "cur": cur,
                "elapsed": cur.minutes - path.points[0].minutes,
                "d_return": d_return,
                "d_fav": cur.favorable_ratio - prev.favorable_ratio,
                "d_adv": cur.adverse_ratio - prev.adverse_ratio,
                "d_conadv": cur.consecutive_adverse - prev.consecutive_adverse,
                "d_mae": cur.mae_pct - prev.mae_pct,
                "d_mfe": cur.mfe_pct - prev.mfe_pct,
            }

    return None


def print_case(record):

    path = record["path"]
    x = record["second"]

    prev = x["prev"]
    cur = x["cur"]

    print("-" * 110)

    print(
        f"CASE #{record['case_no']:02d}  "
        f"{path.symbol:<6} "
        f"{path.direction:<5} "
        f"{record['outcome']}"
    )

    print()

    print(
        f"SECOND NEGATIVE = D+{x['elapsed']}m"
    )

    print(
        f"PREVIOUS CHECKPOINT"
        f"  minute=+{prev.minutes} "
        f"state={prev.state:<22} "
        f"return={prev.return_pct:+.6f}"
    )

    print(
        f"SECOND-NEGATIVE CHECKPOINT"
        f"  minute=+{cur.minutes} "
        f"state={cur.state:<22} "
        f"return={cur.return_pct:+.6f}"
    )

    print()

    print(
        f"dRETURN   = {x['d_return']:+.6f}"
    )

    print(
        f"dFAV      = {x['d_fav']:+.6f}"
    )

    print(
        f"dADV      = {x['d_adv']:+.6f}"
    )

    print(
        f"dCONADV   = {x['d_conadv']:+.6f}"
    )

    print(
        f"dMAE      = {x['d_mae']:+.6f}"
    )

    print(
        f"dMFE      = {x['d_mfe']:+.6f}"
    )

    print()

    print(
        f"CURRENT RETURN       = {cur.return_pct:+.6f}"
    )

    print(
        f"CURRENT FAV RATIO    = {cur.favorable_ratio:.6f}"
    )

    print(
        f"CURRENT ADV RATIO    = {cur.adverse_ratio:.6f}"
    )

    print(
        f"CURRENT CONSEC ADV   = {cur.consecutive_adverse}"
    )

    print(
        f"CURRENT MAE          = {cur.mae_pct:+.6f}"
    )

    print(
        f"CURRENT MFE          = {cur.mfe_pct:+.6f}"
    )


def main():

    print("=" * 110)
    print("AIMn / KISS V13.17 SECOND-NEGATIVE COUNTEREXAMPLE AUDIT")
    print("=" * 110)

    print()
    print("RESEARCH ONLY")
    print("NO ORDERS")
    print("NO PRODUCTION ENGINE CHANGES")
    print("NO AI TRAINING")
    print("NO THRESHOLD PROMOTION")
    print()

    paths = build_v1317_research_paths()

    print(f"TOTAL TRAJECTORY CASES = {len(paths)}")
    print()

    records = []

    for case_no, path in enumerate(paths, start=1):

        second = get_second_negative(path)

        if second is None:
            continue

        records.append(
            {
                "case_no": case_no,
                "path": path,
                "second": second,
                "outcome": outcome_of(path),
            }
        )

    pf = [
        r for r in records
        if r["outcome"] == "LATER_PF_BY_60"
    ]

    no_pf = [
        r for r in records
        if r["outcome"] == "NO_PF_BY_60"
    ]

    print("=" * 110)
    print("SECOND-NEGATIVE CASES")
    print("=" * 110)

    print(
        f"TOTAL SECOND-NEGATIVE CASES = {len(records)}"
    )

    print(
        f"LATER_PF_BY_60 = {len(pf)}"
    )

    print(
        f"NO_PF_BY_60    = {len(no_pf)}"
    )

    print()

    print("=" * 110)
    print("PF CASES")
    print("=" * 110)

    for r in pf:
        print_case(r)

    print()

    print("=" * 110)
    print("NO-PF CASES / COUNTEREXAMPLES")
    print("=" * 110)

    for r in no_pf:
        print_case(r)

    print()

    # --------------------------------------------------------------
    # Compact comparison
    # --------------------------------------------------------------

    def avg(rows, key):
        if not rows:
            return 0.0
        return sum(key(r) for r in rows) / len(rows)

    print("=" * 110)
    print("GROUP COMPARISON AT SECOND NEGATIVE")
    print("=" * 110)

    print()

    headers = [
        "GROUP",
        "N",
        "AVG dRETURN",
        "AVG dFAV",
        "AVG dADV",
        "AVG dCONADV",
        "AVG dMAE",
        "AVG dMFE",
        "AVG RETURN",
        "AVG FAV",
        "AVG ADV",
        "AVG CONADV",
    ]

    print(
        f"{headers[0]:<18}"
        f"{headers[1]:>5}"
        f"{headers[2]:>14}"
        f"{headers[3]:>12}"
        f"{headers[4]:>12}"
        f"{headers[5]:>13}"
        f"{headers[6]:>12}"
        f"{headers[7]:>12}"
        f"{headers[8]:>14}"
        f"{headers[9]:>10}"
        f"{headers[10]:>10}"
        f"{headers[11]:>12}"
    )

    print("-" * 145)

    for name, rows in [
        ("LATER_PF_BY_60", pf),
        ("NO_PF_BY_60", no_pf),
    ]:

        print(
            f"{name:<18}"
            f"{len(rows):>5}"
            f"{avg(rows, lambda r: r['second']['d_return']):>14.6f}"
            f"{avg(rows, lambda r: r['second']['d_fav']):>12.6f}"
            f"{avg(rows, lambda r: r['second']['d_adv']):>12.6f}"
            f"{avg(rows, lambda r: r['second']['d_conadv']):>13.6f}"
            f"{avg(rows, lambda r: r['second']['d_mae']):>12.6f}"
            f"{avg(rows, lambda r: r['second']['d_mfe']):>12.6f}"
            f"{avg(rows, lambda r: r['second']['cur'].return_pct):>14.6f}"
            f"{avg(rows, lambda r: r['second']['cur'].favorable_ratio):>10.6f}"
            f"{avg(rows, lambda r: r['second']['cur'].adverse_ratio):>10.6f}"
            f"{avg(rows, lambda r: r['second']['cur'].consecutive_adverse):>12.6f}"
        )

    # --------------------------------------------------------------
    # Direction controlled comparison
    # --------------------------------------------------------------

    print()
    print("=" * 110)
    print("DIRECTION-CONTROLLED SECOND-NEGATIVE COMPARISON")
    print("=" * 110)

    for direction in ["LONG", "SHORT"]:

        print()
        print(f"### {direction}")

        for name, rows in [
            ("PF", [
                r for r in pf
                if r["path"].direction == direction
            ]),
            ("NO_PF", [
                r for r in no_pf
                if r["path"].direction == direction
            ]),
        ]:

            if not rows:
                continue

            print(
                f"{name:<8}"
                f"N={len(rows):<3} "
                f"avg_dRETURN={avg(rows, lambda r: r['second']['d_return']):+.6f} "
                f"avg_dFAV={avg(rows, lambda r: r['second']['d_fav']):+.6f} "
                f"avg_dADV={avg(rows, lambda r: r['second']['d_adv']):+.6f} "
                f"avg_dCONADV={avg(rows, lambda r: r['second']['d_conadv']):+.6f} "
                f"avg_RETURN={avg(rows, lambda r: r['second']['cur'].return_pct):+.6f} "
                f"avg_FAV={avg(rows, lambda r: r['second']['cur'].favorable_ratio):.6f} "
                f"avg_ADV={avg(rows, lambda r: r['second']['cur'].adverse_ratio):.6f}"
            )

    # --------------------------------------------------------------
    # State at second negative
    # --------------------------------------------------------------

    print()
    print("=" * 110)
    print("STATE AT SECOND NEGATIVE")
    print("=" * 110)

    states = sorted(
        set(r["second"]["cur"].state for r in records)
    )

    for state in states:

        pf_n = sum(
            1 for r in pf
            if r["second"]["cur"].state == state
        )

        no_n = sum(
            1 for r in no_pf
            if r["second"]["cur"].state == state
        )

        print(
            f"{state:<24} "
            f"PF={pf_n:<3} "
            f"NO_PF={no_n:<3}"
        )

    # --------------------------------------------------------------
    # Research interpretation
    # --------------------------------------------------------------

    print()
    print("=" * 110)
    print("RESEARCH INTERPRETATION")
    print("=" * 110)

    print(
        """
1. The second-negative checkpoint is causal: all listed features are
   available at that checkpoint.

2. Eventual PF / NO_PF is used only as the future research label.

3. A large negative dRETURN by itself is NOT assumed to predict PF.

4. State at the second-negative checkpoint is examined separately.

5. Favorable/adverse movement and consecutive-adverse behavior are
   examined as trajectory context.

6. Direction-controlled results are reported separately.

7. The NO_PF cases are treated as counterexamples, not discarded.

8. No threshold, score, exit rule, or production behavior is created.

9. The purpose is to determine whether second-negative persistence
   contains additional structure beyond the negative count itself.
"""
    )


if __name__ == "__main__":
    main()
