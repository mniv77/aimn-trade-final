"""KISS V5.6.10.1 — safe-output wrapper for V5.6.10.

RESEARCH ONLY. No orders, DB writes, engine changes, RSI, or ML.

V5.6.10 completed its analysis successfully, but its representative printer
crashed when a policy record was internally inconsistent: acted=True while
time=None. This wrapper sanitizes only that impossible output state and then
runs the original V5.6.10 analysis unchanged.
"""
from __future__ import annotations

import kiss_transition_detector_v5_6_10_decision_point_test as v5610


def safe_summarize(records, total, skipped):
    """Remove impossible acted=True/time=None records before printing."""
    for rec in records:
        for episode in rec.get("result", {}).get("episodes", []):
            for result in episode.get("policies", {}).values():
                if result.get("acted") and result.get("time") is None:
                    result["acted"] = False
                    result["status"] = "NO_EXIT"
                    result["idx"] = None
                    result["ret60"] = None
                    result["minutes_to_t0"] = None
    return v5610._ORIGINAL_SUMMARIZE(records, total, skipped)


v5610._ORIGINAL_SUMMARIZE = v5610.summarize
v5610.summarize = safe_summarize

if __name__ == "__main__":
    v5610.main()
