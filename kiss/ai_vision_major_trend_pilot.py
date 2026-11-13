"""Export a deterministic, trade-free NVDA major-trend research pilot.

Select five spaced historical cutoffs. Actual model calls are opt-in only;
offline --dry-run exports candle contexts without generating AI judgments.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from kiss.ai_vision_independent import load_candles, packet
from kiss.ai_vision_major_trend_research import api_trend_assessor, pilot


def select_indices(count, warmup=500, samples=5):
    if count <= warmup or samples < 1:
        raise ValueError("Not enough historical candles")
    last = count - 2  # always reserve at least one later candle
    first = warmup - 1
    if last < first or samples > last - first + 1:
        raise ValueError("Insufficient sample cutoffs")
    if samples == 1:
        return [first]
    return [first + (last - first) * i // (samples - 1)
            for i in range(samples)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candles", default="kiss/visual_research/aimn_nvda_candles.json")
    parser.add_argument("--output", default="kiss/results/ai_vision/major_trend_pilot.json")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true",
                        help="Export visible OHLC contexts only; no API calls")
    args = parser.parse_args()
    rows = load_candles(args.candles)
    indices = select_indices(len(rows), args.warmup, args.samples)
    if args.dry_run:
        result = {"research_only": True, "objective": "major_trend_recognition",
                  "dry_run": True, "symbol": "NVDA", "timeframe": "5m",
                  "cutoffs": [packet(rows, i, "NVDA", "SHORT", None, 100)
                              for i in indices],
                  "note": "Historical packets only; no model decisions or trades."}
    else:
        result = pilot(rows, lambda p: api_trend_assessor(p, model=args.model),
                       indices, symbol="NVDA", window=100)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Saved {len(indices)} historical cutoffs to {output}. "
          f"Dry run: {args.dry_run}")


if __name__ == "__main__":
    main()
