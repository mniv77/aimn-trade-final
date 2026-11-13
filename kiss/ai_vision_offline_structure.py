"""Zero-API-cost, causal major/local price-structure baseline for AIMn research.

This is a deterministic OHLC baseline, NOT a vision-language AI model.
No broker imports, Supertrend, RSI, future candles, or trade decisions.
"""
from __future__ import annotations

from kiss.ai_vision_independent import packet


def _structure(bars, span):
    """Compare early and late price ranges using only visible candles."""
    if len(bars) < span * 2:
        return {"trend": "UNCERTAIN", "strength": 0.0,
                "evidence": "Insufficient historical bars"}
    recent = bars[-span:]
    previous = bars[-2 * span:-span]
    previous_high = max(b["high"] for b in previous)
    previous_low = min(b["low"] for b in previous)
    recent_high = max(b["high"] for b in recent)
    recent_low = min(b["low"] for b in recent)
    reference = max(abs(previous_high - previous_low), 1e-9)
    high_delta = (recent_high - previous_high) / reference
    low_delta = (recent_low - previous_low) / reference
    if high_delta > 0 and low_delta > 0:
        trend = "LONG"
    elif high_delta < 0 and low_delta < 0:
        trend = "SHORT"
    else:
        trend = "UNCERTAIN"
    strength = min(1.0, (abs(high_delta) + abs(low_delta)) / 2)
    return {"trend": trend, "strength": round(strength, 4),
            "evidence": (f"Previous high/low {previous_high:.4f}/{previous_low:.4f}; "
                         f"recent high/low {recent_high:.4f}/{recent_low:.4f}")}


def assess_at(rows, index, symbol="NVDA", major_span=100, local_span=10):
    """Assess a completed candle, preserving the exact historical cutoff."""
    if major_span < 2 or local_span < 2 or local_span >= major_span:
        raise ValueError("Require 2 <= local_span < major_span")
    data = packet(rows, index, symbol, "SHORT", None, max(500, 2 * major_span))
    bars = data["visible_ohlc"]
    major = _structure(bars, major_span)
    local = _structure(bars, local_span)
    mt, lt = major["trend"], local["trend"]
    if mt == "UNCERTAIN" or lt == "UNCERTAIN":
        interpretation = "UNCERTAIN"
    elif mt == lt:
        interpretation = "ALIGNED"
    else:
        interpretation = "COUNTERTREND_RECOVERY"
    return {
        "symbol": symbol, "last_visible_candle_unix": data["last_visible_candle_unix"],
        "major_trend": mt, "local_trend": lt,
        "local_transition_type": interpretation,
        "major_trend_confidence": "Low" if mt == "UNCERTAIN" else (
            "High" if major["strength"] >= 0.5 else "Moderate"),
        "major_trend_evidence": major["evidence"],
        "local_trend_evidence": local["evidence"],
        "major_reversal_evidence": "Not established by this two-window baseline",
        "method": "deterministic_ohlc_structure_v1",
        "research_only": True,
    }


def replay(rows, indices, symbol="NVDA", major_span=100, local_span=10):
    return {"research_only": True, "method": "deterministic_ohlc_structure_v1",
            "symbol": symbol, "timeframe": "5m",
            "assessments": [assess_at(rows, i, symbol, major_span, local_span)
                            for i in indices],
            "note": "Baseline structure labels, not model predictions or trade signals."}
