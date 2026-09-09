"""KISS V5.6.10.1 — safe-output wrapper for V5.6.10.

RESEARCH ONLY. No orders, DB writes, engine changes, RSI, or ML.

V5.6.10 completed its analysis successfully, but its representative printer
crashed when a policy record was internally inconsistent: acted=True while
time=None. Keep the analysis unchanged and sanitize only the display value.
"""
from __future__ import annotations

import kiss_transition_detector_v5_6_10_decision_point_test as v5610


def safe_summarize(records, total, skipped):
    """Make representative output safe without changing analysis statistics."""
    for rec in records:
        for episode in rec.get("result", {}).get("episodes", []):
            for result in episode.get("policies", {}).values():
                if result.get("acted") and result.get("time") is None:
                    # Preserve acted/status/score data. Only replace the value
                    # that the original printer formats as a datetime.
                    result["time"] = "N/A"
    return v5610._ORIGINAL_SUMMARIZE(records, total, skipped)


v5610._ORIGINAL_SUMMARIZE = v5610.summarize
v5610.summarize = safe_summarize

if __name__ == "__main__":
    v5610.main()
