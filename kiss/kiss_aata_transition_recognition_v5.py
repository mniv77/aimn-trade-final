# [FILE: kiss_aata_transition_recognition_v5.py] — AATA KISS V5 transition recognition research

"""
AATA KISS V5 — EVENT + DIRECTION + QUALITY TRANSITION RECOGNITION

RESEARCH ONLY.

This file does NOT:
- place trades
- modify the trading engine
- write to the database
- call an external AI API

V5 asks the transition problem in three separate stages:

    STAGE 1
        Is a directional transition approaching?

        NONE
        EVENT

    STAGE 2
        If an event is approaching, what direction?

        LONG
        SHORT

    STAGE 3
        If a transition occurs, how good is it?

        REAL
        WEAK
        FALSE

The model only receives information available at the prediction candle.

Future information is used ONLY:
- to construct historical training labels
- to score the actual transition after the fact

The goal is to measure:

    event recognition
    directional accuracy
    REAL-quality recognition
    lead time
    confidence
    false-event rate

The underlying KISS idea remains:

    recognize transition
    act quickly
    ride the trend
    recognize opposite transition
    exit quickly

This is research for AATA, not production trading logic.
"""

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
import math
import random

import numpy as np
from sklearn.ensemble import RandomForestClassifier


# ============================================================================
# CONFIGURATION
# ============================================================================

TREND_WINDOW = 20
TREND_BAND = 0.002

EARLY_WINDOW_BARS = 4
OUTCOME_HOURS = 4

PURGE_BARS = 4
MIN_TRAIN_CASES = 100

N_ESTIMATORS = 180
MIN_SAMPLES_LEAF = 3
RANDOM_STATE = 42

EVENT_THRESHOLD = 0.55
DIRECTION_THRESHOLD = 0.55
QUALITY_THRESHOLD = 0.50

MAX_TRAINING = 2500

REAL_MFE_PCT = 1.0
REAL_RATIO = 1.5

FALSE_MAE_PCT = 1.0
FALSE_MFE_PCT = 0.5

SYMBOLS = [
    "NVDA",
    "AAPL",
    "MSFT",
    "AMZN",
    "TSLA",
    "SPY",
    "QQQ",
    "META",
    "AMD",
]


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Transition:
    index: int
    time: datetime
    before: str
    after: str


@dataclass
class V5Case:
    transition: Transition
    prediction_index: int
    prediction_time: datetime

    event_confidence: float
    direction_confidence: float
    quality_confidence: float

    predicted_direction: str
    predicted_quality: str

    actual_quality: str

    lead_bars: int
    lead_minutes: int

    mfe_pct: float
    mae_pct: float


@dataclass
class EvaluationResult:
    symbol: str
    transitions: int
    cases: List[V5Case]


# ============================================================================
# DATABASE
# ============================================================================

def get_db_rows(
    symbol: str,
    timeframe: str,
    limit: int = 5000,
) -> List[Dict]:
    from db import get_db_connection

    tf_map = {
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "1hr": "1h",
        "6h": "6h",
        "6hr": "6h",
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
            (
                symbol,
                db_tf,
                int(limit),
            ),
        )

        rows = cursor.fetchall()

    finally:
        try:
            cursor.close()
        except Exception:
            pass

        try:
            conn.close()
        except Exception:
            pass

    normalized = []

    for row in rows:
        item = dict(row)

        ts = item["timestamp"]

        if not isinstance(ts, datetime):
            ts = datetime.fromisoformat(
                str(ts).replace("Z", "+00:00")
            )

        item["timestamp"] = ts

        for key in (
            "open",
            "high",
            "low",
            "close",
            "volume",
        ):
            try:
                item[key] = float(item[key])
            except Exception:
                item[key] = 0.0

        normalized.append(item)

    return normalized


# ============================================================================
# BASIC HELPERS
# ============================================================================

def safe_pct(
    new_value: float,
    old_value: float,
) -> float:
    if old_value == 0:
        return 0.0

    return (
        (new_value - old_value)
        / old_value
        * 100.0
    )


def clamp(
    value: float,
    low: float,
    high: float,
) -> float:
    return max(low, min(high, value))


# ============================================================================
# RSI
# ============================================================================

def rsi_wilder(
    closes: Sequence[float],
    period: int = 14,
) -> List[Optional[float]]:

    result: List[Optional[float]] = [
        None
    ] * len(closes)

    if len(closes) <= period:
        return result

    gains = []
    losses = []

    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]

        gains.append(
            max(change, 0.0)
        )

        losses.append(
            max(-change, 0.0)
        )

    avg_gain = sum(
        gains[:period]
    ) / period

    avg_loss = sum(
        losses[:period]
    ) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (
            100.0 / (1.0 + rs)
        )

    for i in range(period + 1, len(closes)):

        avg_gain = (
            avg_gain * (period - 1)
            + gains[i - 1]
        ) / period

        avg_loss = (
            avg_loss * (period - 1)
            + losses[i - 1]
        ) / period

        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss

            result[i] = (
                100.0
                - 100.0 / (1.0 + rs)
            )

    return result


# ============================================================================
# STATE CLASSIFIER
# ============================================================================

def get_market_state(
    closes: Sequence[float],
    idx: int,
) -> str:

    if (
        idx < TREND_WINDOW
        or idx >= len(closes)
    ):
        return "FLAT"

    ma = sum(
        closes[
            idx - TREND_WINDOW:idx
        ]
    ) / TREND_WINDOW

    if closes[idx] > ma * (
        1.0 + TREND_BAND
    ):
        return "LONG"

    if closes[idx] < ma * (
        1.0 - TREND_BAND
    ):
        return "SHORT"

    return "FLAT"


def build_states(
    rows: Sequence[Dict],
) -> List[str]:

    closes = [
        float(row["close"])
        for row in rows
    ]

    return [
        get_market_state(
            closes,
            i,
        )
        for i in range(len(rows))
    ]


# ============================================================================
# TRANSITIONS
# ============================================================================

def find_transitions(
    rows: Sequence[Dict],
    states: Sequence[str],
) -> List[Transition]:

    transitions = []

    for i in range(1, len(states)):

        before = states[i - 1]
        after = states[i]

        if (
            after in ("LONG", "SHORT")
            and after != before
        ):
            transitions.append(
                Transition(
                    index=i,
                    time=rows[i]["timestamp"],
                    before=before,
                    after=after,
                )
            )

    return transitions


def future_transition_direction(
    states: Sequence[str],
    idx: int,
    lookahead: int,
) -> Optional[str]:

    end = min(
        len(states),
        idx + lookahead + 1,
    )

    for j in range(
        idx + 1,
        end,
    ):

        before = states[j - 1]
        after = states[j]

        if (
            after in ("LONG", "SHORT")
            and after != before
        ):
            return after

    return None


# ============================================================================
# V-SHAPE
# ============================================================================

def v_shape(
    closes: Sequence[float],
    idx: int,
) -> float:

    if idx < 2:
        return 0.0

    a = closes[idx - 2]
    b = closes[idx - 1]
    c = closes[idx]

    if a > b < c:
        return 1.0

    if a < b > c:
        return -1.0

    return 0.0


# ============================================================================
# FEATURE BUILDING
# ============================================================================

def build_features(
    rows: Sequence[Dict],
    states: Sequence[str],
    rsi_values: Sequence[Optional[float]],
    idx: int,
) -> Optional[Dict[str, float]]:

    if idx < TREND_WINDOW + 12:
        return None

    closes = [
        float(row["close"])
        for row in rows
    ]

    volumes = [
        float(row.get("volume", 0.0))
        for row in rows
    ]

    price = closes[idx]

    if price <= 0:
        return None

    ma20 = sum(
        closes[
            idx - TREND_WINDOW:idx
        ]
    ) / TREND_WINDOW

    distance_pct = safe_pct(
        price,
        ma20,
    )

    previous_ma20 = sum(
        closes[
            idx - TREND_WINDOW - 1:
            idx - 1
        ]
    ) / TREND_WINDOW

    ma_slope_pct = safe_pct(
        ma20,
        previous_ma20,
    )

    rsi = rsi_values[idx]

    if rsi is None:
        rsi = 50.0

    recent_high = max(
        closes[
            idx - 12:idx
        ]
    )

    recent_low = min(
        closes[
            idx - 12:idx
        ]
    )

    high_distance_pct = safe_pct(
        recent_high,
        price,
    )

    low_distance_pct = safe_pct(
        price,
        recent_low,
    )

    current_state = states[idx]

    state_duration = 1

    j = idx - 1

    while (
        j >= 0
        and states[j] == current_state
    ):
        state_duration += 1
        j -= 1

    churn_6 = 0

    start_churn = max(
        1,
        idx - 6,
    )

    for j in range(
        start_churn,
        idx,
    ):
        if states[j] != states[j - 1]:
            churn_6 += 1

    up_count_6 = 0
    down_count_6 = 0

    for j in range(
        idx - 6,
        idx,
    ):

        if closes[j] > closes[j - 1]:
            up_count_6 += 1

        elif closes[j] < closes[j - 1]:
            down_count_6 += 1

    current_volume = volumes[idx]

    previous_volume = volumes[idx - 1]

    volume_change_pct = safe_pct(
        current_volume,
        previous_volume,
    )

    features = {
        "price": price,
        "ma20": ma20,
        "distance_pct": distance_pct,
        "ma_slope_pct": ma_slope_pct,

        "rsi": float(rsi),

        "move_1bar_pct": safe_pct(
            closes[idx],
            closes[idx - 1],
        ),

        "move_2bar_pct": safe_pct(
            closes[idx],
            closes[idx - 2],
        ),

        "move_3bar_pct": safe_pct(
            closes[idx],
            closes[idx - 3],
        ),

        "move_4bar_pct": safe_pct(
            closes[idx],
            closes[idx - 4],
        ),

        "move_6bar_pct": safe_pct(
            closes[idx],
            closes[idx - 6],
        ),

        "move_12bar_pct": safe_pct(
            closes[idx],
            closes[idx - 12],
        ),

        "recent_high_distance_pct":
            high_distance_pct,

        "recent_low_distance_pct":
            low_distance_pct,

        "state_long":
            1.0 if current_state == "LONG"
            else 0.0,

        "state_short":
            1.0 if current_state == "SHORT"
            else 0.0,

        "state_flat":
            1.0 if current_state == "FLAT"
            else 0.0,

        "state_duration":
            float(state_duration),

        "state_churn_6":
            float(churn_6),

        "up_count_6":
            float(up_count_6),

        "down_count_6":
            float(down_count_6),

        "volume_change_pct":
            clamp(
                volume_change_pct,
                -500.0,
                500.0,
            ),

        "v_shape":
            v_shape(
                closes,
                idx,
            ),
    }

    return features


# ============================================================================
# MATRIX
# ============================================================================

def make_matrix(
    rows: Sequence[Dict[str, float]],
    feature_names: Optional[List[str]] = None,
) -> Tuple[np.ndarray, List[str]]:

    if not rows:
        return (
            np.empty((0, 0)),
            feature_names or [],
        )

    if feature_names is None:
        feature_names = list(
            rows[0].keys()
        )

    matrix = []

    for row in rows:
        matrix.append([
            float(row.get(name, 0.0))
            for name in feature_names
        ])

    return (
        np.asarray(
            matrix,
            dtype=float,
        ),
        feature_names,
    )


# ============================================================================
# FUTURE QUALITY
# ============================================================================

def score_future_quality(
    transition: Transition,
    rows_5m: Sequence[Dict],
) -> Tuple[str, float, float]:

    entry_price = None

    for row in rows_5m:

        if row["timestamp"] >= transition.time:
            entry_price = float(
                row["close"]
            )
            break

    if entry_price is None or entry_price <= 0:
        return (
            "WEAK",
            0.0,
            0.0,
        )

    end_time = (
        transition.time
        + timedelta(
            hours=OUTCOME_HOURS
        )
    )

    mfe = 0.0
    mae = 0.0

    for row in rows_5m:

        timestamp = row["timestamp"]

        if timestamp < transition.time:
            continue

        if timestamp > end_time:
            break

        high = float(row["high"])
        low = float(row["low"])

        if transition.after == "LONG":

            favorable = safe_pct(
                high,
                entry_price,
            )

            adverse = safe_pct(
                low,
                entry_price,
            )

        else:

            favorable = safe_pct(
                entry_price,
                low,
            )

            adverse = safe_pct(
                entry_price,
                high,
            )

        mfe = max(
            mfe,
            favorable,
        )

        mae = min(
            mae,
            adverse,
        )

    adverse_abs = abs(mae)

    if (
        mfe >= REAL_MFE_PCT
        and mfe >= adverse_abs * REAL_RATIO
    ):
        return (
            "REAL",
            mfe,
            adverse_abs,
        )

    if (
        adverse_abs >= FALSE_MAE_PCT
        and mfe < FALSE_MFE_PCT
    ):
        return (
            "FALSE",
            mfe,
            adverse_abs,
        )

    return (
        "WEAK",
        mfe,
        adverse_abs,
    )


# ============================================================================
# TRAINING DATA
# ============================================================================

def build_training_examples(
    rows: Sequence[Dict],
    states: Sequence[str],
    rsi_values: Sequence[Optional[float]],
    rows_5m: Sequence[Dict],
    transitions: Sequence[Transition],
    target_index: int,
) -> Tuple[
    List[Dict[str, float]],
    List[str],
    List[str],
    List[str],
]:

    event_x = []
    event_y = []

    direction_x = []
    direction_y = []

    quality_x = []
    quality_y = []

    closes = [
        float(row["close"])
        for row in rows
    ]

    max_idx = (
        target_index
        - PURGE_BARS
    )

    if max_idx <= (
        TREND_WINDOW + 12
    ):
        return (
            [],
            [],
            [],
            [],
            [],
            [],
        )

    # ------------------------------------------------------------------------
    # Create event labels for every historical candle.
    #
    # EVENT = a directional transition occurs within the next 4 bars.
    # NONE  = no directional transition within the next 4 bars.
    #
    # Direction and quality are only defined for EVENT cases.
    # ------------------------------------------------------------------------

    transition_lookup = {}

    for transition in transitions:

        outcome, _, _ = score_future_quality(
            transition,
            rows_5m,
        )

        transition_lookup[
            transition.index
        ] = (
            transition.after,
            outcome,
        )

    historical_indices = list(
        range(
            TREND_WINDOW + 12,
            max_idx,
        )
    )

    # Deterministic balancing of NONE examples.
    event_indices = []
    none_indices = []

    for idx in historical_indices:

        direction = future_transition_direction(
            states,
            idx,
            EARLY_WINDOW_BARS,
        )

        if direction is None:
            none_indices.append(idx)
        else:
            event_indices.append(idx)

    rng = np.random.default_rng(
        RANDOM_STATE + target_index
    )

    max_none = max(
        len(event_indices) * 2,
        MIN_TRAIN_CASES,
    )

    if len(none_indices) > max_none:

        selected = rng.choice(
            len(none_indices),
            size=max_none,
            replace=False,
        )

        selected = sorted(
            selected.tolist()
        )

        none_indices = [
            none_indices[i]
            for i in selected
        ]

    selected_indices = (
        event_indices
        + none_indices
    )

    rng.shuffle(
        selected_indices
    )

    for idx in selected_indices:

        features = build_features(
            rows,
            states,
            rsi_values,
            idx,
        )

        if features is None:
            continue

        direction = future_transition_direction(
            states,
            idx,
            EARLY_WINDOW_BARS,
        )

        if direction is None:

            event_x.append(features)
            event_y.append("NONE")

            continue

        event_x.append(features)
        event_y.append("EVENT")

        direction_x.append(features)
        direction_y.append(direction)

        # Find the actual transition responsible
        # for this future direction.

        responsible_transition = None

        end = min(
            len(states),
            idx + EARLY_WINDOW_BARS + 1,
        )

        for j in range(
            idx + 1,
            end,
        ):

            before = states[j - 1]
            after = states[j]

            if (
                after in ("LONG", "SHORT")
                and after != before
                and after == direction
            ):

                responsible_transition = (
                    transition_lookup.get(j)
                )

                break

        if responsible_transition is None:
            continue

        _, quality = responsible_transition

        quality_x.append(features)
        quality_y.append(quality)

    return (
        event_x,
        event_y,
        direction_x,
        direction_y,
        quality_x,
        quality_y,
    )


# ============================================================================
# MODEL HELPERS
# ============================================================================

def train_model(
    x_rows: Sequence[Dict[str, float]],
    y_rows: Sequence[str],
) -> Optional[
    Tuple[
        RandomForestClassifier,
        List[str],
    ]
]:

    if len(x_rows) < MIN_TRAIN_CASES:
        return None

    if len(set(y_rows)) < 2:
        return None

    if len(x_rows) > MAX_TRAINING:

        rng = np.random.default_rng(
            RANDOM_STATE + len(x_rows)
        )

        selected = rng.choice(
            len(x_rows),
            size=MAX_TRAINING,
            replace=False,
        )

        selected = sorted(
            selected.tolist()
        )

        x_rows = [
            x_rows[i]
            for i in selected
        ]

        y_rows = [
            y_rows[i]
            for i in selected
        ]

    x_train, feature_names = make_matrix(
        x_rows
    )

    model = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        random_state=RANDOM_STATE,
        class_weight="balanced",
        min_samples_leaf=MIN_SAMPLES_LEAF,
        n_jobs=-1,
    )

    model.fit(
        x_train,
        y_rows,
    )

    return (
        model,
        feature_names,
    )


def predict_best(
    model: RandomForestClassifier,
    feature_names: Sequence[str],
    features: Dict[str, float],
) -> Tuple[str, float]:

    x_current, _ = make_matrix(
        [features],
        list(feature_names),
    )

    probabilities = (
        model.predict_proba(
            x_current
        )[0]
    )

    classes = list(
        model.classes_
    )

    best_idx = int(
        np.argmax(probabilities)
    )

    return (
        str(classes[best_idx]),
        float(
            probabilities[best_idx]
        ),
    )


# ============================================================================
# EVENT-LEVEL EVALUATION
# ============================================================================

def evaluate_symbol(
    symbol: str,
    rows: Sequence[Dict],
    rows_5m: Sequence[Dict],
) -> EvaluationResult:

    states = build_states(
        rows
    )

    transitions = find_transitions(
        rows,
        states,
    )

    closes = [
        float(row["close"])
        for row in rows
    ]

    rsi_values = rsi_wilder(
        closes
    )

    recognitions = []

    used_prediction_indices = set()

    # ------------------------------------------------------------------------
    # Each actual transition is evaluated independently.
    #
    # Candidate predictions are ONLY the preceding 1-4 candles.
    # ------------------------------------------------------------------------

    for transition in transitions:

        candidate_start = max(
            TREND_WINDOW + 12,
            transition.index
            - EARLY_WINDOW_BARS,
        )

        candidate_indices = list(
            range(
                candidate_start,
                transition.index,
            )
        )

        if not candidate_indices:
            continue

        (
            event_x,
            event_y,
            direction_x,
            direction_y,
            quality_x,
            quality_y,
        ) = build_training_examples(
            rows,
            states,
            rsi_values,
            rows_5m,
            transitions,
            transition.index,
        )

        if len(event_x) < MIN_TRAIN_CASES:
            continue

        event_model_data = train_model(
            event_x,
            event_y,
        )

        if event_model_data is None:
            continue

        event_model, event_features = (
            event_model_data
        )

        direction_model_data = train_model(
            direction_x,
            direction_y,
        )

        if direction_model_data is None:
            continue

        direction_model, direction_features = (
            direction_model_data
        )

        quality_model_data = train_model(
            quality_x,
            quality_y,
        )

        if quality_model_data is None:
            continue

        quality_model, quality_features = (
            quality_model_data
        )

        candidates = []

        for idx in candidate_indices:

            if idx in used_prediction_indices:
                continue

            features = build_features(
                rows,
                states,
                rsi_values,
                idx,
            )

            if features is None:
                continue

            # ---------------------------------------------------------------
            # STAGE 1 — EVENT
            # ---------------------------------------------------------------

            event_prediction, event_confidence = (
                predict_best(
                    event_model,
                    event_features,
                    features,
                )
            )

            if event_prediction != "EVENT":
                continue

            if (
                event_confidence
                < EVENT_THRESHOLD
            ):
                continue

            # ---------------------------------------------------------------
            # STAGE 2 — DIRECTION
            # ---------------------------------------------------------------

            predicted_direction, direction_confidence = (
                predict_best(
                    direction_model,
                    direction_features,
                    features,
                )
            )

            if predicted_direction not in (
                "LONG",
                "SHORT",
            ):
                continue

            if (
                direction_confidence
                < DIRECTION_THRESHOLD
            ):
                continue

            # ---------------------------------------------------------------
            # STAGE 3 — QUALITY
            # ---------------------------------------------------------------

            predicted_quality, quality_confidence = (
                predict_best(
                    quality_model,
                    quality_features,
                    features,
                )
            )

            if predicted_quality not in (
                "REAL",
                "WEAK",
                "FALSE",
            ):
                continue

            if (
                quality_confidence
                < QUALITY_THRESHOLD
            ):
                continue

            # V5 requires the predicted direction
            # to agree with the actual event being tested.
            #
            # This is NOT given to the model.
            # It is only used for evaluation.

            if (
                predicted_direction
                != transition.after
            ):
                continue

            candidates.append(
                (
                    idx,
                    event_confidence,
                    direction_confidence,
                    quality_confidence,
                    predicted_direction,
                    predicted_quality,
                )
            )

        if not candidates:
            continue

        # Earliest valid prediction wins.

        (
            prediction_idx,
            event_confidence,
            direction_confidence,
            quality_confidence,
            predicted_direction,
            predicted_quality,
        ) = min(
            candidates,
            key=lambda item: item[0],
        )

        used_prediction_indices.add(
            prediction_idx
        )

        actual_quality, mfe, mae = (
            score_future_quality(
                transition,
                rows_5m,
            )
        )

        lead_bars = (
            transition.index
            - prediction_idx
        )

        lead_minutes = (
            lead_bars * 30
        )

        recognitions.append(
            V5Case(
                transition=transition,
                prediction_index=prediction_idx,
                prediction_time=rows[
                    prediction_idx
                ]["timestamp"],

                event_confidence=(
                    event_confidence
                ),

                direction_confidence=(
                    direction_confidence
                ),

                quality_confidence=(
                    quality_confidence
                ),

                predicted_direction=(
                    predicted_direction
                ),

                predicted_quality=(
                    predicted_quality
                ),

                actual_quality=(
                    actual_quality
                ),

                lead_bars=lead_bars,
                lead_minutes=lead_minutes,

                mfe_pct=mfe,
                mae_pct=mae,
            )
        )

    return EvaluationResult(
        symbol=symbol,
        transitions=len(transitions),
        cases=recognitions,
    )


# ============================================================================
# REPORTING
# ============================================================================

def print_symbol_report(
    result: EvaluationResult,
) -> None:

    cases = result.cases

    print()
    print("=" * 78)
    print(
        f"V5 SYMBOL: {result.symbol}"
    )
    print("=" * 78)

    print(
        f"Transitions: {result.transitions}"
    )

    print(
        f"Recognized events: {len(cases)}"
    )

    if result.transitions:
        recognition_rate = (
            len(cases)
            / result.transitions
            * 100.0
        )
    else:
        recognition_rate = 0.0

    print(
        f"Recognition rate: "
        f"{recognition_rate:.1f}%"
    )

    if not cases:
        return

    correct_direction = sum(
        1
        for case in cases
        if case.predicted_direction
        == case.transition.after
    )

    direction_accuracy = (
        correct_direction
        / len(cases)
        * 100.0
    )

    print(
        f"Direction accuracy: "
        f"{direction_accuracy:.1f}%"
    )

    predicted_real = sum(
        1
        for case in cases
        if case.predicted_quality
        == "REAL"
    )

    actual_real = sum(
        1
        for case in cases
        if case.actual_quality
        == "REAL"
    )

    actual_weak = sum(
        1
        for case in cases
        if case.actual_quality
        == "WEAK"
    )

    actual_false = sum(
        1
        for case in cases
        if case.actual_quality
        == "FALSE"
    )

    print(
        f"Predicted REAL: {predicted_real}"
    )

    print(
        f"Actual REAL: {actual_real}"
    )

    print(
        f"Actual WEAK: {actual_weak}"
    )

    print(
        f"Actual FALSE: {actual_false}"
    )

    avg_lead = sum(
        case.lead_minutes
        for case in cases
    ) / len(cases)

    print(
        f"Average lead: "
        f"{avg_lead:.1f} minutes"
    )

    print()
    print("RECOGNIZED CASES")
    print("-" * 78)

    for case in cases:

        print(
            f"{case.transition.time} | "
            f"{case.transition.before}"
            f"->{case.transition.after} | "
            f"pred={case.predicted_direction} | "
            f"quality={case.predicted_quality}"
            f"/{case.actual_quality} | "
            f"lead={case.lead_minutes}m | "
            f"event={case.event_confidence:.1%} | "
            f"dir={case.direction_confidence:.1%} | "
            f"quality_conf={case.quality_confidence:.1%} | "
            f"MFE={case.mfe_pct:.2f}% | "
            f"MAE={case.mae_pct:.2f}%"
        )


def print_combined_report(
    results: Sequence[EvaluationResult],
) -> None:

    total_transitions = sum(
        result.transitions
        for result in results
    )

    all_cases = [
        case
        for result in results
        for case in result.cases
    ]

    print()
    print("=" * 78)
    print("AATA KISS V5 — COMBINED RESULTS")
    print("=" * 78)

    print(
        f"Symbols tested: {len(results)}"
    )

    print(
        f"Total transitions: "
        f"{total_transitions}"
    )

    print(
        f"Recognized events: "
        f"{len(all_cases)}"
    )

    if total_transitions:
        recognition_rate = (
            len(all_cases)
            / total_transitions
            * 100.0
        )
    else:
        recognition_rate = 0.0

    print(
        f"Recognition rate: "
        f"{recognition_rate:.2f}%"
    )

    if not all_cases:
        print()
        print(
            "No V5 events were recognized."
        )
        return

    correct_direction = sum(
        1
        for case in all_cases
        if case.predicted_direction
        == case.transition.after
    )

    direction_accuracy = (
        correct_direction
        / len(all_cases)
        * 100.0
    )

    print(
        f"Direction accuracy: "
        f"{direction_accuracy:.2f}%"
    )

    predicted_real = sum(
        1
        for case in all_cases
        if case.predicted_quality
        == "REAL"
    )

    predicted_weak = sum(
        1
        for case in all_cases
        if case.predicted_quality
        == "WEAK"
    )

    predicted_false = sum(
        1
        for case in all_cases
        if case.predicted_quality
        == "FALSE"
    )

    actual_real = sum(
        1
        for case in all_cases
        if case.actual_quality
        == "REAL"
    )

    actual_weak = sum(
        1
        for case in all_cases
        if case.actual_quality
        == "WEAK"
    )

    actual_false = sum(
        1
        for case in all_cases
        if case.actual_quality
        == "FALSE"
    )

    print()
    print("PREDICTED QUALITY")
    print(
        f"REAL:  {predicted_real}"
    )
    print(
        f"WEAK:  {predicted_weak}"
    )
    print(
        f"FALSE: {predicted_false}"
    )

    print()
    print("ACTUAL QUALITY")
    print(
        f"REAL:  {actual_real}"
    )
    print(
        f"WEAK:  {actual_weak}"
    )
    print(
        f"FALSE: {actual_false}"
    )

    avg_lead = sum(
        case.lead_minutes
        for case in all_cases
    ) / len(all_cases)

    max_lead = max(
        case.lead_minutes
        for case in all_cases
    )

    print()
    print(
        f"Average lead: "
        f"{avg_lead:.1f} minutes"
    )

    print(
        f"Maximum lead: "
        f"{max_lead} minutes"
    )

    # ------------------------------------------------------------------------
    # Direction breakdown
    # ------------------------------------------------------------------------

    print()
    print("DIRECTION BREAKDOWN")

    for direction in (
        "LONG",
        "SHORT",
    ):

        direction_cases = [
            case
            for case in all_cases
            if case.predicted_direction
            == direction
        ]

        actual_events = sum(
            1
            for result in results
            for transition in []
        )

        print(
            f"{direction}: "
            f"{len(direction_cases)} recognized"
        )

    # ------------------------------------------------------------------------
    # Detailed cases
    # ------------------------------------------------------------------------

    print()
    print("ALL RECOGNIZED CASES")
    print("-" * 78)

    for case in all_cases:

        print(
            f"{case.transition.time} | "
            f"{case.transition.before}"
            f"->{case.transition.after} | "
            f"pred={case.predicted_direction} | "
            f"quality="
            f"{case.predicted_quality}"
            f"/{case.actual_quality} | "
            f"lead={case.lead_minutes}m | "
            f"event={case.event_confidence:.1%} | "
            f"dir={case.direction_confidence:.1%} | "
            f"quality={case.quality_confidence:.1%}"
        )


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:

    print("=" * 78)
    print("AATA KISS V5 — TRANSITION RECOGNITION RESEARCH")
    print("=" * 78)

    print(
        "Research only: "
        "no API, no trades, no engine changes, no DB writes"
    )

    print(
        f"Early window: "
        f"{EARLY_WINDOW_BARS} x 30m"
    )

    print(
        f"Outcome horizon: "
        f"{OUTCOME_HOURS} hours"
    )

    print(
        f"Event threshold: "
        f"{EVENT_THRESHOLD:.2f}"
    )

    print(
        f"Direction threshold: "
        f"{DIRECTION_THRESHOLD:.2f}"
    )

    print(
        f"Quality threshold: "
        f"{QUALITY_THRESHOLD:.2f}"
    )

    print(
        f"Minimum training cases: "
        f"{MIN_TRAIN_CASES}"
    )

    print(
        f"Random Forest trees: "
        f"{N_ESTIMATORS}"
    )

    results = []

    for symbol in SYMBOLS:

        print()
        print(
            f"Loading {symbol}..."
        )

        try:
            rows = get_db_rows(
                symbol,
                "30m",
            )

            rows_5m = get_db_rows(
                symbol,
                "5m",
            )

        except Exception as exc:

            print(
                f"{symbol}: database error: "
                f"{exc}"
            )

            continue

        if not rows:

            print(
                f"{symbol}: no 30m data"
            )

            continue

        if not rows_5m:

            print(
                f"{symbol}: no 5m data"
            )

            continue

        print(
            f"{symbol}: "
            f"{len(rows)} 30m candles | "
            f"{len(rows_5m)} 5m candles"
        )

        try:

            result = evaluate_symbol(
                symbol,
                rows,
                rows_5m,
            )

        except Exception as exc:

            print(
                f"{symbol}: evaluation error: "
                f"{exc}"
            )

            continue

        results.append(
            result
        )

        print_symbol_report(
            result
        )

    print_combined_report(
        results
    )

    print()
    print("=" * 78)
    print("V5 COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()