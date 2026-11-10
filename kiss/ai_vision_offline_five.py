"""Run zero-cost OHLC trend baseline on the same five NVDA pilot cutoffs."""
from __future__ import annotations
import json
from pathlib import Path
from kiss.ai_vision_independent import load_candles
from kiss.ai_vision_major_trend_pilot import select_indices
from kiss.ai_vision_offline_structure import replay


def main():
    rows = load_candles("kiss/visual_research/aimn_nvda_candles.json")
    indices = select_indices(len(rows), warmup=500, samples=5)
    result = replay(rows, indices)
    target = Path("kiss/results/ai_vision/offline_major_trend_five.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for item in result["assessments"]:
        print(f'{item["last_visible_candle_unix"]}: '
              f'major={item["major_trend"]}, local={item["local_trend"]}, '
              f'interpretation={item["local_transition_type"]}')
    print("Offline baseline only. No AI API calls or trades.")


if __name__ == "__main__":
    main()
