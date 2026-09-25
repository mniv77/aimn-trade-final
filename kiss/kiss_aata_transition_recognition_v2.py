#  kiss_aata_transition_recognition_v2.py
"""
AATA Transition Recognition V2
==============================

RESEARCH ONLY.

Purpose
-------
Test whether a local AATA model can recognize a DEVELOPING directional
transition before the existing MA20 state detector officially flips.

This version specifically fixes the main weakness discovered in V1:

V1 generated many repeated LONG/SHORT predictions while the market
remained in the same condition.

V2 treats a transition as ONE EVENT.

For each historical transition:

    developing transition
            |
            v
    earliest valid AATA prediction
            |
            v
    REAL / WEAK / FALSE outcome
            |
            v
    measure lead time and price behavior

Safety
------
- NO API
- NO external AI
- NO trades
- NO engine changes
- NO DB writes
- Historical data only
- Future data is used ONLY for training labels and
  post-prediction scoring
- Walk-forward training
- Purge gap between training and test
- No future features are supplied to the model

Main research questions
-----------------------
1. Can AATA recognize SHORT -> LONG before the existing detector?
2. Can AATA recognize LONG -> SHORT before the existing detector?
3. How early is recognition?
4. Are the recognized transitions REAL, WEAK, or FALSE?
5. How many genuine transition events are missed?
6. How many false alarms occur?
7. Does AATA recognize the important reversal transitions better
   than the weaker FLAT transitions?

IMPORTANT
---------
This file must NOT be connected to the trading engine based on this
experiment alone.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

import math

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, accuracy_score

from db import get_db_connection

from engine.kiss_execution_5m import (
    TREND_BAND,
    TREND_WINDOW,
    rsi_wilder,
    get_market_state,
)


# ============================================================================
# CONFIGURATION
# ============================================================================

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

# A developing transition can be predicted up to this many 30m candles
# before the existing detector flips.
EARLY_WINDOW_BARS = 4

# Future horizon used to determine whether the developing transition
# eventually becomes the next directional transition.
LOOKAHEAD_BARS = 4

# Future 5m horizon used ONLY after the transition for outcome scoring.
OUTCOME_HOURS = 4

# Walk-forward settings.
MIN_TRAIN_CASES = 80
PURGE_BARS = 4

# Probability threshold for accepting a directional prediction.
PREDICTION_THRESHOLD = 0.60

# To prevent repeated predictions for the same developing event.
EVENT_COOLDOWN_BARS = 4

# Outcome definitions.
REAL_MFE_PCT = 1.0
REAL_MFE_TO_MAE = 1.5

FALSE_MAE_PCT = 1.0
FALSE_MFE_PCT = 0.5

RANDOM_STATE = 42


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class TransitionEvent:
    index: int
    time: datetime
    from_state: str
    to_state: str
    direction: str
    shape: Optional[str] = None

    outcome: str = "UNKNOWN"

    mfe_pct: float = 0.0
    mae_pct: float = 0.0

    prediction_index: Optional[int] = None
    prediction_time: Optional[datetime] = None
    prediction_direction: Optional[str] = None
    prediction_confidence: float = 0.0

    lead_bars: Optional[int] = None


# ============================================================================
# BASIC HELPERS
# ============================================================================

def _safe_float(value, default: float = 0.0) -> float:
    try:
        x = float(value)
        if not math.isfinite(x):
            return default
        return x
    except Exception:
        return default


def _pct(a: float, b: float) -> float:
    """Percentage change from a to b."""
    if not a:
        return 0.0
    return ((b - a) / a) * 100.0


def _dt(value) -> datetime:
    if isinstance(value, datetime):
        return value

    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()

    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _db_rows(symbol: str, timeframe: str, limit: int = LIMIT):
    """
    Read historical candles from the existing DB connection.

    This function ONLY reads.
    """
    tf_map = {
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1hr": "1h",
        "1h": "1h",
        "6hr": "6h",
        "6h": "6h",
    }

    db_tf = tf_map.get(timeframe, timeframe)

    conn, cursor = get_db_connection()

    try:
        cursor.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=%s
              AND timeframe=%s
            ORDER BY timestamp ASC
            LIMIT %s
            """,
            (symbol, db_tf, int(limit)),
        )

        rows = cursor.fetchall()
        return rows or []

    finally:
        try:
            cursor.close()
        except Exception:
            pass

        try:
            conn.close()
        except Exception:
            pass


def _row_dicts(rows):
    output = []

    for row in rows:
        if isinstance(row, dict):
            output.append(row)
        else:
            output.append(
                {
                    "timestamp": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                }
            )

    return output


# ============================================================================
# STATE / TRANSITION DETECTION
# ============================================================================

def build_states(closes: Sequence[float]) -> List[str]:
    return [
        get_market_state(closes, i)
        for i in range(len(closes))
    ]


def _v_shape(closes: Sequence[float], idx: int) -> Optional[str]:
    if idx < 2:
        return None

    a = closes[idx - 2]
    b = closes[idx - 1]
    c = closes[idx]

    if a > b < c:
        return "V-LONG"

    if a < b > c:
        return "V-SHORT"

    return None


def find_transitions(
    states: Sequence[str],
    times: Sequence[datetime],
    closes: Sequence[float],
) -> List[TransitionEvent]:

    events: List[TransitionEvent] = []

    for i in range(1, len(states)):
        before = states[i - 1]
        after = states[i]

        if before == after:
            continue

        # We only care about directional transitions.
        if after not in ("LONG", "SHORT"):
            continue

        events.append(
            TransitionEvent(
                index=i,
                time=times[i],
                from_state=before,
                to_state=after,
                direction=after,
                shape=_v_shape(closes, i),
            )
        )

    return events


# ============================================================================
# BACKWARD-LOOKING FEATURES
# ============================================================================

def _state_duration(states: Sequence[str], idx: int) -> int:
    if idx <= 0:
        return 0

    current = states[idx - 1]
    duration = 0

    j = idx - 1

    while j >= 0 and states[j] == current:
        duration += 1
        j -= 1

    return duration


def _state_churn(states: Sequence[str], idx: int, window: int = 6) -> int:
    start = max(1, idx - window + 1)

    changes = 0

    for j in range(start, idx + 1):
        if states[j] != states[j - 1]:
            changes += 1

    return changes


def _ma(values: Sequence[float], end_idx: int, window: int) -> float:
    if end_idx < window:
        return sum(values[: end_idx + 1]) / max(1, end_idx + 1)

    start = end_idx - window + 1
    return sum(values[start : end_idx + 1]) / window


def _recent_high(
    closes: Sequence[float],
    idx: int,
    window: int,
) -> float:

    start = max(0, idx - window + 1)

    return max(closes[start : idx + 1])


def _recent_low(
    closes: Sequence[float],
    idx: int,
    window: int,
) -> float:

    start = max(0, idx - window + 1)

    return min(closes[start : idx + 1])


def feature_names() -> List[str]:
    return [
        "price",
        "ma20",
        "distance_pct",
        "ma20_slope_pct",
        "rsi",

        "move_1bar_pct",
        "move_2bar_pct",
        "move_3bar_pct",
        "move_4bar_pct",
        "move_6bar_pct",
        "move_12bar_pct",

        "recent_high_distance_pct",
        "recent_low_distance_pct",

        "state_duration",
        "state_churn",

        "up_count_3",
        "down_count_3",

        "up_count_6",
        "down_count_6",

        "volume_change_pct",
    ]


def feature_vector(
    closes: Sequence[float],
    volumes: Sequence[float],
    states: Sequence[str],
    rsi_values: Sequence[float],
    idx: int,
) -> List[float]:

    price = _safe_float(closes[idx])

    ma20 = _ma(closes, idx, TREND_WINDOW)

    distance_pct = (
        ((price - ma20) / ma20) * 100.0
        if ma20
        else 0.0
    )

    previous_ma_idx = max(0, idx - 3)

    previous_ma = _ma(
        closes,
        previous_ma_idx,
        TREND_WINDOW,
    )

    ma20_slope_pct = (
        ((ma20 - previous_ma) / previous_ma) * 100.0
        if previous_ma
        else 0.0
    )

    def move(bars: int) -> float:
        if idx < bars:
            return 0.0

        return _pct(closes[idx - bars], closes[idx])

    recent_high = _recent_high(closes, idx, 12)
    recent_low = _recent_low(closes, idx, 12)

    recent_high_distance_pct = (
        ((price - recent_high) / recent_high) * 100.0
        if recent_high
        else 0.0
    )

    recent_low_distance_pct = (
        ((price - recent_low) / recent_low) * 100.0
        if recent_low
        else 0.0
    )

    start3 = max(1, idx - 2)

    up_count_3 = 0
    down_count_3 = 0

    for j in range(start3, idx + 1):
        if closes[j] > closes[j - 1]:
            up_count_3 += 1
        elif closes[j] < closes[j - 1]:
            down_count_3 += 1

    start6 = max(1, idx - 5)

    up_count_6 = 0
    down_count_6 = 0

    for j in range(start6, idx + 1):
        if closes[j] > closes[j - 1]:
            up_count_6 += 1
        elif closes[j] < closes[j - 1]:
            down_count_6 += 1

    volume_change_pct = 0.0

    if idx > 0 and volumes[idx - 1]:
        volume_change_pct = (
            (volumes[idx] - volumes[idx - 1])
            / abs(volumes[idx - 1])
        ) * 100.0

    return [
        price,
        ma20,
        distance_pct,
        ma20_slope_pct,
        _safe_float(rsi_values[idx]),

        move(1),
        move(2),
        move(3),
        move(4),
        move(6),
        move(12),

        recent_high_distance_pct,
        recent_low_distance_pct,

        float(_state_duration(states, idx)),
        float(_state_churn(states, idx)),

        float(up_count_3),
        float(down_count_3),

        float(up_count_6),
        float(down_count_6),

        volume_change_pct,
    ]


# ============================================================================
# TRANSITION LABELS FOR TRAINING
# ============================================================================

def next_directional_transition(
    transitions: Sequence[TransitionEvent],
    idx: int,
    lookahead: int,
) -> Optional[str]:

    end = min(
        len(transitions),
        idx + lookahead + 1,
    )

    current_index = transitions[idx].index

    for event in transitions:
        if event.index <= current_index:
            continue

        distance = event.index - current_index

        if distance > lookahead:
            break

        return event.direction

    return None


def build_training_dataset(
    closes: Sequence[float],
    volumes: Sequence[float],
    states: Sequence[str],
    rsi_values: Sequence[float],
    transitions: Sequence[TransitionEvent],
) -> Tuple[List[List[float]], List[str], List[int]]:

    X: List[List[float]] = []
    y: List[str] = []
    indices: List[int] = []

    transition_by_index = {
        event.index: event
        for event in transitions
    }

    for idx in range(TREND_WINDOW + 12, len(closes) - LOOKAHEAD_BARS):
        features = feature_vector(
            closes,
            volumes,
            states,
            rsi_values,
            idx,
        )

        # Is the NEXT directional transition developing?
        label = "NONE"

        if idx in transition_by_index:
            # A transition candle itself is NOT a prediction target.
            # The model should learn to recognize what happens before it.
            label = "NONE"

        else:
            future_direction = None

            for future_idx in range(
                idx + 1,
                min(
                    len(states),
                    idx + LOOKAHEAD_BARS + 1,
                ),
            ):
                before = states[future_idx - 1]
                after = states[future_idx]

                if before != after and after in ("LONG", "SHORT"):
                    future_direction = after
                    break

            if future_direction is not None:
                label = future_direction

        X.append(features)
        y.append(label)
        indices.append(idx)

    return X, y, indices


# ============================================================================
# OUTCOME SCORING
# ============================================================================

def score_transition_outcome(
    event: TransitionEvent,
    execution_rows,
) -> Tuple[str, float, float]:

    if not execution_rows:
        return "UNKNOWN", 0.0, 0.0

    transition_time = event.time

    start = None

    for i, row in enumerate(execution_rows):
        if _dt(row["timestamp"]) >= transition_time:
            start = i
            break

    if start is None:
        return "UNKNOWN", 0.0, 0.0

    entry_price = _safe_float(
        execution_rows[start]["close"]
    )

    if entry_price <= 0:
        return "UNKNOWN", 0.0, 0.0

    end_time = transition_time

    # Four hours of 5m candles.
    horizon_bars = OUTCOME_HOURS * 12

    end = min(
        len(execution_rows),
        start + horizon_bars + 1,
    )

    favorable = []
    adverse = []

    for row in execution_rows[start:end]:

        high = _safe_float(row["high"])
        low = _safe_float(row["low"])

        if event.direction == "LONG":
            favorable.append(
                ((high - entry_price) / entry_price) * 100.0
            )

            adverse.append(
                ((low - entry_price) / entry_price) * 100.0
            )

        else:
            favorable.append(
                ((entry_price - low) / entry_price) * 100.0
            )

            adverse.append(
                ((entry_price - high) / entry_price) * 100.0
            )

    if not favorable or not adverse:
        return "UNKNOWN", 0.0, 0.0

    mfe = max(favorable)
    mae = abs(min(adverse))

    # REAL:
    # Enough favorable movement AND favorable movement dominates adverse.
    if (
        mfe >= REAL_MFE_PCT
        and mfe >= REAL_MFE_TO_MAE * max(mae, 0.01)
    ):
        return "REAL", mfe, mae

    # FALSE:
    # Significant adverse movement occurs while favorable movement
    # never develops sufficiently.
    if (
        mae >= FALSE_MAE_PCT
        and mfe < FALSE_MFE_PCT
    ):
        return "FALSE", mfe, mae

    return "WEAK", mfe, mae


# ============================================================================
# WALK-FORWARD MODEL
# ============================================================================

def train_model(
    X: List[List[float]],
    y: List[str],
    indices: List[int],
    current_index: int,
) -> Optional[RandomForestClassifier]:

    training_positions = []

    for pos, sample_index in enumerate(indices):

        # Only historical data.
        if sample_index >= current_index:
            continue

        # Purge the most recent observations so information immediately
        # surrounding the prediction cannot leak into training.
        if sample_index > current_index - PURGE_BARS:
            continue

        training_positions.append(pos)

    if len(training_positions) < MIN_TRAIN_CASES:
        return None

    X_train = [
        X[pos]
        for pos in training_positions
    ]

    y_train = [
        y[pos]
        for pos in training_positions
    ]

    # Need at least two classes.
    if len(set(y_train)) < 2:
        return None

    model = RandomForestClassifier(
        n_estimators=250,
        max_depth=8,
        min_samples_leaf=4,
        class_weight="balanced_subsample",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)

    return model


def model_prediction(
    model,
    features: List[float],
) -> Tuple[str, float]:

    probabilities = model.predict_proba([features])[0]
    classes = list(model.classes_)

    best_position = max(
        range(len(probabilities)),
        key=lambda i: probabilities[i],
    )

    direction = classes[best_position]
    confidence = float(probabilities[best_position])

    if direction not in ("LONG", "SHORT"):
        return "NONE", confidence

    if confidence < PREDICTION_THRESHOLD:
        return "NONE", confidence

    return direction, confidence


# ============================================================================
# EVENT-LEVEL EVALUATION
# ============================================================================

def evaluate_symbol(
    symbol: str,
    trend_rows,
    execution_rows,
):

    if len(trend_rows) < TREND_WINDOW + 30:
        print(
            f"{symbol}: SKIP "
            f"(30m candles={len(trend_rows)})"
        )
        return None

    times = [
        _dt(row["timestamp"])
        for row in trend_rows
    ]

    closes = [
        _safe_float(row["close"])
        for row in trend_rows
    ]

    volumes = [
        _safe_float(row.get("volume", 0.0))
        for row in trend_rows
    ]

    states = build_states(closes)

    rsi_values = rsi_wilder(closes)

    transitions = find_transitions(
        states,
        times,
        closes,
    )

    # Score each actual transition first.
    for event in transitions:
        outcome, mfe, mae = score_transition_outcome(
            event,
            execution_rows,
        )

        event.outcome = outcome
        event.mfe_pct = mfe
        event.mae_pct = mae

    X, y, indices = build_training_dataset(
        closes,
        volumes,
        states,
        rsi_values,
        transitions,
    )

    feature_by_index = {
        idx: features
        for idx, features in zip(indices, X)
    }

    # ------------------------------------------------------------
    # Find the earliest prediction for each transition.
    #
    # We scan each transition's preceding window independently.
    # This is the key V2 correction: one event gets one prediction.
    # ------------------------------------------------------------

    recognized = []

    used_prediction_indices = set()

    for event in transitions:

        start = max(
            TREND_WINDOW + 12,
            event.index - EARLY_WINDOW_BARS,
        )

        end = event.index - 1

        if end < start:
            continue

        best_prediction = None

        for prediction_index in range(start, end + 1):

            if prediction_index not in feature_by_index:
                continue

            # Prevent one prediction from being assigned to multiple
            # nearby transition events.
            if prediction_index in used_prediction_indices:
                continue

            model = train_model(
                X,
                y,
                indices,
                prediction_index,
            )

            if model is None:
                continue

            direction, confidence = model_prediction(
                model,
                feature_by_index[prediction_index],
            )

            if direction != event.direction:
                continue

            # Earliest valid prediction wins.
            best_prediction = (
                prediction_index,
                direction,
                confidence,
            )
            break

        if best_prediction is None:
            continue

        prediction_index, direction, confidence = best_prediction

        used_prediction_indices.add(prediction_index)

        event.prediction_index = prediction_index
        event.prediction_time = times[prediction_index]
        event.prediction_direction = direction
        event.prediction_confidence = confidence
        event.lead_bars = event.index - prediction_index

        recognized.append(event)

    return {
        "symbol": symbol,
        "candles": len(trend_rows),
        "transitions": transitions,
        "recognized": recognized,
        "predictions_total": len(recognized),
        "features": feature_names(),
    }


# ============================================================================
# REPORTING
# ============================================================================

def _print_event_examples(events: List[TransitionEvent], limit: int = 15):

    print()
    print("RECOGNIZED TRANSITION EXAMPLES")
    print("-" * 100)

    for event in events[:limit]:

        print(
            f"{event.prediction_time} | "
            f"{event.from_state}->{event.to_state} | "
            f"predicted={event.prediction_direction} | "
            f"lead={event.lead_bars} bars | "
            f"confidence={event.prediction_confidence * 100:.1f}% | "
            f"outcome={event.outcome} | "
            f"MFE={event.mfe_pct:.2f}% | "
            f"MAE={event.mae_pct:.2f}%"
        )


def summarize_symbol(result):

    if result is None:
        return

    symbol = result["symbol"]
    transitions = result["transitions"]
    recognized = result["recognized"]

    total = len(transitions)

    long_events = [
        e for e in transitions
        if e.direction == "LONG"
    ]

    short_events = [
        e for e in transitions
        if e.direction == "SHORT"
    ]

    recognized_long = [
        e for e in recognized
        if e.direction == "LONG"
    ]

    recognized_short = [
        e for e in recognized
        if e.direction == "SHORT"
    ]

    leads = [
        e.lead_bars
        for e in recognized
        if e.lead_bars is not None
    ]

    avg_lead = (
        sum(leads) / len(leads)
        if leads
        else 0.0
    )

    outcomes = Counter(
        e.outcome
        for e in recognized
    )

    print()
    print("=" * 80)
    print(f"AATA TRANSITION RECOGNITION V2 — {symbol}")
    print("=" * 80)

    print(f"30m candles:             {result['candles']}")
    print(f"Existing transitions:    {total}")
    print(f"LONG transitions:        {len(long_events)}")
    print(f"SHORT transitions:       {len(short_events)}")
    print(f"Recognized events:       {len(recognized)}")

    if total:
        print(
            f"Recognition rate:        "
            f"{len(recognized) / total * 100:.1f}%"
        )

    print(
        f"LONG recognized:         "
        f"{len(recognized_long)}/{len(long_events)}"
    )

    print(
        f"SHORT recognized:        "
        f"{len(recognized_short)}/{len(short_events)}"
    )

    print(
        f"Average lead:            "
        f"{avg_lead:.2f} x 30m"
    )

    if leads:
        print(
            f"Maximum lead:            "
            f"{max(leads):.2f} x 30m"
        )

    print()
    print("RECOGNIZED OUTCOMES")
    print("-" * 80)

    for label in ("REAL", "WEAK", "FALSE", "UNKNOWN"):
        count = outcomes.get(label, 0)

        pct = (
            count / len(recognized) * 100.0
            if recognized
            else 0.0
        )

        print(
            f"{label:<10} "
            f"{count:>4} "
            f"{pct:>6.1f}%"
        )

    _print_event_examples(recognized)


def combined_summary(results):

    all_transitions = []
    all_recognized = []

    for result in results:
        all_transitions.extend(
            result["transitions"]
        )

        all_recognized.extend(
            result["recognized"]
        )

    total = len(all_transitions)
    recognized = len(all_recognized)

    leads = [
        e.lead_bars
        for e in all_recognized
        if e.lead_bars is not None
    ]

    outcomes = Counter(
        e.outcome
        for e in all_recognized
    )

    print()
    print("=" * 80)
    print("AATA TRANSITION RECOGNITION V2 — COMBINED SUMMARY")
    print("=" * 80)

    print(
        f"Symbols tested:          {len(results)}"
    )

    print(
        f"Transitions:             {total}"
    )

    print(
        f"Recognized events:       {recognized}"
    )

    print(
        f"Recognition rate:        "
        f"{recognized / total * 100:.1f}%"
        if total
        else "Recognition rate:        0.0%"
    )

    print(
        f"Average lead:            "
        f"{sum(leads) / len(leads):.2f} x 30m"
        if leads
        else "Average lead:            0.00 x 30m"
    )

    print(
        f"Maximum lead:            "
        f"{max(leads):.2f} x 30m"
        if leads
        else "Maximum lead:            0.00 x 30m"
    )

    print()
    print("OUTCOME DISTRIBUTION")
    print("-" * 80)

    for label in ("REAL", "WEAK", "FALSE", "UNKNOWN"):

        count = outcomes.get(label, 0)

        pct = (
            count / recognized * 100.0
            if recognized
            else 0.0
        )

        print(
            f"{label:<10} "
            f"{count:>5} "
            f"{pct:>6.1f}%"
        )

    print()
    print("TRANSITION TYPE")
    print("-" * 80)

    transition_types = Counter(
        (e.from_state, e.to_state)
        for e in all_transitions
    )

    recognized_types = Counter(
        (e.from_state, e.to_state)
        for e in all_recognized
    )

    for transition_type, count in sorted(
        transition_types.items()
    ):

        rec = recognized_types.get(
            transition_type,
            0,
        )

        rate = (
            rec / count * 100.0
            if count
            else 0.0
        )

        print(
            f"{transition_type[0]:<5}"
            f"->{transition_type[1]:<5} "
            f"{count:>4} transitions | "
            f"{rec:>4} recognized | "
            f"{rate:>5.1f}%"
        )

    print()
    print("IMPORTANT:")
    print(
        "Do NOT change the trading engine from this research result."
    )


# ============================================================================
# MAIN
# ============================================================================

def main():

    print("=" * 80)
    print("AATA TRANSITION RECOGNITION V2")
    print("=" * 80)
    print()
    print("RESEARCH ONLY")
    print("No API")
    print("No trades")
    print("No engine changes")
    print("No DB writes")
    print()
    print("V2 EVENT-LEVEL TRANSITION TEST")
    print()
    print(
        "The model is evaluated on ONE prediction per transition event."
    )
    print(
        "Future data is used only for training labels and post-event scoring."
    )
    print()
    print(
        f"Early-recognition window: {EARLY_WINDOW_BARS} x 30m"
    )
    print(
        f"Outcome horizon:          {OUTCOME_HOURS} hours"
    )
    print(
        f"Prediction threshold:     {PREDICTION_THRESHOLD * 100:.0f}%"
    )
    print(
        f"Minimum training cases:   {MIN_TRAIN_CASES}"
    )
    print()

    results = []

    for symbol in SYMBOLS:

        try:

            trend_rows = _row_dicts(
                _db_rows(
                    symbol,
                    TREND_TIMEFRAME,
                    LIMIT,
                )
            )

            execution_rows = _row_dicts(
                _db_rows(
                    symbol,
                    EXECUTION_TIMEFRAME,
                    LIMIT * 6,
                )
            )

            result = evaluate_symbol(
                symbol,
                trend_rows,
                execution_rows,
            )

            if result is not None:
                results.append(result)
                summarize_symbol(result)

        except Exception as exc:

            print()
            print(
                f"{symbol}: ERROR: {type(exc).__name__}: {exc}"
            )

    if results:
        combined_summary(results)

    print()
    print("=" * 80)
    print("END OF AATA TRANSITION RECOGNITION V2")
    print("=" * 80)


if __name__ == "__main__":
    main()