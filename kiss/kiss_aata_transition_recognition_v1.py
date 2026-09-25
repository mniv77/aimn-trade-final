# kiss_aata_transition_recognition_v1.py
"""
AATA Transition Recognition V1
================================

RESEARCH ONLY.

This file:
- reads real historical 30m/5m market data from the existing DB
- DOES NOT modify the trading engine
- DOES NOT place trades
- DOES NOT write to the DB
- DOES NOT call an external AI/API
- uses only information available at each historical decision point
- uses future information ONLY AFTER the prediction, for scoring
- uses walk-forward training so the model never trains on later data

Goal:
    Test whether a local AATA model can recognize a developing
    LONG or SHORT transition BEFORE the existing MA20 state detector
    flips.

The experiment deliberately separates:

    WHAT AATA KNEW
        from
    WHAT ACTUALLY HAPPENED LATER

That separation is the most important part of this experiment.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from db import get_db_connection

from engine.kiss_execution_5m import (
    TREND_BAND,
    TREND_WINDOW,
    get_market_state,
    rsi_wilder,
)

from sklearn.ensemble import RandomForestClassifier


# ============================================================
# CONFIGURATION
# ============================================================

SYMBOLS = [
    "NVDA",
    "AAPL",
    "MSFT",
    "AMZN",
    "TSLA",
    "META",
    "AMD",
    "SPY",
    "QQQ",
]

TREND_TIMEFRAME = "30m"
EXECUTION_TIMEFRAME = "5m"

LIMIT = 5000

# A prediction may look ahead ONLY for scoring/label creation.
# The model itself never receives this information.
LOOKAHEAD_BARS = 4

# How far ahead we allow AATA to anticipate the existing
# transition detector.
#
# Example:
# existing detector flips at 14:00.
# AATA prediction at 13:00 can count as an early recognition.
EARLY_WINDOW_BARS = 4

# Minimum historical training examples before making predictions.
MIN_TRAIN_CASES = 80

# Minimum confidence required to call a developing transition.
PREDICTION_THRESHOLD = 0.60

RANDOM_STATE = 42


# ============================================================
# DATABASE
# ============================================================

def _db_rows(
    symbol: str,
    timeframe: str,
    limit: int = LIMIT,
) -> List[Dict[str, Any]]:
    conn, cursor = get_db_connection()

    try:
        cursor.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=%s AND timeframe=%s
            ORDER BY timestamp ASC
            LIMIT %s
            """,
            (symbol, timeframe, int(limit)),
        )

        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    finally:
        cursor.close()
        conn.close()


# ============================================================
# BASIC HELPERS
# ============================================================

def _dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value

    return datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )


def _pct(a: float, b: float) -> float:
    if not b:
        return 0.0

    return (a / b) - 1.0


def _safe_float(value: Any) -> Optional[float]:
    try:
        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    except Exception:
        return None


# ============================================================
# STATE CALCULATION
# ============================================================

def build_states(rows: Sequence[Dict[str, Any]]) -> List[str]:
    closes = [
        float(row["close"])
        for row in rows
    ]

    return [
        get_market_state(closes, i)
        for i in range(len(closes))
    ]


# ============================================================
# FIND THE EXISTING TRANSITIONS
# ============================================================

def find_transitions(
    rows: Sequence[Dict[str, Any]],
    states: Sequence[str],
) -> List[Dict[str, Any]]:

    transitions: List[Dict[str, Any]] = []

    for i in range(1, len(rows)):

        previous = states[i - 1]
        current = states[i]

        if previous == current:
            continue

        if current == "FLAT":
            continue

        if current not in ("LONG", "SHORT"):
            continue

        if previous not in ("LONG", "SHORT", "FLAT"):
            continue

        transitions.append(
            {
                "index": i,
                "time": _dt(rows[i]["timestamp"]),
                "from": previous,
                "to": current,
                "price": float(rows[i]["close"]),
            }
        )

    return transitions


# ============================================================
# BACKWARD-LOOKING FEATURES
# ============================================================

def feature_vector(
    rows: Sequence[Dict[str, Any]],
    states: Sequence[str],
    index: int,
) -> Optional[Dict[str, float]]:

    # IMPORTANT:
    #
    # Everything below uses candles at index or BEFORE index.
    #
    # Nothing from index + 1 or later is allowed here.

    if index < TREND_WINDOW + 12:
        return None

    closes = [
        float(row["close"])
        for row in rows
    ]

    price = closes[index]

    # --------------------------------------------------------
    # MA20 using only candles BEFORE/current point
    # --------------------------------------------------------

    ma_start = index - TREND_WINDOW
    ma_window = closes[ma_start:index]

    if not ma_window:
        return None

    ma20 = sum(ma_window) / len(ma_window)

    # Previous MA20
    previous_window = closes[
        index - TREND_WINDOW - 1:index - 1
    ]

    if previous_window:
        previous_ma20 = (
            sum(previous_window)
            / len(previous_window)
        )
    else:
        previous_ma20 = ma20

    ma_slope_pct = _pct(ma20, previous_ma20)

    distance_pct = _pct(price, ma20)

    # --------------------------------------------------------
    # RSI
    #
    # rsi_wilder is calculated from the historical sequence,
    # but RSI at this index depends only on candles up to this
    # point.
    # --------------------------------------------------------

    rsi_values = rsi_wilder(closes)

    rsi = (
        _safe_float(rsi_values[index])
        if index < len(rsi_values)
        else None
    )

    if rsi is None:
        rsi = 50.0

    # --------------------------------------------------------
    # Recent price movement
    # --------------------------------------------------------

    def move(bars: int) -> float:

        if index - bars < 0:
            return 0.0

        return _pct(
            closes[index],
            closes[index - bars],
        )

    move_1 = move(1)
    move_2 = move(2)
    move_3 = move(3)
    move_4 = move(4)
    move_6 = move(6)
    move_12 = move(12)

    # --------------------------------------------------------
    # Recent range
    # --------------------------------------------------------

    recent = closes[index - 12:index]

    recent_high = max(recent)
    recent_low = min(recent)

    distance_from_high = _pct(
        price,
        recent_high,
    )

    distance_from_low = _pct(
        price,
        recent_low,
    )

    # --------------------------------------------------------
    # State persistence
    # --------------------------------------------------------

    current_state = states[index]

    state_duration = 1

    j = index - 1

    while j >= 0 and states[j] == current_state:
        state_duration += 1
        j -= 1

    # --------------------------------------------------------
    # Recent state churn
    # --------------------------------------------------------

    churn = 0

    for j in range(
        max(1, index - 6),
        index + 1,
    ):
        if states[j] != states[j - 1]:
            churn += 1

    # --------------------------------------------------------
    # Candle direction sequence
    # --------------------------------------------------------

    up_count_3 = 0
    down_count_3 = 0

    for j in range(
        max(1, index - 2),
        index + 1,
    ):
        if closes[j] > closes[j - 1]:
            up_count_3 += 1

        elif closes[j] < closes[j - 1]:
            down_count_3 += 1

    # --------------------------------------------------------
    # Return ONLY backward/current information.
    # --------------------------------------------------------

    return {
        "price": price,
        "ma20": ma20,
        "distance_pct": distance_pct,
        "ma_slope_pct": ma_slope_pct,
        "rsi": rsi,

        "move_1bar_pct": move_1,
        "move_2bar_pct": move_2,
        "move_3bar_pct": move_3,
        "move_4bar_pct": move_4,
        "move_6bar_pct": move_6,
        "move_12bar_pct": move_12,

        "distance_from_high_pct": distance_from_high,
        "distance_from_low_pct": distance_from_low,

        "state_duration_bars": float(state_duration),
        "state_churn_6bars": float(churn),

        "up_count_3": float(up_count_3),
        "down_count_3": float(down_count_3),
    }


FEATURE_NAMES = [
    "price",
    "ma20",
    "distance_pct",
    "ma_slope_pct",
    "rsi",

    "move_1bar_pct",
    "move_2bar_pct",
    "move_3bar_pct",
    "move_4bar_pct",
    "move_6bar_pct",
    "move_12bar_pct",

    "distance_from_high_pct",
    "distance_from_low_pct",

    "state_duration_bars",
    "state_churn_6bars",

    "up_count_3",
    "down_count_3",
]


# ============================================================
# FUTURE LABEL
# ============================================================

def future_transition_label(
    states: Sequence[str],
    index: int,
) -> str:

    """
    This function is allowed to look forward.

    IMPORTANT:
        It is NEVER called to construct model features.

    It exists only to create the historical training/test label.
    """

    end = min(
        len(states),
        index + LOOKAHEAD_BARS + 1,
    )

    for j in range(index + 1, end):

        if states[j] == "LONG":
            return "LONG"

        if states[j] == "SHORT":
            return "SHORT"

    return "NONE"


# ============================================================
# BUILD WALK-FORWARD DATA
# ============================================================

def build_dataset(
    symbol: str,
    rows: Sequence[Dict[str, Any]],
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:

    states = build_states(rows)

    transitions = find_transitions(
        rows,
        states,
    )

    dataset: List[Dict[str, Any]] = []

    for i in range(
        TREND_WINDOW + 12,
        len(rows) - LOOKAHEAD_BARS,
    ):

        features = feature_vector(
            rows,
            states,
            i,
        )

        if features is None:
            continue

        label = future_transition_label(
            states,
            i,
        )

        dataset.append(
            {
                "symbol": symbol,
                "index": i,
                "time": _dt(rows[i]["timestamp"]),
                "features": features,
                "label": label,
                "state": states[i],
            }
        )

    return dataset, transitions


# ============================================================
# MODEL
# ============================================================

def train_model(
    training_cases: Sequence[Dict[str, Any]],
) -> Optional[RandomForestClassifier]:

    if len(training_cases) < MIN_TRAIN_CASES:
        return None

    usable = [
        case
        for case in training_cases
        if case["label"] in ("LONG", "SHORT", "NONE")
    ]

    if len(usable) < MIN_TRAIN_CASES:
        return None

    labels = [
        case["label"]
        for case in usable
    ]

    if len(set(labels)) < 2:
        return None

    X = [
        [
            case["features"][name]
            for name in FEATURE_NAMES
        ]
        for case in usable
    ]

    y = labels

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=8,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    model.fit(X, y)

    return model


# ============================================================
# PREDICTION
# ============================================================

def predict(
    model: RandomForestClassifier,
    case: Dict[str, Any],
) -> Tuple[str, float]:

    X = [[
        case["features"][name]
        for name in FEATURE_NAMES
    ]]

    probabilities = model.predict_proba(X)[0]

    classes = list(model.classes_)

    best_index = max(
        range(len(probabilities)),
        key=lambda i: probabilities[i],
    )

    prediction = classes[best_index]
    confidence = float(probabilities[best_index])

    if confidence < PREDICTION_THRESHOLD:
        return "NONE", confidence

    return prediction, confidence


# ============================================================
# MATCH AATA EARLY PREDICTIONS TO REAL TRANSITIONS
# ============================================================

def evaluate_early_predictions(
    predictions: Sequence[Dict[str, Any]],
    transitions: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    results: List[Dict[str, Any]] = []

    for transition in transitions:

        transition_time = transition["time"]
        direction = transition["to"]

        eligible = []

        for prediction in predictions:

            if prediction["prediction"] != direction:
                continue

            if prediction["time"] >= transition_time:
                continue

            delta_seconds = (
                transition_time
                - prediction["time"]
            ).total_seconds()

            delta_bars = delta_seconds / (
                30 * 60
            )

            if 0 < delta_bars <= EARLY_WINDOW_BARS:
                eligible.append(
                    (
                        delta_bars,
                        prediction,
                    )
                )

        if not eligible:
            results.append(
                {
                    "transition": transition,
                    "recognized": False,
                    "lead_bars": None,
                    "confidence": None,
                }
            )

            continue

        # Use the latest valid prediction before the
        # actual transition.
        eligible.sort(
            key=lambda x: x[0]
        )

        lead_bars, best = eligible[0]

        results.append(
            {
                "transition": transition,
                "recognized": True,
                "lead_bars": lead_bars,
                "confidence": best["confidence"],
                "prediction_time": best["time"],
            }
        )

    return results


# ============================================================
# MAIN RESEARCH RUN
# ============================================================

def run_symbol(
    symbol: str,
) -> Optional[Dict[str, Any]]:

    trend_rows = _db_rows(
        symbol,
        TREND_TIMEFRAME,
    )

    if len(trend_rows) < TREND_WINDOW + 20:
        print(
            f"{symbol}: SKIP "
            f"(30m candles={len(trend_rows)})"
        )

        return None

    dataset, transitions = build_dataset(
        symbol,
        trend_rows,
    )

    if not dataset:
        print(
            f"{symbol}: SKIP "
            "(no usable dataset)"
        )

        return None

    predictions: List[Dict[str, Any]] = []

    # --------------------------------------------------------
    # WALK FORWARD
    #
    # At point i:
    #
    # training = cases sufficiently before i
    # prediction = case at i
    #
    # The current case is NEVER used for training.
    #
    # The future label of the current case is NOT used
    # until after prediction.
    # --------------------------------------------------------

    for position, case in enumerate(dataset):

        # The last LOOKAHEAD_BARS cases are excluded from
        # training to create a clean purge gap.
        cutoff_time = (
            case["time"]
        )

        training_cases = [
            previous
            for previous in dataset[:position]
            if previous["time"] < cutoff_time
        ]

        # Purge cases whose future-label window could overlap
        # the current prediction point.
        purge_seconds = (
            LOOKAHEAD_BARS
            * 30
            * 60
        )

        safe_training = []

        for previous in training_cases:

            age_seconds = (
                cutoff_time
                - previous["time"]
            ).total_seconds()

            if age_seconds > purge_seconds:
                safe_training.append(previous)

        model = train_model(
            safe_training
        )

        if model is None:
            continue

        prediction, confidence = predict(
            model,
            case,
        )

        if prediction == "NONE":
            continue

        predictions.append(
            {
                "symbol": symbol,
                "time": case["time"],
                "index": case["index"],
                "state_at_prediction": case["state"],
                "prediction": prediction,
                "confidence": confidence,
            }
        )

    # --------------------------------------------------------
    # Evaluate early recognition against actual transitions.
    # --------------------------------------------------------

    early_results = evaluate_early_predictions(
        predictions,
        transitions,
    )

    recognized = [
        result
        for result in early_results
        if result["recognized"]
    ]

    long_predictions = [
        p
        for p in predictions
        if p["prediction"] == "LONG"
    ]

    short_predictions = [
        p
        for p in predictions
        if p["prediction"] == "SHORT"
    ]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    total_transitions = len(transitions)
    recognized_count = len(recognized)

    recognition_rate = (
        recognized_count / total_transitions
        if total_transitions
        else 0.0
    )

    lead_bars = [
        result["lead_bars"]
        for result in recognized
        if result["lead_bars"] is not None
    ]

    average_lead = (
        sum(lead_bars) / len(lead_bars)
        if lead_bars
        else 0.0
    )

    maximum_lead = (
        max(lead_bars)
        if lead_bars
        else 0.0
    )

    transition_counts = Counter(
        transition["to"]
        for transition in transitions
    )

    recognized_counts = Counter(
        result["transition"]["to"]
        for result in recognized
    )

    print()
    print("=" * 80)
    print(f"AATA V1 — {symbol}")
    print("=" * 80)

    print(
        f"30m candles:          {len(trend_rows)}"
    )

    print(
        f"Usable model cases:   {len(dataset)}"
    )

    print(
        f"Existing transitions: {total_transitions}"
    )

    print(
        f"AATA predictions:     {len(predictions)}"
    )

    print()

    print(
        f"LONG transitions:     "
        f"{transition_counts['LONG']}"
    )

    print(
        f"SHORT transitions:    "
        f"{transition_counts['SHORT']}"
    )

    print()

    print(
        f"Transitions recognized early: "
        f"{recognized_count}/{total_transitions} "
        f"({recognition_rate * 100:.1f}%)"
    )

    print(
        f"Average lead:         "
        f"{average_lead:.2f} x 30m bars"
    )

    print(
        f"Maximum lead:         "
        f"{maximum_lead:.2f} x 30m bars"
    )

    print()

    print(
        f"LONG recognized early:  "
        f"{recognized_counts['LONG']}/"
        f"{transition_counts['LONG']}"
    )

    print(
        f"SHORT recognized early: "
        f"{recognized_counts['SHORT']}/"
        f"{transition_counts['SHORT']}"
    )

    # --------------------------------------------------------
    # Show actual examples.
    # --------------------------------------------------------

    print()
    print("EARLY RECOGNITION EXAMPLES")
    print("-" * 80)

    for result in recognized[:12]:

        transition = result["transition"]

        print(
            f"{transition['time']} | "
            f"{transition['from']}->{transition['to']} | "
            f"AATA predicted at "
            f"{result['prediction_time']} | "
            f"lead={result['lead_bars']:.2f} bars | "
            f"confidence={result['confidence'] * 100:.1f}%"
        )

    print()

    # --------------------------------------------------------
    # Show cases where AATA produced a prediction that did
    # NOT correspond to an upcoming transition.
    #
    # This is important. We don't want early prediction
    # at the cost of generating noise everywhere.
    # --------------------------------------------------------

    false_early_predictions = []

    for prediction in predictions:

        matched = False

        for transition in transitions:

            if transition["to"] != prediction["prediction"]:
                continue

            if prediction["time"] >= transition["time"]:
                continue

            delta_bars = (
                transition["time"]
                - prediction["time"]
            ).total_seconds() / (30 * 60)

            if 0 < delta_bars <= EARLY_WINDOW_BARS:
                matched = True
                break

        if not matched:
            false_early_predictions.append(
                prediction
            )

    print("PREDICTIONS WITHOUT A MATCHING TRANSITION")
    print("-" * 80)

    print(
        f"Unmatched predictions: "
        f"{len(false_early_predictions)}"
    )

    for prediction in false_early_predictions[:10]:

        print(
            f"{prediction['time']} | "
            f"{prediction['state_at_prediction']} | "
            f"predicted {prediction['prediction']} | "
            f"confidence="
            f"{prediction['confidence'] * 100:.1f}%"
        )

    return {
        "symbol": symbol,
        "candles": len(trend_rows),
        "dataset_cases": len(dataset),
        "transitions": total_transitions,
        "predictions": len(predictions),
        "recognized": recognized_count,
        "recognition_rate": recognition_rate,
        "average_lead_bars": average_lead,
        "maximum_lead_bars": maximum_lead,
        "long_transitions": transition_counts["LONG"],
        "short_transitions": transition_counts["SHORT"],
        "long_recognized": recognized_counts["LONG"],
        "short_recognized": recognized_counts["SHORT"],
        "unmatched_predictions": len(
            false_early_predictions
        ),
    }


# ============================================================
# PROGRAM ENTRY
# ============================================================

def main() -> None:

    print()
    print("=" * 80)
    print("AATA TRANSITION RECOGNITION V1")
    print("=" * 80)
    print()
    print("RESEARCH ONLY")
    print("No API")
    print("No trades")
    print("No engine changes")
    print("No DB writes")
    print()
    print("STRICT NO-LOOK-AHEAD TEST")
    print()
    print(
        "AATA prediction uses ONLY information available "
        "at the prediction candle."
    )
    print()
    print(
        "Future market behavior is used ONLY afterward "
        "to score the prediction."
    )
    print()
    print(
        f"Look-ahead scoring horizon: "
        f"{LOOKAHEAD_BARS} x 30m"
    )
    print(
        f"Early-recognition window: "
        f"{EARLY_WINDOW_BARS} x 30m"
    )
    print(
        f"Training minimum: "
        f"{MIN_TRAIN_CASES}"
    )
    print(
        f"Prediction threshold: "
        f"{PREDICTION_THRESHOLD * 100:.0f}%"
    )
    print()

    all_results = []

    for symbol in SYMBOLS:

        try:
            result = run_symbol(symbol)

            if result is not None:
                all_results.append(result)

        except Exception as exc:

            print()
            print(
                f"{symbol}: ERROR: {exc}"
            )

    # --------------------------------------------------------
    # Combined summary
    # --------------------------------------------------------

    print()
    print()
    print("=" * 80)
    print("AATA V1 COMBINED SUMMARY")
    print("=" * 80)

    if not all_results:

        print("No usable symbols.")

        return

    total_transitions = sum(
        r["transitions"]
        for r in all_results
    )

    total_recognized = sum(
        r["recognized"]
        for r in all_results
    )

    total_predictions = sum(
        r["predictions"]
        for r in all_results
    )

    total_unmatched = sum(
        r["unmatched_predictions"]
        for r in all_results
    )

    all_leads = []

    for result in all_results:

        # Weighted average will be calculated below.
        if result["recognized"] > 0:
            all_leads.extend(
                [result["average_lead_bars"]]
                * result["recognized"]
            )

    combined_rate = (
        total_recognized / total_transitions
        if total_transitions
        else 0.0
    )

    combined_average_lead = (
        sum(all_leads) / len(all_leads)
        if all_leads
        else 0.0
    )

    print()
    print(
        f"Symbols tested:       "
        f"{len(all_results)}"
    )

    print(
        f"Transitions:          "
        f"{total_transitions}"
    )

    print(
        f"AATA predictions:     "
        f"{total_predictions}"
    )

    print(
        f"Early recognitions:    "
        f"{total_recognized}"
    )

    print(
        f"Recognition rate:      "
        f"{combined_rate * 100:.1f}%"
    )

    print(
        f"Average lead:          "
        f"{combined_average_lead:.2f} x 30m"
    )

    print(
        f"Unmatched predictions: "
        f"{total_unmatched}"
    )

    print()
    print("SYMBOL")
    print(
        "       TRANSITIONS  RECOGNIZED  "
        "RATE     AVG_LEAD"
    )
    print("-" * 80)

    for result in all_results:

        rate = (
            result["recognized"]
            / result["transitions"]
            if result["transitions"]
            else 0.0
        )

        print(
            f"{result['symbol']:<7}"
            f"{result['transitions']:>11}"
            f"{result['recognized']:>12}"
            f"{rate * 100:>8.1f}%"
            f"{result['average_lead_bars']:>11.2f}"
        )

    print()
    print("=" * 80)
    print("END OF AATA V1 RESEARCH")
    print("=" * 80)
    print()
    print(
        "IMPORTANT:"
    )
    print(
        "Do NOT change the trading engine from these results."
    )
    print(
        "First inspect whether the recognition is genuinely "
        "early and whether unmatched predictions are acceptable."
    )
    print()


if __name__ == "__main__":
    main()