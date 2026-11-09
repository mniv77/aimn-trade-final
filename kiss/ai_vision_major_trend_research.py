"""Blind major/local trend recognition research, independent of trading signals.

This module intentionally does not import EXP53 or the trading engine.
The assessor is injected so tests never require an API key.
"""
from __future__ import annotations

import json
from pathlib import Path

from kiss.ai_vision_independent import packet, model_decision

TRENDS = {"LONG", "SHORT", "UNCERTAIN"}
LOCAL_TYPES = {"ALIGNED", "COUNTERTREND_RECOVERY", "POSSIBLE_MAJOR_REVERSAL", "UNCERTAIN"}


def validate_trend(result, historical_packet):
    required = {"major_trend", "local_trend", "local_transition_type",
                "major_trend_confidence", "major_trend_evidence",
                "major_reversal_evidence"}
    missing = required - result.keys()
    if missing:
        raise ValueError("Missing major-trend fields: " + ", ".join(sorted(missing)))
    if result["major_trend"] not in TRENDS or result["local_trend"] not in TRENDS:
        raise ValueError("Invalid major/local trend")
    if result["local_transition_type"] not in LOCAL_TYPES:
        raise ValueError("Invalid local transition type")
    if result["major_trend_confidence"] not in {"Low", "Moderate", "High"}:
        raise ValueError("Invalid major-trend confidence")
    for field in ("major_trend_evidence", "major_reversal_evidence"):
        if not isinstance(result[field], str) or not result[field].strip():
            raise ValueError("Missing trend evidence: " + field)
    if (result.get("last_visible_candle_unix") !=
            historical_packet["last_visible_candle_unix"]):
        raise ValueError("Trend assessment mismatched historical cutoff")
    return result


def assess_at(rows, index, assessor, symbol="NVDA", window=100):
    """One causal, trade-free trend assessment at a completed 5m candle."""
    data = packet(rows, index, symbol, "SHORT", None, window)
    result = assessor(data)
    return validate_trend(result, data)


def pilot(rows, assessor, indices, symbol="NVDA", window=100):
    """Evaluate explicitly selected historical cutoffs; no fills or P&L."""
    decisions = [assess_at(rows, i, assessor, symbol, window) for i in indices]
    return {"research_only": True, "objective": "major_trend_recognition",
            "symbol": symbol, "timeframe": "5m",
            "assessments": decisions, "assessment_count": len(decisions),
            "note": "Trend hypotheses only; no trades, no performance claim."}
