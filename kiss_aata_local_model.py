"""
AATA LOCAL TRANSITION MODEL

Research only.
- Does NOT call OpenAI or any external API.
- Does NOT modify the KISS engine.
- Does NOT place trades.
- Does NOT write to the trading database.

Purpose:
    Train a local machine-learning model on historical transition cases and
    test it on later, unseen cases. The model sees only information that was
    available at the transition. The future outcome is used ONLY as the label
    for training/scoring, never as an input feature.

This is deliberately a first experiment, not a production trading model.
"""

from __future__ import annotations

import argparse
import math
from collections import Counter
from typing import Any, Dict, List, Sequence, Tuple

from kiss_ai_transition_research import SYMBOLS, _db_rows, build_states, transition_events, make_case

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
except ImportError as exc:
    raise SystemExit(
        "scikit-learn is not installed in this virtualenv. "
        "Install it with: pip install scikit-learn"
    ) from exc


RANDOM_SEED = 42
TRAIN_FRACTION = 0.70
PURGE_HOURS = 4.0

NUMERIC_FEATURES = [
    "price",
    "ma20",
    "distance_pct",
    "rsi",
    "previous_state_duration_bars",
    "state_churn_6bars",
    "move_1bar_pct",
    "move_2bar_pct",
    "move_3bar_pct",
    "move_4bar_pct",
    "move_6bar_pct",
    "move_12bar_pct",
    "recent_12bar_high_distance_pct",
    "recent_12bar_low_distance_pct",
]

CATEGORICAL_FEATURES = [
    ("direction", ["LONG", "SHORT"]),
    ("transition", ["FLAT->LONG", "SHORT->LONG", "LONG->SHORT", "FLAT->SHORT"]),
    ("ma_slope", ["UP", "DOWN", "FLAT"]),
    ("shape", ["V-LONG", "V-SHORT", "NO_SHAPE"]),
]

LABELS = ["REAL", "WEAK", "FALSE"]


def load_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for symbol in SYMBOLS:
        trend = _db_rows(symbol, "30m")
        execution = _db_rows(symbol, "5m")
        if len(trend) < 22 or len(execution) < 48:
            print(f"{symbol}: SKIP (30m={len(trend)}, 5m={len(execution)})")
            continue
        states = build_states(trend)
        events = transition_events(trend, states)
        for event in events:
            case = make_case(symbol, event, execution)
            if case and case["future_outcome"]["label"] in LABELS:
                cases.append(case)
        print(f"{symbol}: loaded")
    cases.sort(key=lambda c: c["transition_time"])
    return cases


def raw_features(case: Dict[str, Any]) -> Dict[str, Any]:
    f = dict(case["features_available_at_transition"])
    transition = f"{case['features_available_at_transition'].get('from', '')}->{case['features_available_at_transition'].get('to', '')}"
    # The research harness keeps from/to in the feature dictionary.
    f["direction"] = case["direction"]
    f["transition"] = transition
    return f


def build_matrix(train_cases: Sequence[Dict[str, Any]], cases: Sequence[Dict[str, Any]]) -> Tuple[List[List[float]], List[str]]:
    # Medians are calculated from TRAIN ONLY to avoid test-set information
    # leaking into preprocessing.
    medians: Dict[str, float] = {}
    for name in NUMERIC_FEATURES:
        vals = []
        for case in train_cases:
            value = raw_features(case).get(name)
            try:
                x = float(value)
                if math.isfinite(x):
                    vals.append(x)
            except (TypeError, ValueError):
                pass
        vals.sort()
        medians[name] = vals[len(vals) // 2] if vals else 0.0

    feature_names = list(NUMERIC_FEATURES)
    for name, values in CATEGORICAL_FEATURES:
        feature_names.extend(f"{name}={value}" for value in values)

    matrix: List[List[float]] = []
    for case in cases:
        f = raw_features(case)
        row: List[float] = []
        for name in NUMERIC_FEATURES:
            try:
                x = float(f.get(name))
                row.append(x if math.isfinite(x) else medians[name])
            except (TypeError, ValueError):
                row.append(medians[name])

        for name, values in CATEGORICAL_FEATURES:
            actual = f.get(name)
            row.extend(1.0 if actual == value else 0.0 for value in values)
        matrix.append(row)

    return matrix, feature_names


def purge_split(cases: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Chronological split with a 4-hour gap between train and test."""
    cut = max(1, int(len(cases) * TRAIN_FRACTION))
    train = list(cases[:cut])
    if not train:
        return [], []

    # Keep the test period strictly after a small purge gap so outcomes from
    # cases near the boundary do not overlap as closely as possible.
    boundary = train[-1]["transition_time"]
    from datetime import datetime, timedelta
    boundary_dt = datetime.fromisoformat(boundary.replace("Z", "+00:00"))
    test_start = boundary_dt + timedelta(hours=PURGE_HOURS)
    test = []
    for case in cases[cut:]:
        t = datetime.fromisoformat(case["transition_time"].replace("Z", "+00:00"))
        if t >= test_start:
            test.append(case)
    return train, test


def print_examples(model: RandomForestClassifier, x_test: List[List[float]], test_cases: Sequence[Dict[str, Any]]) -> None:
    probs = model.predict_proba(x_test)
    predictions = model.classes_[probs.argmax(axis=1)]
    confidence = probs.max(axis=1)
    print()
    print("TEST EXAMPLES")
    for i, case in enumerate(test_cases[:10]):
        actual = case["future_outcome"]["label"]
        print(
            f"{i + 1:02d} {case['symbol']}|{case['direction']}|{case['transition_time']} "
            f"MODEL={predictions[i]} conf={confidence[i] * 100:.0f}% actual={actual}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trees", type=int, default=300, help="number of random-forest trees")
    args = parser.parse_args()

    print("AATA LOCAL TRANSITION MODEL")
    print("Research only: no API, no engine changes, no trades, no DB writes")
    print("The model receives only transition-time features.")
    print("Future outcome is used only as the training/test label.")
    print("=" * 80)

    cases = load_cases()
    print("=" * 80)
    print(f"TOTAL CASES: {len(cases)}")
    print(f"LABELS: {dict(Counter(c['future_outcome']['label'] for c in cases))}")

    train, test = purge_split(cases)
    if len(train) < 30 or len(test) < 20:
        raise SystemExit(f"Not enough cases after chronological split: train={len(train)} test={len(test)}")

    print(f"TRAIN CASES: {len(train)}")
    print(f"TEST CASES:  {len(test)}")
    print(f"PURGE GAP:   {PURGE_HOURS:.1f} hours")
    print(f"TRAIN PERIOD: {train[0]['transition_time']} -> {train[-1]['transition_time']}")
    print(f"TEST PERIOD:  {test[0]['transition_time']} -> {test[-1]['transition_time']}")

    x_train, feature_names = build_matrix(train, train)
    x_test, _ = build_matrix(train, test)
    y_train = [c["future_outcome"]["label"] for c in train]
    y_test = [c["future_outcome"]["label"] for c in test]

    model = RandomForestClassifier(
        n_estimators=max(50, args.trees),
        max_depth=6,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    probs = model.predict_proba(x_test)
    confidences = probs.max(axis=1)

    accuracy = accuracy_score(y_test, predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, predictions, labels=LABELS, zero_division=0
    )
    cm = confusion_matrix(y_test, predictions, labels=LABELS)

    majority = Counter(y_train).most_common(1)[0][0]
    majority_accuracy = sum(1 for y in y_test if y == majority) / len(y_test)

    print()
    print("RESULTS ON UNSEEN TEST DATA")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Training-majority baseline ({majority}): {majority_accuracy * 100:.2f}%")
    print()
    print("CONFUSION MATRIX (actual -> predicted)")
    print("             " + " ".join(f"{label:>7}" for label in LABELS))
    for i, label in enumerate(LABELS):
        print(f"{label:>7} : " + " ".join(f"{cm[i, j]:7d}" for j in range(len(LABELS))))
    print()
    print("PER CLASS")
    for label, p, r, f in zip(LABELS, precision, recall, f1):
        print(f"{label:>5}: precision={p * 100:6.2f}% recall={r * 100:6.2f}% f1={f * 100:6.2f}%")

    print()
    print("HIGH-CONFIDENCE MISTAKES (>=80%)")
    found = 0
    for i, case in enumerate(test):
        if predictions[i] != y_test[i] and confidences[i] >= 0.80:
            print(
                f"{case['symbol']}|{case['direction']}|{case['transition_time']} "
                f"MODEL={predictions[i]} conf={confidences[i] * 100:.0f}% actual={y_test[i]}"
            )
            found += 1
    if not found:
        print("None")

    print()
    print("TOP FEATURES")
    ranked = sorted(zip(feature_names, model.feature_importances_), key=lambda x: x[1], reverse=True)
    for name, importance in ranked[:12]:
        print(f"{name:42s} {importance * 100:6.2f}%")

    print_examples(model, x_test, test)

    print()
    print("IMPORTANT:")
    print("This is a first local learning experiment, not a trading model.")
    print("A good test score is required before we consider using it for decisions.")
    print("Professor feedback has NOT been included yet; that will be a separate learning layer.")


if __name__ == "__main__":
    main()
