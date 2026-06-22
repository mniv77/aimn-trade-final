"""
ai_vision_check.py
Sends a chart image to Claude's vision API and returns a structured
judgment on whether a price reversal is confirmed.

Part of the AI Vision Confirmation initiative (see Doc 3).
Standalone module - safe to test without touching the live engine.
"""

import base64
import json
import os
import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"


def check_reversal(image_path, symbol, direction):
    """
    Ask Claude to look at a chart image and judge whether a reversal
    in `direction` is confirmed (2+ candles of follow-through) or not.

    Returns a dict: {"verdict": "CONFIRMED"|"NOT_CONFIRMED"|"UNCLEAR", "reason": "..."}
    On error, returns {"verdict": "ERROR", "reason": "..."}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"verdict": "ERROR", "reason": "ANTHROPIC_API_KEY not set"}

    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return {"verdict": "ERROR", "reason": f"Could not read image: {e}"}

    direction_word = "bottom" if direction == "LONG" else "top"
    entry_word = "LONG (buy)" if direction == "LONG" else "SHORT (sell)"
    opposite = "SHORT" if direction == "LONG" else "LONG"
    prompt = (
        f"You are a strict trading judge analyzing a {symbol} candlestick chart. "
        f"Your ONLY job: decide if {direction} entry is valid RIGHT NOW. "
        f"\n\n"
        f"STEP 1 - DETERMINE OVERALL TREND (MANDATORY FIRST STEP): "
        f"Look at the entire chart left to right. Is the general price direction UP, DOWN, or SIDEWAYS? "
        f"UP = series of higher highs and higher lows. "
        f"DOWN = series of lower highs and lower lows. "
        f"SIDEWAYS = price oscillating in a range with no clear direction. "
        f"\n\n"
        f"STEP 2 - APPLY TREND FILTER (NO EXCEPTIONS): "
        f"If trend is DOWN: LONG = NOT_CONFIRMED immediately. Only SHORT can be CONFIRMED. "
        f"If trend is UP: SHORT = NOT_CONFIRMED immediately. Only LONG can be CONFIRMED. "
        f"If trend is SIDEWAYS: both directions = UNCLEAR. "
        f"IT IS IMPOSSIBLE for both LONG and SHORT to be CONFIRMED. Never do this. "
        f"\n\n"
        f"STEP 3 - CHECK REQUEST ({direction}): "
        f"Does the trend support {direction}? "
        f"If NO -> answer NOT_CONFIRMED immediately without looking further. "
        f"If YES -> look for V-pattern: "
        f"LONG: sharp drop + volume spike at bottom + 2+ green recovery candles. "
        f"SHORT: sharp rally + volume spike at top + 2+ red declining candles. "
        f"\n\n"
        f"VERDICT: "
        f"CONFIRMED = trend supports {direction} AND clear V-pattern exists. "
        f"NOT_CONFIRMED = trend does NOT support {direction} OR no clear V-pattern. "
        f"UNCLEAR = trend is sideways only. "
        f"\n\n"
        f"State the trend direction in your reason FIRST, then explain the pattern. "
        f'Respond ONLY with JSON: '
        f'{{"verdict": "CONFIRMED|NOT_CONFIRMED|UNCLEAR", "reason": "TREND=UP/DOWN/SIDEWAYS. Pattern: ..."}}'
    )
    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": MODEL,
                "max_tokens": 300,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": img_b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        text = data["content"][0]["text"].strip()

        # Strip markdown code fences if present
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:].strip()
        text = text.strip()
        # Extract just the JSON object if embedded in text
        if "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            if end > start:
                text = text[start:end]

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # Try to extract verdict directly from malformed JSON
            import re
            verdict_match = re.search(r'"verdict"\s*:\s*"([^"]+)"', text)
            reason_match  = re.search(r'"reason"\s*:\s*"([^"]+)"', text)
            if verdict_match:
                return {
                    "verdict": verdict_match.group(1),
                    "reason": reason_match.group(1) if reason_match else "Partial parse"
                }
            return {"verdict": "ERROR", "reason": f"JSON parse failed: {text[:50]}"}
        if "verdict" not in result:
            return {"verdict": "ERROR", "reason": f"Unexpected response: {text}"}
        return result

    except requests.exceptions.RequestException as e:
        return {"verdict": "ERROR", "reason": f"API request failed: {e}"}
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return {"verdict": "ERROR", "reason": f"Could not parse response: {e}"}


if __name__ == "__main__":
    import sys

    image_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/chart_test.png"
    symbol = sys.argv[2] if len(sys.argv) > 2 else "BTC/USD"
    direction = sys.argv[3] if len(sys.argv) > 3 else "LONG"

    result = check_reversal(image_path, symbol, direction)
    print(json.dumps(result, indent=2))
