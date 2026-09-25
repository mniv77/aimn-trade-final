"""
AI Vision BLIND scoring runner.

This is the first real AI evaluation layer for KISS transition recognition.

Rules:
  1. The model receives ONLY features known at the transition.
  2. future_outcome is never included in the model request.
  3. The actual label is attached to the result only AFTER the model returns.
  4. No KISS engine changes, no trading, and no DB writes.
  5. Results are written locally to a JSONL file so runs can be resumed.

Environment:
  OPENAI_API_KEY   required
  OPENAI_MODEL     optional; default gpt-5.6-luna

Usage:
  python kiss_ai_blind_scoring_runner.py
  python kiss_ai_blind_scoring_runner.py --limit 20
  python kiss_ai_blind_scoring_runner.py --fresh
  python kiss_ai_blind_scoring_runner.py --model gpt-5.6-luna

The runner uses the OpenAI Responses API with Structured Outputs so the
prediction format is machine-validated rather than parsed from free text.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI

from kiss_ai_transition_research import (
    SYMBOLS,
    TIMEFRAME,
    EXECUTION_TIMEFRAME,
    LIMIT,
    _db_rows,
    build_states,
    transition_events,
    make_case,
)

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")
RESULTS_FILE = Path("kiss_ai_blind_results.jsonl")

SYSTEM_INSTRUCTIONS = """
You are the transition-recognition component of an autonomous trading research
system. Your job is to classify ONE market trend transition using only the
information available at that transition.

Classify:
- REAL: evidence supports a meaningful continuation/move in the new direction.
- WEAK: the transition is plausible but evidence is mixed or insufficient.
- FALSE: evidence suggests the transition is likely to fail or reverse.

Important:
- Do not assume every transition is tradable.
- Do not use future information.
- Do not invent missing data.
- Consider the transition type (for example SHORT->LONG versus FLAT->LONG),
  price location, RSI context, MA relationship, prior state duration, churn,
  recent price movement, and V-shape only insofar as the supplied evidence
  supports it.
- Give a confidence from 0 to 100 representing confidence in your CLASS.
- The reason must be short and evidence-based.
""".strip()

SCHEMA = {
    "type": "object",
    "properties": {
        "prediction": {"type": "string", "enum": ["REAL", "WEAK", "FALSE"]},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
    },
    "required": ["prediction", "confidence", "reason"],
    "additionalProperties": False,
}


def load_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for symbol in SYMBOLS:
        trend = _db_rows(symbol, TIMEFRAME, LIMIT)
        execution = _db_rows(symbol, EXECUTION_TIMEFRAME, LIMIT)
        if len(trend) < 22 or len(execution) < 48:
            continue
        states = build_states(trend)
        for event in transition_events(trend, states):
            case = make_case(symbol, event, execution)
            if case:
                cases.append(case)
    cases.sort(key=lambda c: (c["transition_time"], c["symbol"], c["direction"]))
    return cases


def case_id(case: Dict[str, Any]) -> str:
    return f"{case['symbol']}|{case['transition_time']}|{case['direction']}"


def load_existing() -> Dict[str, Dict[str, Any]]:
    done: Dict[str, Dict[str, Any]] = {}
    if not RESULTS_FILE.exists():
        return done
    with RESULTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if row.get("case_id"):
                    done[row["case_id"]] = row
            except json.JSONDecodeError:
                continue
    return done


def model_input(case: Dict[str, Any]) -> str:
    # Deliberately construct the payload from the feature-only section.
    # future_outcome is not referenced or serialized here.
    payload = {
        "symbol": case["symbol"],
        "timeframe": case["timeframe"],
        "execution_timeframe": case["execution_timeframe"],
        "transition_time": case["transition_time"],
        "direction": case["direction"],
        "features": case["features_available_at_transition"],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def call_ai(client: OpenAI, model: str, case: Dict[str, Any]) -> Dict[str, Any]:
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=model_input(case),
        text={
            "format": {
                "type": "json_schema",
                "name": "transition_classification",
                "strict": True,
                "schema": SCHEMA,
            },
            "verbosity": "low",
        },
        reasoning={"effort": "low"},
        store=False,
        temperature=0.0,
    )
    text = response.output_text
    result = json.loads(text)
    return {
        "prediction": result["prediction"],
        "confidence": int(result["confidence"]),
        "reason": result["reason"],
        "response_id": getattr(response, "id", None),
        "model": model,
    }


def score(rows: List[Dict[str, Any]]) -> None:
    usable = [r for r in rows if r.get("ai", {}).get("prediction")]
    print("\n" + "=" * 80)
    print("BLIND AI VISION SCORE")
    print("=" * 80)
    print(f"Scored cases: {len(usable)}")
    if not usable:
        return

    correct = sum(r["ai"]["prediction"] == r["actual"]["label"] for r in usable)
    print(f"Accuracy: {correct}/{len(usable)} = {correct / len(usable) * 100:.2f}%")

    print("\nCONFUSION MATRIX")
    labels = ["REAL", "WEAK", "FALSE"]
    print("prediction -> actual")
    print("             " + "  ".join(f"{x:>6}" for x in labels))
    matrix = Counter((r["ai"]["prediction"], r["actual"]["label"]) for r in usable)
    for pred in labels:
        print(f"{pred:>10}   " + "  ".join(f"{matrix[(pred, act)]:6d}" for act in labels))

    for target in labels:
        tp = sum(r["ai"]["prediction"] == target and r["actual"]["label"] == target for r in usable)
        fp = sum(r["ai"]["prediction"] == target and r["actual"]["label"] != target for r in usable)
        fn = sum(r["ai"]["prediction"] != target and r["actual"]["label"] == target for r in usable)
        precision = tp / (tp + fp) * 100 if tp + fp else 0.0
        recall = tp / (tp + fn) * 100 if tp + fn else 0.0
        print(f"{target}: precision={precision:.2f}% recall={recall:.2f}%")

    confidence_buckets = defaultdict(list)
    for r in usable:
        bucket = min(100, (int(r["ai"]["confidence"]) // 10) * 10)
        confidence_buckets[bucket].append(r)
    print("\nCONFIDENCE CALIBRATION")
    for bucket in sorted(confidence_buckets):
        group = confidence_buckets[bucket]
        acc = sum(x["ai"]["prediction"] == x["actual"]["label"] for x in group) / len(group) * 100
        print(f"{bucket:02d}-{bucket+9:02d}: n={len(group):3d} accuracy={acc:6.2f}%")

    by_direction = defaultdict(list)
    by_transition = defaultdict(list)
    for r in usable:
        by_direction[r["actual"]["label"]].append(r)
        f = r["features"]
        by_transition[f"{f['from']}->{f['to']}"] .append(r)

    print("\nBY TRANSITION TYPE")
    for key in sorted(by_transition):
        group = by_transition[key]
        acc = sum(x["ai"]["prediction"] == x["actual"]["label"] for x in group) / len(group) * 100
        print(f"{key:14s} n={len(group):3d} accuracy={acc:6.2f}%")

    print("\nHIGH-CONFIDENCE MISTAKES (>=80 confidence)")
    mistakes = [r for r in usable if r["ai"]["prediction"] != r["actual"]["label"] and r["ai"]["confidence"] >= 80]
    mistakes.sort(key=lambda r: r["ai"]["confidence"], reverse=True)
    for r in mistakes[:15]:
        print(
            f"{r['case_id']} predicted={r['ai']['prediction']} "
            f"actual={r['actual']['label']} conf={r['ai']['confidence']} "
            f"reason={r['ai']['reason']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Maximum NEW AI cases to score; 0 = all")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--fresh", action="store_true", help="Ignore previous local results and start again")
    parser.add_argument("--delay", type=float, default=0.0, help="Optional delay between API calls")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set. Set it as an environment variable; never paste the key into this file.")

    if args.fresh and RESULTS_FILE.exists():
        RESULTS_FILE.unlink()

    cases = load_cases()
    existing = load_existing()
    pending = [c for c in cases if case_id(c) not in existing]
    if args.limit > 0:
        pending = pending[: args.limit]

    print("AI VISION BLIND SCORING RUNNER")
    print(f"Model: {args.model}")
    print(f"Total cases available: {len(cases)}")
    print(f"Already scored locally: {len(existing)}")
    print(f"New cases this run: {len(pending)}")
    print("FUTURE OUTCOME IS NOT SENT TO THE MODEL.")

    client = OpenAI()
    for n, case in enumerate(pending, 1):
        cid = case_id(case)
        print(f"[{n}/{len(pending)}] {cid}", flush=True)
        try:
            # Blind inference happens first.
            ai = call_ai(client, args.model, case)
            # Only after the model returns do we attach the actual outcome.
            row = {
                "case_id": cid,
                "symbol": case["symbol"],
                "transition_time": case["transition_time"],
                "direction": case["direction"],
                "features": case["features_available_at_transition"],
                "ai": ai,
                "actual": case["future_outcome"],
            }
            with RESULTS_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True) + "\n")
            existing[cid] = row
            print(
                f"    AI={ai['prediction']} conf={ai['confidence']} "
                f"actual={case['future_outcome']['label']}"
            )
        except Exception as exc:
            print(f"    ERROR: {type(exc).__name__}: {exc}")
        if args.delay:
            time.sleep(args.delay)

    score(list(existing.values()))
    print(f"\nResults saved to: {RESULTS_FILE.resolve()}")


if __name__ == "__main__":
    main()
