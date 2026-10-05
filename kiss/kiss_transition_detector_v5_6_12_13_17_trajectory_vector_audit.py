"""
AIMn / KISS V13.17
TRAJECTORY VECTOR / TRANSITION GEOMETRY AUDIT

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING
NO THRESHOLD PROMOTION

PURPOSE
-------
Reconstruct the actual StatePoint trajectory vectors for four
specific V13.17 anchor cases.

The cases are identified by their COMPLETE state trajectory,
not by partial state landmarks.

ANCHOR CASES
------------
1. AMZN LONG  -> LATER_PF_BY_60
2. NVDA LONG  -> LATER_PF_BY_60
3. GOOGL SHORT -> LATER_PF_BY_60
4. QQQ SHORT  -> NO_PF_BY_60

For every StatePoint report:

    minutes
    state
    return_pct
    favorable_ratio
    adverse_ratio
    consecutive_adverse
    mae_pct
    mfe_pct

Also report successive vector deltas between checkpoints.

IMPORTANT
---------
This audit does not modify the V13.17 research builder.
"""

from kiss.kiss_transition_detector_v5_6_12_13_17_case_aware_validation import (
    build_v1317_research_paths,
)


# ---------------------------------------------------------------------
# EXACT TRAJECTORY SIGNATURES
# ---------------------------------------------------------------------

ANCHORS = {
    "AMZN_LONG_PF": {
        "symbol": "AMZN",
        "direction": "LONG",
        "expected": "LATER_PF_BY_60",
        "states": [
            "RECOVERING",
            "NEUTRAL",
            "DETERIORATING",
            "DETERIORATING",
            "DETERIORATING",
            "PERSISTENT_FAILURE",
            "PERSISTENT_FAILURE",
        ],
    },

    "NVDA_LONG_PF": {
        "symbol": "NVDA",
        "direction": "LONG",
        "expected": "LATER_PF_BY_60",
        "states": [
            "DETERIORATING",
            "RECOVERING",
            "NEUTRAL",
            "DETERIORATING",
            "DETERIORATING",
            "PERSISTENT_FAILURE",
            "PERSISTENT_FAILURE",
        ],
    },

    "GOOGL_SHORT_PF": {
        "symbol": "GOOGL",
        "direction": "SHORT",
        "expected": "LATER_PF_BY_60",
        "states": [
            "RECOVERING",
            "RECOVERING",
            "RECOVERING",
            "DETERIORATING",
            "DETERIORATING",
            "PERSISTENT_FAILURE",
            "PERSISTENT_FAILURE",
        ],
    },

    "QQQ_SHORT_NO_PF": {
        "symbol": "QQQ",
        "direction": "SHORT",
        "expected": "NO_PF_BY_60",
        "states": [
            "RECOVERING",
            "RECOVERING",
            "DETERIORATING",
            "DETERIORATING",
            "DETERIORATING",
            "DETERIORATING",
            "DETERIORATING",
        ],
    },
}


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def trajectory_states(path):
    return [point.state for point in path.points]


def find_matches(paths, spec):
    matches = []

    for path in paths:

        if path.symbol != spec["symbol"]:
            continue

        if path.direction != spec["direction"]:
            continue

        states = trajectory_states(path)

        if states == spec["states"]:
            matches.append(path)

    return matches


def print_point(point):
    print(
        f"{point.minutes:>5} "
        f"{point.state:<22} "
        f"{point.return_pct:>12.6f} "
        f"{point.favorable_ratio:>10.6f} "
        f"{point.adverse_ratio:>10.6f} "
        f"{float(point.consecutive_adverse):>10.0f} "
        f"{point.mae_pct:>12.6f} "
        f"{point.mfe_pct:>12.6f}"
    )


def print_vector_deltas(path):

    print()
    print("SUCCESSIVE TRAJECTORY DELTAS")
    print()

    points = path.points

    if len(points) < 2:
        print("Not enough points for delta analysis.")
        return

    print(
        "FROM->TO".ljust(12),
        "dRETURN".rjust(12),
        "dFAV".rjust(12),
        "dADV".rjust(12),
        "dCONADV".rjust(12),
        "dMAE".rjust(12),
        "dMFE".rjust(12),
    )

    for previous, current in zip(points, points[1:]):

        print(
            f"{previous.minutes}->{current.minutes}".ljust(12),
            f"{current.return_pct - previous.return_pct:12.6f}",
            f"{current.favorable_ratio - previous.favorable_ratio:12.6f}",
            f"{current.adverse_ratio - previous.adverse_ratio:12.6f}",
            f"{float(current.consecutive_adverse) - float(previous.consecutive_adverse):12.0f}",
            f"{current.mae_pct - previous.mae_pct:12.6f}",
            f"{current.mfe_pct - previous.mfe_pct:12.6f}",
        )


def print_first_d_transition(path):

    points = path.points

    d_index = None

    for i, point in enumerate(points):
        if point.state == "DETERIORATING":
            d_index = i
            break

    if d_index is None:
        print("No DETERIORATING checkpoint found.")
        return

    current = points[d_index]

    print()
    print("FIRST DETERIORATING CHECKPOINT")
    print()
    print(f"minute               = +{current.minutes}")
    print(f"state                = {current.state}")
    print(f"return_pct           = {current.return_pct:.6f}")
    print(f"favorable_ratio      = {current.favorable_ratio:.6f}")
    print(f"adverse_ratio        = {current.adverse_ratio:.6f}")
    print(f"consecutive_adverse  = {float(current.consecutive_adverse):.0f}")
    print(f"mae_pct              = {current.mae_pct:.6f}")
    print(f"mfe_pct              = {current.mfe_pct:.6f}")

    if d_index > 0:

        previous = points[d_index - 1]

        print()
        print("TRANSITION INTO FIRST D")
        print()
        print(
            f"+{previous.minutes} {previous.state}"
            f" -> +{current.minutes} {current.state}"
        )

        print(
            f"d_return_pct  = "
            f"{current.return_pct - previous.return_pct:+.6f}"
        )

        print(
            f"d_favorable   = "
            f"{current.favorable_ratio - previous.favorable_ratio:+.6f}"
        )

        print(
            f"d_adverse     = "
            f"{current.adverse_ratio - previous.adverse_ratio:+.6f}"
        )

        print(
            f"d_conadv      = "
            f"{float(current.consecutive_adverse) - float(previous.consecutive_adverse):+.0f}"
        )

        print(
            f"d_mae         = "
            f"{current.mae_pct - previous.mae_pct:+.6f}"
        )

        print(
            f"d_mfe         = "
            f"{current.mfe_pct - previous.mfe_pct:+.6f}"
        )


def print_cross_case_summary(found):

    print()
    print("=" * 120)
    print("CROSS-CASE TRAJECTORY ANATOMY")
    print("=" * 120)
    print()

    for name, path in found.items():

        states = trajectory_states(path)

        print(
            f"{name:<20} "
            f"{path.symbol:<6} "
            f"{path.direction:<6} "
            f"{' -> '.join(states)}"
        )

    print()


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():

    print("=" * 120)
    print("AIMn / KISS V13.17 TRAJECTORY VECTOR / TRANSITION GEOMETRY AUDIT")
    print("=" * 120)
    print()
    print("RESEARCH ONLY")
    print("NO ORDERS")
    print("NO PRODUCTION ENGINE CHANGES")
    print("NO AI TRAINING")
    print("NO THRESHOLD PROMOTION")
    print()

    paths = build_v1317_research_paths()

    print()
    print("SEARCHING FOR EXACT COMPLETE-TRAJECTORY ANCHORS...")
    print()

    found = {}

    for name, spec in ANCHORS.items():

        matches = find_matches(paths, spec)

        print(
            f"{name:<25} "
            f"FOUND={len(matches)}"
        )

        if len(matches) == 1:
            found[name] = matches[0]

        elif len(matches) > 1:
            print(
                f"WARNING: {name} matched multiple cases."
            )

    print()

    print(
        f"ANCHOR CASES EXPECTED = {len(ANCHORS)}"
    )

    print(
        f"ANCHOR CASES FOUND    = {len(found)}"
    )

    print()

    if len(found) != len(ANCHORS):

        print(
            "WARNING: Exact four-anchor population was not "
            "reconstructed uniquely."
        )

        print(
            "No partial inference will be made."
        )

        print()
        print("=" * 120)
        print("AUDIT STOPPED")
        print("=" * 120)

        return

    # -----------------------------------------------------------------
    # PRINT EACH COMPLETE VECTOR
    # -----------------------------------------------------------------

    for name, path in found.items():

        spec = ANCHORS[name]

        print()
        print("=" * 120)
        print(name)
        print("=" * 120)

        print()
        print(f"symbol        = {path.symbol}")
        print(f"direction     = {path.direction}")
        print(f"expected      = {spec['expected']}")
        print(f"opposite_time = {path.opposite_time}")
        print(f"official_time = {path.official_time}")
        print(f"warning_lead  = {path.warning_lead}")

        print()
        print("TRAJECTORY")
        print()

        print(
            " -> ".join(
                f"+{p.minutes}={p.state}"
                for p in path.points
            )
        )

        print()
        print("FULL STATEPOINT VECTOR")
        print()

        print(
            "MIN".ljust(6),
            "STATE".ljust(22),
            "RETURN".rjust(12),
            "FAV".rjust(10),
            "ADV".rjust(10),
            "CONADV".rjust(10),
            "MAE".rjust(12),
            "MFE".rjust(12),
        )

        for point in path.points:
            print_point(point)

        print_vector_deltas(path)

        print_first_d_transition(path)

    # -----------------------------------------------------------------
    # CROSS CASE
    # -----------------------------------------------------------------

    print_cross_case_summary(found)

    print("=" * 120)
    print("TRAJECTORY VECTOR AUDIT COMPLETE")
    print("=" * 120)


if __name__ == "__main__":
    main()
