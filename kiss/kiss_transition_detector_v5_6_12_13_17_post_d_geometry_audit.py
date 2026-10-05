"""
AIMn / KISS V13.17
POST-FIRST-DETERIORATION TRAJECTORY GEOMETRY AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING
NO THRESHOLD PROMOTION

PURPOSE
-------
Study what happens AFTER the first DETERIORATING checkpoint.

The prior four-anchor audit revealed an important distinction:

    PF cases:
        D -> continued deterioration -> PF

    QQQ:
        D -> deterioration -> recovery in return
        while state remains DETERIORATING

This audit therefore studies the actual trajectory vector,
rather than treating state labels as the entire trajectory.

ALL 28 V13.17 CASES ARE INCLUDED.

For every case we report:

    first D checkpoint
    return at first D
    subsequent returns
    return deltas
    favorable-ratio deltas
    adverse-ratio deltas
    MAE deltas
    MFE deltas
    state sequence after first D

No threshold is proposed.
No trading rule is proposed.
This is descriptive research only.
"""

from kiss.kiss_transition_detector_v5_6_12_13_17_case_aware_validation import (
    build_v1317_research_paths,
)


def state_sequence(path):
    return [p.state for p in path.points]


def has_pf_by_60(path):
    return any(
        p.state == "PERSISTENT_FAILURE"
        for p in path.points
    )


def first_d_index(path):
    for i, point in enumerate(path.points):
        if point.state == "DETERIORATING":
            return i
    return None


def sign(value):
    if value > 0:
        return "+"
    if value < 0:
        return "-"
    return "0"


def return_delta_sequence(path, start_index):
    points = path.points

    deltas = []

    for i in range(start_index + 1, len(points)):
        previous = points[i - 1]
        current = points[i]

        delta = current.return_pct - previous.return_pct

        deltas.append(delta)

    return deltas


def classify_post_d_return_geometry(deltas):
    """
    Purely descriptive classification.

    No numerical threshold is used.

    Categories describe the signs of successive return changes.
    """

    if not deltas:
        return "NO_POST_D_DATA"

    signs = [sign(x) for x in deltas]

    if all(x == "+" for x in signs):
        return "CONSISTENT_POSITIVE_RETURN_CHANGE"

    if all(x == "-" for x in signs):
        return "CONSISTENT_NEGATIVE_RETURN_CHANGE"

    if "+" in signs and "-" in signs:
        return "MIXED_RETURN_CHANGE"

    return "ZERO_OR_MIXED"


def print_case(path, case_number):

    d_index = first_d_index(path)

    outcome = (
        "LATER_PF_BY_60"
        if has_pf_by_60(path)
        else "NO_PF_BY_60"
    )

    print("-" * 130)
    print(
        f"CASE #{case_number:02d}  "
        f"{path.symbol:<6} "
        f"{path.direction:<5} "
        f"{outcome:<15}"
    )

    print(
        f"opposite_time={path.opposite_time}  "
        f"official_time={path.official_time}"
    )

    print()

    print(
        "FULL STATE PATH:"
    )

    print(
        " -> ".join(
            f"+{p.minutes}:{p.state}"
            for p in path.points
        )
    )

    if d_index is None:
        print()
        print("FIRST D: NONE")
        print()
        return {
            "case": case_number,
            "symbol": path.symbol,
            "direction": path.direction,
            "outcome": outcome,
            "first_d_min": None,
            "geometry": "NO_D",
            "deltas": [],
        }

    first_d = path.points[d_index]

    print()
    print(
        f"FIRST DETERIORATING = +{first_d.minutes}"
    )

    print(
        f"return={first_d.return_pct:+.6f}  "
        f"fav={first_d.favorable_ratio:.6f}  "
        f"adv={first_d.adverse_ratio:.6f}  "
        f"conadv={float(first_d.consecutive_adverse):.0f}  "
        f"mae={first_d.mae_pct:+.6f}  "
        f"mfe={first_d.mfe_pct:+.6f}"
    )

    print()
    print("POST-D VECTOR")
    print()

    print(
        "MIN".ljust(7),
        "STATE".ljust(22),
        "RETURN".rjust(12),
        "dRETURN".rjust(12),
        "dFAV".rjust(12),
        "dADV".rjust(12),
        "dMAE".rjust(12),
        "dMFE".rjust(12),
    )

    deltas = []

    previous = first_d

    for point in path.points[d_index:]:

        if point is first_d:
            print(
                f"{point.minutes:>5} ",
                f"{point.state:<22}",
                f"{point.return_pct:12.6f}",
                f"{'--':>12}",
                f"{'--':>12}",
                f"{'--':>12}",
                f"{'--':>12}",
                f"{'--':>12}",
            )
            continue

        d_return = point.return_pct - previous.return_pct
        d_fav = point.favorable_ratio - previous.favorable_ratio
        d_adv = point.adverse_ratio - previous.adverse_ratio
        d_mae = point.mae_pct - previous.mae_pct
        d_mfe = point.mfe_pct - previous.mfe_pct

        deltas.append(d_return)

        print(
            f"{point.minutes:>5} ",
            f"{point.state:<22}",
            f"{point.return_pct:12.6f}",
            f"{d_return:+12.6f}",
            f"{d_fav:+12.6f}",
            f"{d_adv:+12.6f}",
            f"{d_mae:+12.6f}",
            f"{d_mfe:+12.6f}",
        )

        previous = point

    geometry = classify_post_d_return_geometry(deltas)

    print()
    print(f"POST-D RETURN GEOMETRY = {geometry}")

    print()
    print(
        "POST-D RETURN DELTA SIGNS = "
        + " ".join(sign(x) for x in deltas)
    )

    if deltas:
        positive = sum(1 for x in deltas if x > 0)
        negative = sum(1 for x in deltas if x < 0)

        print(
            f"positive return changes = {positive}"
        )
        print(
            f"negative return changes = {negative}"
        )

        print(
            f"net return change after first D = "
            f"{sum(deltas):+.6f}"
        )

        print(
            f"largest positive return change = "
            f"{max(deltas):+.6f}"
        )

        print(
            f"largest negative return change = "
            f"{min(deltas):+.6f}"
        )

    return {
        "case": case_number,
        "symbol": path.symbol,
        "direction": path.direction,
        "outcome": outcome,
        "first_d_min": first_d.minutes,
        "geometry": geometry,
        "deltas": deltas,
    }


def print_summary(results):

    print()
    print("=" * 130)
    print("POST-FIRST-D GEOMETRY SUMMARY")
    print("=" * 130)
    print()

    print(
        "CASE".ljust(7),
        "SYMBOL".ljust(8),
        "DIR".ljust(7),
        "OUTCOME".ljust(18),
        "FIRST_D".rjust(9),
        "GEOMETRY"
    )

    for r in results:

        print(
            f"{r['case']:>4}   ",
            f"{r['symbol']:<8}",
            f"{r['direction']:<7}",
            f"{r['outcome']:<18}",
            f"{str(r['first_d_min']):>9}",
            r["geometry"]
        )


def print_geometry_counts(results):

    print()
    print("=" * 130)
    print("GEOMETRY COUNTS BY OUTCOME")
    print("=" * 130)
    print()

    geometries = sorted(
        set(r["geometry"] for r in results)
    )

    for geometry in geometries:

        pf = sum(
            1
            for r in results
            if r["geometry"] == geometry
            and r["outcome"] == "LATER_PF_BY_60"
        )

        no_pf = sum(
            1
            for r in results
            if r["geometry"] == geometry
            and r["outcome"] == "NO_PF_BY_60"
        )

        total = pf + no_pf

        print(
            f"{geometry:<40} "
            f"TOTAL={total:>2} "
            f"PF={pf:>2} "
            f"NO_PF={no_pf:>2}"
        )


def print_reversal_candidates(results):

    print()
    print("=" * 130)
    print("CASES WITH A POSITIVE RETURN CHANGE AFTER FIRST D")
    print("=" * 130)
    print()

    found = 0

    for r in results:

        positive_changes = [
            x for x in r["deltas"]
            if x > 0
        ]

        if not positive_changes:
            continue

        found += 1

        print(
            f"CASE #{r['case']:02d} "
            f"{r['symbol']} "
            f"{r['direction']} "
            f"{r['outcome']}"
        )

        print(
            f"  first D = +{r['first_d_min']}m"
        )

        print(
            f"  delta signs = "
            f"{' '.join(sign(x) for x in r['deltas'])}"
        )

        print(
            f"  positive changes = "
            f"{len(positive_changes)}"
        )

        print()

    if found == 0:
        print("No post-D positive return changes found.")


def main():

    print("=" * 130)
    print("AIMn / KISS V13.17 POST-FIRST-DETERIORATION TRAJECTORY GEOMETRY AUDIT")
    print("=" * 130)
    print()
    print("RESEARCH ONLY")
    print("NO ORDERS")
    print("NO PRODUCTION ENGINE CHANGES")
    print("NO AI TRAINING")
    print("NO THRESHOLD PROMOTION")
    print()

    paths = build_v1317_research_paths()

    print()
    print(f"TOTAL TRAJECTORY CASES = {len(paths)}")
    print()

    results = []

    for case_number, path in enumerate(paths, start=1):

        result = print_case(
            path,
            case_number
        )

        results.append(result)

    print_summary(results)

    print_geometry_counts(results)

    print_reversal_candidates(results)

    print()
    print("=" * 130)
    print("AUDIT COMPLETE")
    print("=" * 130)


if __name__ == "__main__":
    main()
