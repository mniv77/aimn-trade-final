"""
AIMn / KISS V13.17
NVDA LONG TRAJECTORY CASE DIAGNOSTIC

RESEARCH ONLY
NO ORDERS
NO PRODUCTION ENGINE CHANGES
NO AI TRAINING
NO THRESHOLD PROMOTION

Purpose:
Print every NVDA LONG trajectory case exactly as reconstructed
by the V13.17 case-aware research builder.

This diagnostic does not modify the research builder.
"""

from kiss.kiss_transition_detector_v5_6_12_13_17_case_aware_validation import (
    build_v1317_research_paths,
)


def main():
    print("=" * 120)
    print("AIMn / KISS V13.17 NVDA LONG TRAJECTORY CASE DIAGNOSTIC")
    print("=" * 120)
    print()
    print("RESEARCH ONLY")
    print()

    paths = build_v1317_research_paths()

    nvda_long = [
        p for p in paths
        if p.symbol == "NVDA" and p.direction == "LONG"
    ]

    print(f"NVDA LONG CASES FOUND = {len(nvda_long)}")
    print()

    for case_no, path in enumerate(nvda_long, start=1):

        print("-" * 120)
        print(f"NVDA LONG CASE #{case_no}")
        print(f"symbol        = {path.symbol}")
        print(f"direction     = {path.direction}")
        print(f"opposite_time = {path.opposite_time}")
        print(f"official_time = {path.official_time}")
        print(f"warning_lead  = {path.warning_lead}")
        print()

        print("TRAJECTORY:")
        sequence = []

        for point in path.points:
            sequence.append(
                f"+{point.minutes}={point.state}"
            )

        print(" -> ".join(sequence))
        print()

        print("FULL STATEPOINTS:")
        print(
            "MIN".ljust(7),
            "STATE".ljust(22),
            "RETURN".rjust(12),
            "FAV".rjust(10),
            "ADV".rjust(10),
            "CONADV".rjust(10),
            "MAE".rjust(12),
            "MFE".rjust(12),
        )

        for point in path.points:
            print(
                str(point.minutes).rjust(7),
                str(point.state).ljust(22),
                f"{point.return_pct:12.6f}",
                f"{point.favorable_ratio:10.6f}",
                f"{point.adverse_ratio:10.6f}",
                f"{point.consecutive_adverse:10.0f}",
                f"{point.mae_pct:12.6f}",
                f"{point.mfe_pct:12.6f}",
            )

        print()

    print("=" * 120)
    print("END NVDA LONG DIAGNOSTIC")
    print("=" * 120)


if __name__ == "__main__":
    main()
