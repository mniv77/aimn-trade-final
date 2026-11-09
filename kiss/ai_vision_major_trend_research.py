"""Blind major/local trend recognition research, independent of trading signals.

This module intentionally does not import EXP53 or the trading engine.
The assessor is injected so tests never require an API key.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

from kiss.ai_vision_independent import packet

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

TREND_PROMPT_VERSION = "aimn-major-trend-blind-v1"
TREND_SYSTEM = """You are a blind OHLC major-trend research assessor.
Only analyze historical candles supplied to you; never assume later candles.
Distinguish the older multi-scale price structure from recent local movement.
A rising local move inside a major SHORT trend is not proof of a major LONG
reversal. A falling local move inside a major LONG trend is not proof of a
major SHORT reversal. UNCERTAIN is appropriate when structure is inconclusive.
Describe observed evidence, not hindsight. Do not propose trades or entries.
Return only JSON with keys: last_visible_candle_unix, major_trend,
local_trend, local_transition_type, major_trend_confidence,
major_trend_evidence, major_reversal_evidence.
major_trend/local_trend: LONG, SHORT, UNCERTAIN.
local_transition_type: ALIGNED, COUNTERTREND_RECOVERY,
POSSIBLE_MAJOR_REVERSAL, UNCERTAIN.
major_trend_confidence: Low, Moderate, High.
Every evidence field must be a nonempty explanation grounded in visible OHLC.
No indicator values, EXP53 outputs, future candles, or trading decisions."""


def api_trend_assessor(data, model="gpt-4o",
                       cache_dir="kiss/results/ai_vision/trend_cache"):
    """Explicitly invoked, billable model assessor; never used by offline tests."""
    request_data = {"model": model, "version": TREND_PROMPT_VERSION,
                    "packet": data}
    digest = hashlib.sha256(json.dumps(request_data, sort_keys=True).encode()).hexdigest()
    target = Path(cache_dir) / (digest + ".json")
    if target.exists():
        return validate_trend(json.loads(target.read_text(encoding="utf-8")), data)
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY required; no simulated model results")
    body = json.dumps({"model": model, "messages": [
        {"role": "system", "content": TREND_SYSTEM},
        {"role": "user", "content": json.dumps(data)}],
        "temperature": 0, "response_format": {"type": "json_object"}}).encode()
    request = urllib.request.Request("https://api.openai.com/v1/chat/completions",
        data=body, headers={"Authorization": "Bearer " + key,
                            "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = json.load(response)
    result = json.loads(raw["choices"][0]["message"]["content"])
    validate_trend(result, data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
