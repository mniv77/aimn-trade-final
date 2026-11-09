"""Independent, candle-only AI Vision research runner. No broker or EXP53 imports.

Run locally with OPENAI_API_KEY configured. Each assessment uses only candles
through the current close. Signals fill at the NEXT candle open. Decisions are
cached by exact packet hash, model and prompt version.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import urllib.request

DECISIONS = {"WAIT", "WATCH LONG", "WATCH SHORT", "ENTER LONG", "ENTER SHORT", "EXIT LONG", "EXIT SHORT"}
PROMPT_VERSION = "aimn-blind-v2-multiscale-major-local"
SYSTEM = """You are an independent historical OHLC research assessor. Only use supplied
visible candles. Never use future prices, indicators, EXP53, KISS, or outside data.
The research direction is a focus, not a forced signal. Explicitly distinguish
major trend from local trend using the historical big-picture and close-up
views. A local rally within a major SHORT trend is not automatically a LONG
reversal. State evidence for a major reversal before countertrend entry.
Avoid countertrend entries without compelling
visible structure. Maintain position consistency. Respond with ONLY JSON keys:
symbol, research_direction, last_visible_candle_unix, decision, confidence,
reason, notes. Allowed decisions: WAIT, WATCH LONG, WATCH SHORT, ENTER LONG,
ENTER SHORT, EXIT LONG, EXIT SHORT. Confidence: Low, Moderate, High.
Never claim live orders. No live orders."""

def timestamp(row):
    value = row.get("timestamp", row.get("utc"))
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        value = value.replace(" UTC", "").replace("Z", "").replace("T", " ")
        parsed = dt.datetime.fromisoformat(value)
        return int((parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)).timestamp())
    raise ValueError("Unsupported timestamp")

def load_candles(path):
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(obj, dict):
        obj = obj.get("candles", obj.get("data"))
    if not isinstance(obj, list):
        raise ValueError("Expected candle array")
    rows = []
    for r in obj:
        item = {"unix": timestamp(r)}
        for k in ("open", "high", "low", "close"):
            item[k] = float(r[k])
        if not (item["low"] <= min(item["open"], item["close"]) <= max(item["open"], item["close"]) <= item["high"]):
            raise ValueError("Invalid OHLC")
        rows.append(item)
    if any(a["unix"] >= b["unix"] for a,b in zip(rows, rows[1:])):
        raise ValueError("Candles must be strictly chronological")
    return rows

def packet(rows, index, symbol, direction, position, window):
    visible = rows[max(0, index-window+1):index+1]
    return {"symbol": symbol, "timeframe": "5m", "research_direction": direction,
            "last_visible_candle_unix": rows[index]["unix"],
            "visible_count": index+1, "paper_position": position,
            "visible_ohlc": visible}

def model_decision(data, model, cache_dir):
    request_data = {"model": model, "prompt_version": PROMPT_VERSION, "packet": data}
    digest = hashlib.sha256(json.dumps(request_data, sort_keys=True).encode()).hexdigest()
    target = Path(cache_dir) / (digest + ".json")
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY required; no fabricated AI decisions")
    body = json.dumps({"model": model, "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(data)}],
        "temperature": 0, "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions",
        data=body, headers={"Authorization": "Bearer " + key,
                            "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = json.load(response)
    result = json.loads(raw["choices"][0]["message"]["content"])
    required = {"symbol", "research_direction", "last_visible_candle_unix",
                "decision", "confidence", "reason", "notes"}
    if set(result) != required or result["decision"] not in DECISIONS:
        raise ValueError("Invalid AI decision schema")
    if result["symbol"] != data["symbol"] or result["research_direction"] != data["research_direction"] or result["last_visible_candle_unix"] != data["last_visible_candle_unix"]:
        raise ValueError("AI response mismatched packet")
    if result["confidence"] not in {"Low", "Moderate", "High"}:
        raise ValueError("Invalid confidence")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

def run(rows, assessor, symbol="NVDA", direction="SHORT", window=100,
        step=5, warmup=100, commission_pct=0.10):
    if direction not in {"SHORT", "LONG"}:
        raise ValueError("Choose LONG or SHORT")
    if step < 1 or window < 1 or warmup < 1:
        raise ValueError("Invalid sampling")
    position = None
    pending = None
    decisions, trades = [], []
    for i, candle in enumerate(rows):
        # Fill prior candle's signal at the next available open.
        if pending is not None:
            signal = pending
            pending = None
            price = candle["open"]
            if signal["decision"] == "ENTER " + direction and position is None:
                position = {"side": direction, "entry_unix": candle["unix"],
                            "entry_price": price, "signal_unix": signal["last_visible_candle_unix"]}
            elif signal["decision"] == "EXIT " + direction and position is not None:
                gross = (price / position["entry_price"] - 1) * 100
                if direction == "SHORT":
                    gross = -gross
                trades.append({**position, "exit_unix": candle["unix"], "exit_price": price,
                               "exit_signal_unix": signal["last_visible_candle_unix"],
                               "gross_pnl_pct": round(gross, 6),
                               "net_pnl_pct": round(gross - 2 * commission_pct, 6)})
                position = None
        if i < warmup-1 or i == len(rows)-1 or (i-(warmup-1)) % step:
            continue
        if max_assessments is not None and len(decisions) >= max_assessments:
            break
        data = packet(rows, i, symbol, direction, position, window)
        result = assessor(data)
        if result["decision"] not in DECISIONS:
            raise ValueError("Invalid decision")
        decisions.append(result)
        if (result["decision"] == "ENTER " + direction and position is None) or (
            result["decision"] == "EXIT " + direction and position is not None):
            pending = result
    return {"symbol": symbol, "direction": direction, "timeframe": "5m",
            "research_only": True, "decision_count": len(decisions),
            "decisions": decisions, "trades": trades, "open_position": position,
            "unfilled_final_signal": pending,
            "realized_gross_pnl_pct": round(sum(t["gross_pnl_pct"] for t in trades), 6),
            "realized_net_pnl_pct": round(sum(t["net_pnl_pct"] for t in trades), 6),
            "commission_pct_per_side": commission_pct,
            "execution": "next_available_candle_open",
            "note": "Summed per-trade percent returns, not compounded portfolio equity. No live orders."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candles", default="kiss/visual_research/aimn_nvda_candles.json")
    parser.add_argument("--output", default="kiss/results/ai_vision/nvda_short_v1.json")
    parser.add_argument("--cache", default="kiss/results/ai_vision/cache")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--direction", choices=["SHORT", "LONG"], default="SHORT")
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--window", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--commission-pct", type=float, default=0.10)
    parser.add_argument("--max-assessments", type=int, default=None,
                        help="Limit API calls for initial smoke tests")
    args = parser.parse_args()
    candles = load_candles(args.candles)
    result = run(candles, lambda p: model_decision(p, args.model, args.cache),
                 direction=args.direction, step=args.step, window=args.window,
                 warmup=args.warmup, commission_pct=args.commission_pct,
                 max_assessments=args.max_assessments)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Saved {result['decision_count']} assessments and {len(result['trades'])} trades to {output}")

if __name__ == "__main__":
    main()
