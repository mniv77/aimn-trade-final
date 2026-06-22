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
    prompt = (
        f"You are an expert trader analyzing a {symbol} candlestick chart. "
        f"STEP 1: Determine the OVERALL TREND from the chart (last 20-40 candles). Is it UP, DOWN, or SIDEWAYS? "
        f"STEP 2: Identify the most recent V-pattern (V-bottom or V-top). "
        f"STEP 3: Only CONFIRM entries that align WITH the overall trend. "
        f"If trend is UP: confirm LONG entries only. V-tops in uptrend = temporary pullbacks, NOT shorts. "
        f"If trend is DOWN: confirm SHORT entries only. V-bottoms in downtrend = temporary bounces, NOT longs. "
        f"If trend is SIDEWAYS or UNCLEAR: say UNCLEAR for both directions. "
        f"Never confirm BOTH directions — they are mutually exclusive. "
        f"Be objective — do NOT find reasons to confirm {direction} if the trend disagrees. "
        f"PATTERN RULES — study ALL of these: "
        f"V-LONG: Sharp decline, big GREEN volume spike at bottom, 2+ green candles recovering. "
        f"U-LONG: Gradual curved decline, volume spike at bottom, steady recovery. Same as V but slower. "
        f"V-SHORT: Sharp rally, big RED volume spike at top, 2+ red candles declining. "
        f"U-SHORT: Gradual curved rally, red volume spike at top, steady decline. "
        f"W-PATTERN: Double bottom - wait for breakout above middle bounce before LONG. "
        f"M-PATTERN: Double top - wait for breakdown below middle dip before SHORT. "
        f"FAILED BREAKOUT SHORT: Long UPPER wick + red volume = price rejected at high = SHORT signal. "
        f"FAILED BREAKDOWN LONG: Long LOWER wick + green volume = price rejected at low = LONG signal. "
        f"VOLUME IS THE LIE DETECTOR: High volume move = trust it. Low volume move = doubt it. "
        f"LOW VOLUME DRIFT: Price drifting on low volume = weak move, wait for volume confirmation. "
        f"WICK ANALYSIS: Upper wick = buyers tried and failed. Lower wick = sellers tried and failed. "
        f"CANDLE BODY: The CLOSE price matters most. Body direction shows who WON. "
        f"SEQUENCE THINKING: After V-bottom recovery = watch for next SHORT. After V-top decline = watch for next LONG. "
        f"CRYPTO CORRELATION: BTC/ETH/SOL often move together. Check if pattern matches market direction. "
        f"TOO LATE: If recovery already happened and price extended from bottom = do NOT enter LONG. "
        f"NOISE: Small choppy candles alternating red/green = DO NOT ENTER. "
        f"VOLUME SPIKE DELAY: Volume spike is WARNING not immediate trigger — move comes 5-10 candles later. "
        f"RED spike then sideways drift on low volume = DISTRIBUTION = SHORT coming. "
        f"GREEN spike then sideways drift on low volume = ACCUMULATION = LONG coming. "
        f"Wait for breakout AFTER the drift phase to confirm entry. "
        f"RSI/MACD are just alerts — YOU make the final decision based on chart structure. "
        f"CRITICAL ANALYSIS RULES: "
        f"1. Find the MOST RECENT V-bottom or V-top anywhere on the chart (not just right edge). "
        f"2. If a V-bottom formed recently (last 20-40 candles) AND price is now recovering = LONG CONFIRMED. "
        f"3. If a V-top formed recently (last 20-40 candles) AND price is now declining = SHORT CONFIRMED. "
        f"4. The V needs: sharp move + volume spike + 2+ candles in new direction. "
        f"5. If price is still recovering from recent V-bottom = CONFIRMED LONG (not too late if within 20 candles). "
        f"6. RIGHT EDGE noise/chop after a clear V = still CONFIRMED if the V was recent and strong. "
        f"7. Only say NOT_CONFIRMED if NO clear V pattern exists anywhere in the recent chart. "
        f"Is there a recent {direction_word} pattern supporting a {entry_word} entry? "
        f'Respond ONLY with JSON: '
        f'{{"verdict": "CONFIRMED|NOT_CONFIRMED|UNCLEAR", "reason": "describe V pattern structure"}}'
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
