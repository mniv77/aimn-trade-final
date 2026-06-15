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

    prompt = (
        f"You are reviewing a candlestick chart for {symbol}. "
        f"A trading system wants to enter {direction} based on an extreme "
        f"RSI reading. Has the price ACTUALLY reversed and shown at least "
        f"2 candles of follow-through in the {direction} direction, or is "
        f"this still mid-move / already extended? "
        f'Respond ONLY with JSON, no other text: '
        f'{{"verdict": "CONFIRMED|NOT_CONFIRMED|UNCLEAR", "reason": "brief explanation"}}'
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
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()

        result = json.loads(text)
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
