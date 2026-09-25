# [FILE: kiss_aata_transition_recognition_v4.py] — AATA KISS V4 transition quality research

"""
AATA KISS V4 — TRANSITION QUALITY RECOGNITION

RESEARCH ONLY
- No API
- No trades
- No engine changes
- No DB writes

V4 GOAL
-------
V3 demonstrated that AATA can sometimes recognize a transition before
the official KISS state transition, but most recognized events were WEAK.

V4 asks the next question:

    When a transition is developing, can AATA distinguish a
    REAL transition from a WEAK or FALSE one?

IMPORTANT CAUSALITY RULE
------------------------
The model receives only information available at the prediction candle.

Future data is used ONLY to create research labels.

V4 LABELS
---------
REAL  = future movement reaches the REAL threshold
WEAK  = transition occurs but does not become a strong move
FALSE = adverse movement reaches the FALSE threshold before useful movement

MODEL
-----
A single efficient walk-forward Random Forest is trained per prediction
point rather than repeatedly training separate models for every candidate
inside every event.

The model predicts:

    REAL
    WEAK
    FALSE

The official transition direction is also supplied as a feature because
the quality question is being asked after the transition direction is
known from the current state evidence.

EARLY WINDOW
------------
A prediction is considered useful only when made 1-4 x 30m bars BEFORE
the official directional transition.

NO HINDSIGHT
------------
The model never receives MFE, MAE, future prices, future states, or
future transition labels as input.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple
import math

import numpy as np
from sklearn.ensemble import RandomForestClassifier


# =============================================================================
# CONFIGURATION
# =============================================================================

TREND_WINDOW = 20
TREND_BAND = 0.002

EARLY_WINDOW_BARS = 4
OUTCOME_HOURS = 4

MIN_TRAIN_CASES = 100
PURGE_BARS = 8

PREDICTION_THRESHOLD = 0.60

N_ESTIMATORS = 180
MIN_SAMPLES_LEAF = 4

RANDOM_STATE = 42

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


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Transition:
    index: int
    time: datetime
    before: str
    after: str


@dataclass
class QualityCase:
    transition: Transition
    prediction_index: int
    prediction_time: datetime
    confidence: float
    predicted_quality: str
    actual_quality: str
    lead_bars: int
    mfe_pct: float
    mae_pct: float


# =============================================================================
# DATABASE
# =============================================================================

def get_db_rows(symbol: str, timeframe: str, limit: int = 5000) -> List[dict]:
    from db import get_db_connection

    tf_map = {
        "5m": "5m",
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
            WHERE symbol=%s AND timeframe=%s
            ORDER BY timestamp ASC
            LIMIT %s
            """,
            (symbol, db_tf, int(limit)),
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
        if isinstance(row, dict):
            normalized.append(
                {
                    "timestamp": row["timestamp"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
            )
        else:
            normalized.append(
                {
                    "timestamp": row[0],
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
            )

    return normalized


# =============================================================================
# BASIC MARKET STATE
# =============================================================================

def get_market_state(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"

    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW

    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"

    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"

    return "FLAT"


def build_states(rows: List[dict]) -> List[str]:
    closes = [float(row["close"]) for row in rows]

    return [
        get_market_state(closes, i)
        for i in range(len(closes))
    ]


def find_transitions(
    rows: List[dict],
    states: List[str],
) -> List[Transition]:

    transitions = []

    for i in range(1, len(states)):
        before = states[i - 1]
        after = states[i]

        if before == after:
            continue

        # Only directional transitions matter for this experiment.
        if after not in ("LONG", "SHORT"):
            continue

        transitions.append(
            Transition(
                index=i,
                time=rows[i]["timestamp"],
                before=before,
                after=after,
            )
        )

    return transitions


# =============================================================================
# RSI
# =============================================================================

def rsi_wilder(
    closes: Sequence[float],
    period: int = 14,
) -> List[Optional[float]]:

    result: List[Optional[float]] = [None] * len(closes)

    if len(closes) <= period:
        return result

    gains = []
    losses = []

    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]

        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]

        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)

        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period

        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))

    return result


# =============================================================================
# HELPERS
# =============================================================================

def safe_pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0

    return ((a - b) / b) * 100.0


def state_duration(
    states: Sequence[str],
    idx: int,
) -> int:

    if idx <= 0:
        return 1

    current = states[idx]
    duration = 1

    j = idx - 1

    while j >= 0 and states[j] == current:
        duration += 1
        j -= 1

    return duration


def state_churn(
    states: Sequence[str],
    idx: int,
    window: int = 6,
) -> float:

    start = max(1, idx - window + 1)

    changes = 0

    for j in range(start, idx + 1):
        if states[j] != states[j - 1]:
            changes += 1

    return float(changes)


def v_shape(
    closes: Sequence[float],
    idx: int,
) -> str:

    if idx < 2:
        return "NONE"

    a = closes[idx - 2]
    b = closes[idx - 1]
    c = closes[idx]

    if a > b < c:
        return "LONG"

    if a < b > c:
        return "SHORT"

    return "NONE"


def up_down_counts(
    closes: Sequence[float],
    idx: int,
    window: int,
) -> Tuple[float, float]:

    start = max(1, idx - window + 1)

    up = 0
    down = 0

    for j in range(start, idx + 1):
        if closes[j] > closes[j - 1]:
            up += 1
        elif closes[j] < closes[j - 1]:
            down += 1

    return float(up), float(down)


# =============================================================================
# FEATURES
# =============================================================================

def build_features(
    rows: List[dict],
    states: List[str],
    rsi_values: List[Optional[float]],
    idx: int,
) -> Optional[Dict[str, float]]:

    if idx < TREND_WINDOW + 12:
        return None

    closes = [float(row["close"]) for row in rows]
    volumes = [float(row["volume"]) for row in rows]

    price = closes[idx]

    ma20 = sum(
        closes[idx - TREND_WINDOW:idx]
    ) / TREND_WINDOW

    distance_pct = safe_pct(price, ma20)

    previous_ma = sum(
        closes[idx - TREND_WINDOW - 1:idx - 1]
    ) / TREND_WINDOW

    ma_slope_pct = safe_pct(ma20, previous_ma)

    moves = {}

    for bars in (1, 2, 3, 4, 6, 12):
        moves[bars] = safe_pct(
            closes[idx],
            closes[idx - bars],
        )

    recent_high = max(
        closes[idx - 12:idx + 1]
    )

    recent_low = min(
        closes[idx - 12:idx + 1]
    )

    high_distance = safe_pct(price, recent_high)
    low_distance = safe_pct(price, recent_low)

    up3, down3 = up_down_counts(closes, idx, 3)
    up6, down6 = up_down_counts(closes, idx, 6)

    previous_volume = (
        sum(volumes[idx - 3:idx]) / 3.0
        if idx >= 3
        else volumes[idx]
    )

    volume_change = safe_pct(
        volumes[idx],
        previous_volume,
    )

    rsi = (
        float(rsi_values[idx])
        if rsi_values[idx] is not None
        else 50.0
    )

    current_state = states[idx]

    features = {
        # Current state encoding
        "state_long": 1.0 if current_state == "LONG" else 0.0,
        "state_short": 1.0 if current_state == "SHORT" else 0.0,
        "state_flat": 1.0 if current_state == "FLAT" else 0.0,

        # Price context
        "price": price,
        "ma20": ma20,
        "distance_pct": distance_pct,
        "ma_slope_pct": ma_slope_pct,

        # Momentum
        "move_1bar_pct": moves[1],
        "move_2bar_pct": moves[2],
        "move_3bar_pct": moves[3],
        "move_4bar_pct": moves[4],
        "move_6bar_pct": moves[6],
        "move_12bar_pct": moves[12],

        # Recent range position
        "recent_high_distance_pct": high_distance,
        "recent_low_distance_pct": low_distance,

        # State behavior
        "state_duration": float(
            state_duration(states, idx)
        ),
        "state_churn_6": state_churn(
            states,
            idx,
            6,
        ),

        # Candle direction balance
        "up_count_3": up3,
        "down_count_3": down3,
        "up_count_6": up6,
        "down_count_6": down6,

        # Volume context
        "volume_change_pct": volume_change,

        # RSI as context, not a buy/sell trigger
        "rsi": rsi,

        # Simple shape context
        "v_long": 1.0 if v_shape(closes, idx) == "LONG" else 0.0,
        "v_short": 1.0 if v_shape(closes, idx) == "SHORT" else 0.0,
    }

    return features


FEATURE_NAMES: Optional[List[str]] = None


def make_matrix(
    rows: List[Dict[str, float]],
) -> np.ndarray:

    global FEATURE_NAMES

    if FEATURE_NAMES is None:
        FEATURE_NAMES = list(rows[0].keys())

    return np.asarray(
        [
            [
                float(row.get(name, 0.0))
                for name in FEATURE_NAMES
            ]
            for row in rows
        ],
        dtype=float,
    )


# =============================================================================
# FUTURE LABEL — TRAINING ONLY
# =============================================================================

def future_transition_direction(
    states: Sequence[str],
    idx: int,
    lookahead: int,
) -> Optional[str]:

    end = min(
        len(states),
        idx + lookahead + 1,
    )

    for j in range(idx + 1, end):
        before = states[j - 1]
        after = states[j]

        if before == after:
            continue

        if after in ("LONG", "SHORT"):
            return after

    return None


def score_future_quality(
    transition: Transition,
    rows_5m: List[dict],
) -> Tuple[str, float, float]:

    if not rows_5m:
        return "WEAK", 0.0, 0.0

    start_time = transition.time
    end_time = start_time + timedelta(
        hours=OUTCOME_HOURS
    )

    entry_price = None

    future_rows = []

    for row in rows_5m:
        ts = row["timestamp"]

        if ts < start_time:
            continue

        if ts > end_time:
            break

        if entry_price is None:
            entry_price = float(row["open"])

        future_rows.append(row)

    if entry_price is None or not future_rows:
        return "WEAK", 0.0, 0.0

    mfe = 0.0
    mae = 0.0

    direction = transition.after

    for row in future_rows:
        high = float(row["high"])
        low = float(row["low"])

        if direction == "LONG":
            favorable = safe_pct(high, entry_price)
            adverse = safe_pct(low, entry_price)
        else:
            favorable = safe_pct(entry_price, low)
            adverse = safe_pct(entry_price, high)

        mfe = max(mfe, favorable)
        mae = max(mae, adverse)

    if (
        mfe >= REAL_MFE_PCT
        and mfe >= (mae * REAL_RATIO)
    ):
        return "REAL", mfe, mae

    if (
        mae >= FALSE_MAE_PCT
        and mfe < FALSE_MFE_PCT
    ):
        return "FALSE", mfe, mae

    return "WEAK", mfe, mae


# =============================================================================
# EFFICIENT WALK-FORWARD QUALITY MODEL
# =============================================================================

def train_quality_model(
    rows: List[dict],
    states: List[str],
    rsi_values: List[Optional[float]],
    target_idx: int,
    direction: str,
) -> Optional[Tuple[RandomForestClassifier, List[str]]]:

    train_end = target_idx - PURGE_BARS

    if train_end <= TREND_WINDOW + 20:
        return None

    train_x: List[Dict[str, float]] = []
    train_y: List[str] = []

    for idx in range(
        TREND_WINDOW + 12,
        train_end,
    ):

        historical_direction = future_transition_direction(
            states,
            idx,
            EARLY_WINDOW_BARS,
        )

        if historical_direction is None:
            continue

        features = build_features(
            rows,
            states,
            rsi_values,
            idx,
        )

        if features is None:
            continue

        # Directional candidate only:
        # quality is evaluated for transitions that actually occur.
        train_x.append(features)

        # We cannot use future outcome as a feature.
        # The actual quality label is created below from historical data.
        #
        # For efficiency, the historical transition is located and scored
        # using the 5m dataset outside this function in the main dataset
        # builder.
        #
        # Placeholder is replaced by the pre-built historical labels.
        train_y.append("WEAK")

    return None


# =============================================================================
# BUILD HISTORICAL QUALITY DATASET
# =============================================================================

def build_quality_dataset(
    rows: List[dict],
    rows_5m: List[dict],
    states: List[str],
    transitions: List[Transition],
) -> Tuple[
    List[Dict[str, float]],
    List[str],
    List[int],
]:

    closes = [float(row["close"]) for row in rows]

    rsi_values = rsi_wilder(closes)

    x_data: List[Dict[str, float]] = []
    y_data: List[str] = []
    index_data: List[int] = []

    for transition in transitions:

        start = max(
            TREND_WINDOW + 12,
            transition.index - EARLY_WINDOW_BARS,
        )

        end = transition.index

        outcome, _, _ = score_future_quality(
            transition,
            rows_5m,
        )

        for idx in range(start, end):

            features = build_features(
                rows,
                states,
                rsi_values,
                idx,
            )

            if features is None:
                continue

            x_data.append(features)
            y_data.append(outcome)
            index_data.append(idx)

    return x_data, y_data, index_data


# =============================================================================
# WALK-FORWARD EVENT EVALUATION
# =============================================================================

def evaluate_symbol(
    rows: List[dict],
    rows_5m: List[dict],
    symbol: str,
) -> List[QualityCase]:

    if len(rows) < TREND_WINDOW + 50:
        return []

    states = build_states(rows)
    transitions = find_transitions(rows, states)

    closes = [float(row["close"]) for row in rows]
    rsi_values = rsi_wilder(closes)

    # -------------------------------------------------------------------------
    # Pre-build historical examples.
    #
    # Each transition contributes only its preceding 1-4 candidate candles.
    # Future outcome is used ONLY as the training label.
    # -------------------------------------------------------------------------

    all_x: List[Dict[str, float]] = []
    all_y: List[str] = []
    all_idx: List[int] = []

    for transition in transitions:

        outcome, _, _ = score_future_quality(
            transition,
            rows_5m,
        )

        start = max(
            TREND_WINDOW + 12,
            transition.index - EARLY_WINDOW_BARS,
        )

        for idx in range(start, transition.index):

            features = build_features(
                rows,
                states,
                rsi_values,
                idx,
            )

            if features is None:
                continue

            all_x.append(features)
            all_y.append(outcome)
            all_idx.append(idx)

    if len(all_x) < MIN_TRAIN_CASES:
        return []

    recognitions: List[QualityCase] = []

    used_prediction_indices = set()

    # -------------------------------------------------------------------------
    # One model per evaluation point.
    #
    # This is still walk-forward and causal, but only one model is trained
    # for each transition rather than once for every candidate candle.
    # -------------------------------------------------------------------------

    for transition in transitions:

        candidate_start = max(
            TREND_WINDOW + 12,
            transition.index - EARLY_WINDOW_BARS,
        )

        candidate_indices = list(
            range(
                candidate_start,
                transition.index,
            )
        )

        if not candidate_indices:
            continue

        train_rows = []
        train_labels = []

        for x_row, y_label, x_idx in zip(
            all_x,
            all_y,
            all_idx,
        ):

            if x_idx >= transition.index - PURGE_BARS:
                continue

            train_rows.append(x_row)
            train_labels.append(y_label)

        if len(train_rows) < MIN_TRAIN_CASES:
            continue

        if len(set(train_labels)) < 2:
            continue

        # Limit the historical training set to avoid runaway runtime.
        max_training = 1800

        if len(train_rows) > max_training:
            rng = np.random.default_rng(
                RANDOM_STATE + transition.index
            )

            selected = rng.choice(
                len(train_rows),
                size=max_training,
                replace=False,
            )

            selected = sorted(
                selected.tolist()
            )

            train_rows = [
                train_rows[i]
                for i in selected
            ]

            train_labels = [
                train_labels[i]
                for i in selected
            ]

        x_train = make_matrix(train_rows)

        model = RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            random_state=RANDOM_STATE,
            class_weight="balanced",
            min_samples_leaf=MIN_SAMPLES_LEAF,
            n_jobs=-1,
        )

        model.fit(
            x_train,
            train_labels,
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

            x_current = make_matrix(
                [features]
            )

            probabilities = model.predict_proba(
                x_current
            )[0]

            classes = list(model.classes_)

            best_idx = int(
                np.argmax(probabilities)
            )

            predicted_quality = str(
                classes[best_idx]
            )

            confidence = float(
                probabilities[best_idx]
            )

            if confidence < PREDICTION_THRESHOLD:
                continue

            # We only accept REAL predictions.
            #
            # This is the critical V4 test:
            # can the model identify a transition that will actually
            # develop into a strong move?
            if predicted_quality != "REAL":
                continue

            candidates.append(
                (
                    idx,
                    confidence,
                )
            )

        if not candidates:
            continue

        # Earliest REAL-quality prediction wins.
        prediction_idx, confidence = min(
            candidates,
            key=lambda item: item[0],
        )

        used_prediction_indices.add(
            prediction_idx
        )

        actual_quality, mfe, mae = score_future_quality(
            transition,
            rows_5m,
        )

        lead = (
            transition.index
            - prediction_idx
        )

        recognitions.append(
            QualityCase(
                transition=transition,
                prediction_index=prediction_idx,
                prediction_time=rows[prediction_idx]["timestamp"],
                confidence=confidence,
                predicted_quality="REAL",
                actual_quality=actual_quality,
                lead_bars=lead,
                mfe_pct=mfe,
                mae_pct=mae,
            )
        )

    return recognitions


# =============================================================================
# REPORTING
# =============================================================================

def pct(value: int, total: int) -> float:
    if total == 0:
        return 0.0

    return value / total * 100.0


def print_symbol_report(
    symbol: str,
    rows: List[dict],
    transitions: List[Transition],
    cases: List[QualityCase],
) -> None:

    long_total = sum(
        1 for t in transitions
        if t.after == "LONG"
    )

    short_total = sum(
        1 for t in transitions
        if t.after == "SHORT"
    )

    long_recognized = sum(
        1 for c in cases
        if c.transition.after == "LONG"
    )

    short_recognized = sum(
        1 for c in cases
        if c.transition.after == "SHORT"
    )

    real = sum(
        1 for c in cases
        if c.actual_quality == "REAL"
    )

    weak = sum(
        1 for c in cases
        if c.actual_quality == "WEAK"
    )

    false = sum(
        1 for c in cases
        if c.actual_quality == "FALSE"
    )

    avg_lead = (
        sum(c.lead_bars for c in cases) / len(cases)
        if cases
        else 0.0
    )

    print()
    print("=" * 80)
    print(f"AATA TRANSITION RECOGNITION V4 — {symbol}")
    print("=" * 80)

    print(
        f"30m candles:             {len(rows)}"
    )

    print(
        f"Existing transitions:    {len(transitions)}"
    )

    print(
        f"LONG transitions:        {long_total}"
    )

    print(
        f"SHORT transitions:       {short_total}"
    )

    print(
        f"REAL-quality predictions: {len(cases)}"
    )

    print(
        f"Recognition rate:        "
        f"{pct(len(cases), len(transitions)):.1f}%"
    )

    print(
        f"LONG recognized:         "
        f"{long_recognized}/{long_total}"
    )

    print(
        f"SHORT recognized:        "
        f"{short_recognized}/{short_total}"
    )

    print(
        f"Average lead:            "
        f"{avg_lead:.2f} x 30m"
    )

    print(
        f"Maximum lead:            "
        f"{max((c.lead_bars for c in cases), default=0):.2f} x 30m"
    )

    print()
    print(
        "ACTUAL OUTCOMES OF PREDICTED REAL EVENTS"
    )

    print("-" * 80)

    print(
        f"REAL            {real:3d}    "
        f"{pct(real, len(cases)):5.1f}%"
    )

    print(
        f"WEAK            {weak:3d}    "
        f"{pct(weak, len(cases)):5.1f}%"
    )

    print(
        f"FALSE           {false:3d}    "
        f"{pct(false, len(cases)):5.1f}%"
    )

    print()
    print(
        "RECOGNIZED REAL-QUALITY PREDICTIONS"
    )

    print("-" * 100)

    for case in cases:

        print(
            f"{case.transition.time} | "
            f"{case.transition.before}->{case.transition.after} | "
            f"predicted=REAL | "
            f"lead={case.lead_bars} bars | "
            f"confidence={case.confidence * 100:.1f}% | "
            f"actual={case.actual_quality} | "
            f"MFE={case.mfe_pct:.2f}% | "
            f"MAE={case.mae_pct:.2f}%"
        )


def print_combined_report(
    tested_symbols: int,
    total_transitions: int,
    all_cases: List[QualityCase],
) -> None:

    real = sum(
        1 for c in all_cases
        if c.actual_quality == "REAL"
    )

    weak = sum(
        1 for c in all_cases
        if c.actual_quality == "WEAK"
    )

    false = sum(
        1 for c in all_cases
        if c.actual_quality == "FALSE"
    )

    avg_lead = (
        sum(c.lead_bars for c in all_cases)
        / len(all_cases)
        if all_cases
        else 0.0
    )

    print()
    print("=" * 80)
    print(
        "AATA TRANSITION RECOGNITION V4 — COMBINED SUMMARY"
    )
    print("=" * 80)

    print(
        f"Symbols tested: {tested_symbols}"
    )
    print(
        f"Transitions:             {total_transitions}"
    )

    print(
        f"REAL-quality predictions: {len(all_cases)}"
    )

    print(
        f"Recognition rate:        "
        f"{pct(len(all_cases), total_transitions):.1f}%"
    )

    print(
        f"Average lead:            "
        f"{avg_lead:.2f} x 30m"
    )

    print(
        f"Maximum lead:            "
        f"{max((c.lead_bars for c in all_cases), default=0):.2f} x 30m"
    )

    print()
    print(
        "ACTUAL OUTCOME DISTRIBUTION"
    )

    print("-" * 80)

    print(
        f"REAL           {real:4d}    "
        f"{pct(real, len(all_cases)):5.1f}%"
    )

    print(
        f"WEAK           {weak:4d}    "
        f"{pct(weak, len(all_cases)):5.1f}%"
    )

    print(
        f"FALSE          {false:4d}    "
        f"{pct(false, len(all_cases)):5.1f}%"
    )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:

    print("=" * 80)
    print("AATA TRANSITION RECOGNITION V4")
    print("=" * 80)
    print("RESEARCH ONLY")
    print("No API")
    print("No trades")
    print("No engine changes")
    print("No DB writes")
    print()
    print(
        f"Early-recognition window: {EARLY_WINDOW_BARS} x 30m"
    )
    print(
        f"Outcome horizon:          {OUTCOME_HOURS} hours"
    )
    print(
        f"Prediction threshold:     "
        f"{PREDICTION_THRESHOLD * 100:.0f}%"
    )
    print(
        f"Minimum training cases:   {MIN_TRAIN_CASES}"
    )
    print(
        f"RF trees:                 {N_ESTIMATORS}"
    )
    print()
    print(
        "V4 GOAL: distinguish REAL transitions from WEAK/FALSE "
        "before the official transition."
    )
    print("=" * 80)

    total_transitions = 0
    all_cases: List[QualityCase] = []
    tested_symbols = 0

    tested_symbols += 1

    for symbol in SYMBOLS:

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
                f"{symbol}: ERROR loading data: {exc}"
            )

            continue

        if len(rows) == 0:

            print(
                f"{symbol}: SKIP (30m candles=0)"
            )

            continue

        if len(rows_5m) == 0:

            print(
                f"{symbol}: SKIP (5m candles=0)"
            )

            continue

        tested_symbols += 1

        states = build_states(rows)

        transitions = find_transitions(
            rows,
            states,
        )

        cases = evaluate_symbol(
            rows,
            rows_5m,
            symbol,
        )

        total_transitions += len(
            transitions
        )

        all_cases.extend(cases)

        print_symbol_report(
            symbol,
            rows,
            transitions,
            cases,
        )

        print_combined_report(
            tested_symbols,
            total_transitions,
            all_cases,
        )


if __name__ == "__main__":
    main()
