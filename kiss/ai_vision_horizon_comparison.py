"""Compare causal major-trend horizons on identical NVDA historical cutoffs.

Offline deterministic OHLC baseline; not a trained AI or a trading system.
"""
from __future__ import annotations
import json
from pathlib import Path
from kiss.ai_vision_independent import load_candles
from kiss.ai_vision_major_trend_pilot import select_indices
from kiss.ai_vision_offline_structure import assess_at

HORIZONS = (40, 70, 100, 150, 200)
LOCAL_SPAN = 10


def compare(rows, indices, horizons=HORIZONS, local_span=LOCAL_SPAN):
    cases = []
    for index in indices:
        results = []
        for span in horizons:
            result = assess_at(rows, index, major_span=span, local_span=local_span)
            results.append({"major_span": span,
                            "major_trend": result["major_trend"],
                            "local_trend": result["local_trend"],
                            "interpretation": result["local_transition_type"],
                            "confidence": result["major_trend_confidence"],
                            "evidence": result["major_trend_evidence"]})
        labels = [x["major_trend"] for x in results]
        cases.append({"index": index, "cutoff_unix": rows[index]["unix"],
                      "close": rows[index]["close"], "horizons": results,
                      "all_agree": len(set(labels)) == 1,
                      "disagreement": len(set(labels)) > 1})
    return {"research_only": True, "method": "deterministic_ohlc_multi_horizon_v1",
            "symbol": "NVDA", "timeframe": "5m", "local_span": local_span,
            "major_spans": list(horizons), "cases": cases,
            "disagreement_count": sum(x["disagreement"] for x in cases),
            "note": "Disagreement is not error. No hindsight labels, AI API calls, or trades."}


def main():
    rows = load_candles("kiss/visual_research/aimn_nvda_candles.json")
    indices = select_indices(len(rows), warmup=500, samples=5)
    result = compare(rows, indices)
    target = Path("kiss/results/ai_vision/major_horizon_comparison.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for case in result["cases"]:
        print(f'{case["cutoff_unix"]}: ' +
              ", ".join(f'{x["major_span"]}={x["major_trend"]}' for x in case["horizons"]) +
              f'; disagreement={case["disagreement"]}')
    print(f'Disagreement in {result["disagreement_count"]} of {len(result["cases"])} cases.')


if __name__ == "__main__":
    main()
