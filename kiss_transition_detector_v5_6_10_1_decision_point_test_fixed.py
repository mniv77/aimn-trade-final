"""KISS V5.6.10.1 — safe-output wrapper for V5.6.10.

RESEARCH ONLY. No orders, DB writes, engine changes, RSI, or ML.

V5.6.10 analysis is already correct. Its representative printer can receive
an acted policy with one or more missing display-only values when future data
is unavailable. This wrapper changes ONLY those display values so the existing
V5.6.10 analysis and statistics remain untouched.
"""
from __future__ import annotations

import kiss_transition_detector_v5_6_10_decision_point_test as v5610


class _DisplayNA:
    """Display-only value that safely accepts numeric format specifications."""

    def __format__(self, spec: str) -> str:
        return "N/A"

    def __str__(self) -> str:
        return "N/A"


_DISPLAY_NA = _DisplayNA()


def safe_summarize(records, total, skipped):
    """Make representative output safe without changing analysis statistics."""
    for rec in records:
        for episode in rec.get("result", {}).get("episodes", []):
            for result in episode.get("policies", {}).values():
                if not result.get("acted"):
                    continue

                # The original printer formats these with numeric format codes.
                # If future coverage is missing, preserve the missing value as
                # N/A rather than allowing the display code to crash.
                if result.get("minutes_to_t0") is None:
                    result["minutes_to_t0"] = _DISPLAY_NA
                if result.get("ret60") is None:
                    result["ret60"] = _DISPLAY_NA
                if result.get("time") is None:
                    result["time"] = _DISPLAY_NA

    return v5610._ORIGINAL_SUMMARIZE(records, total, skipped)


v5610._ORIGINAL_SUMMARIZE = v5610.summarize
v5610.summarize = safe_summarize

if __name__ == "__main__":
    v5610.main()
