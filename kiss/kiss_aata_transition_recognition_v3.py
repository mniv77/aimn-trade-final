# [FILE: kiss_aata_transition_recognition_v3.py] — AATA KISS V3 transition recognition research
"""
AATA KISS V3 — REAL-TIME TRANSITION RECOGNITION RESEARCH

RESEARCH ONLY
- No API
- No trades
- No engine changes
- No DB writes

Purpose:
Test whether AATA can recognize an approaching LONG/SHORT transition
using ONLY information that was available at that moment.

V3 focuses on:
1. Event-level transition recognition.
2. REAL / WEAK / FALSE outcome quality.
3. Recognition speed.
4. LONG and SHORT separately.
5. Confidence calibration.
6. Avoiding repeated predictions for the same event.

The future is NEVER provided as an input feature.
Future data is used only for:
- training labels
- evaluating the eventual transition outcome
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from db import get_db_connection
from engine.kiss_execution_5m import (
    TREND_BAND,
    TREND_WINDOW,
    rsi_wilder,
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

EARLY_WINDOW_BARS = 4
OUTCOME_HOURS = 4

MIN_TRAIN_CASES = 80
PURGE_BARS = 4

PREDICTION_THRESHOLD = 0.60

# A prediction can belong to only one transition event.
EVENT_COOLDOWN_BARS = 4

RANDOM_STATE = 42
N_ESTIMATORS = 250


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Transition:
    index: int
    timestamp: object
    before: str
    after: str


@dataclass
class Prediction:
    index: int
    direction: str
    confidence: float


@dataclass
class Recognition:
    transition: Transition
    prediction: Prediction
    lead_bars: int
    outcome: str
    mfe_pct: float
    mae_pct: float


# ============================================================================
# MARKET STATE
# ============================================================================

def get_market_state(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"

    ma = sum(closes[idx - TREND_WINDOW:idx]) / TREND_WINDOW

    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"

    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"

    return "FLAT"


def find_transitions(rows: List[dict]) -> List[Transition]:
    closes = [float(r["close"]) for r in rows]
    states = [get_market_state(closes, i) for i in range(len(closes))]

    transitions: List[Transition] = []

    for i in range(1, len(states)):
        before = states[i - 1]
        after = states[i]

        if before == after:
            continue

        if after not in ("LONG", "SHORT"):
            continue

        transitions.append(
            Transition(
                index=i,
                timestamp=rows[i]["timestamp"],
                before=before,
                after=after,
            )
        )

    return transitions


# ============================================================================
# FEATURES
# ============================================================================

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
    "recent_high_distance_pct",
    "recent_low_distance_pct",
    "state_duration",
    "state_churn_6",
    "up_count_3",
    "down_count_3",
    "up_count_6",
    "down_count_6",
    "volume_change_pct",
    "v_shape",
]


def pct_change(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a / b - 1.0) * 100.0


def build_features(rows: List[dict], states: List[str], idx: int) -> Optional[Dict[str, float]]:
    if idx < max(TREND_WINDOW, 20):
        return None

    closes = [float(r["close"]) for r in rows]
    volumes = [float(r.get("volume", 0) or 0) for r in rows]

    price = closes[idx]

    ma20 = sum(closes[idx - 20:idx]) / 20.0
    distance_pct = pct_change(price, ma20)

    older_ma_start = idx - 25
    older_ma_end = idx - 5

    if older_ma_start >= 0:
        older_ma = sum(closes[older_ma_start:older_ma_end]) / 20.0
        ma_slope_pct = pct_change(ma20, older_ma)
    else:
        ma_slope_pct = 0.0

    rsi_values = rsi_wilder(closes[: idx + 1], 14)
    rsi = float(rsi_values[-1]) if rsi_values else 50.0

    def move(bars: int) -> float:
        if idx < bars:
            return 0.0
        return pct_change(closes[idx], closes[idx - bars])

    recent_high = max(closes[idx - 12:idx + 1])
    recent_low = min(closes[idx - 12:idx + 1])

    high_distance = pct_change(price, recent_high)
    low_distance = pct_change(price, recent_low)

    current_state = states[idx]

    duration = 0
    j = idx - 1
    while j >= 0 and states[j] == current_state:
        duration += 1
        j -= 1

    churn = 0
    start = max(1, idx - 6)

    for j in range(start, idx + 1):
        if states[j] != states[j - 1]:
            churn += 1

    up3 = 0
    down3 = 0
    for j in range(max(1, idx - 2), idx + 1):
        if closes[j] > closes[j - 1]:
            up3 += 1
        elif closes[j] < closes[j - 1]:
            down3 += 1

    up6 = 0
    down6 = 0
    for j in range(max(1, idx - 5), idx + 1):
        if closes[j] > closes[j - 1]:
            up6 += 1
        elif closes[j] < closes[j - 1]:
            down6 += 1

    if idx > 0 and volumes[idx - 1] != 0:
        volume_change = pct_change(volumes[idx], volumes[idx - 1])
    else:
        volume_change = 0.0

    v_shape = 0.0

    if idx >= 2:
        a = closes[idx - 2]
        b = closes[idx - 1]
        c = closes[idx]

        if a > b < c:
            v_shape = 1.0
        elif a < b > c:
            v_shape = -1.0

    return {
        "price": price,
        "ma20": ma20,
        "distance_pct": distance_pct,
        "ma_slope_pct": ma_slope_pct,
        "rsi": rsi,
        "move_1bar_pct": move(1),
        "move_2bar_pct": move(2),
        "move_3bar_pct": move(3),
        "move_4bar_pct": move(4),
        "move_6bar_pct": move(6),
        "move_12bar_pct": move(12),
        "recent_high_distance_pct": high_distance,
        "recent_low_distance_pct": low_distance,
        "state_duration": float(duration),
        "state_churn_6": float(churn),
        "up_count_3": float(up3),
        "down_count_3": float(down3),
        "up_count_6": float(up6),
        "down_count_6": float(down6),
        "volume_change_pct": volume_change,
        "v_shape": v_shape,
    }


# ============================================================================
# TRAINING LABEL
# ============================================================================

def future_transition_direction(
    states: Sequence[str],
    idx: int,
    lookahead: int = EARLY_WINDOW_BARS,
) -> Optional[str]:
    end = min(len(states), idx + lookahead + 1)

    for j in range(idx + 1, end):
        if states[j] == "LONG" and states[j - 1] != "LONG":
            return "LONG"

        if states[j] == "SHORT" and states[j - 1] != "SHORT":
            return "SHORT"

    return None


# ============================================================================
# OUTCOME SCORING
# ============================================================================

def score_transition_outcome(
    transition: Transition,
    trend_rows: List[dict],
    execution_rows: List[dict],
) -> Tuple[str, float, float]:
    entry_time = transition.timestamp
    direction = transition.after

    entry_price = float(trend_rows[transition.index]["close"])

    horizon_seconds = OUTCOME_HOURS * 60 * 60

    mfe = 0.0
    mae = 0.0

    for row in execution_rows:
        ts = row["timestamp"]

        if ts < entry_time:
            continue

        try:
            delta_seconds = (ts - entry_time).total_seconds()
        except AttributeError:
            continue

        if delta_seconds > horizon_seconds:
            break

        high = float(row["high"])
        low = float(row["low"])

        if direction == "LONG":
            favorable = (high / entry_price - 1.0) * 100.0
            adverse = (low / entry_price - 1.0) * 100.0

            mfe = max(mfe, favorable)
            mae = min(mae, adverse)

        else:
            favorable = (entry_price / low - 1.0) * 100.0
            adverse = (entry_price / high - 1.0) * 100.0

            mfe = max(mfe, favorable)
            mae = min(mae, adverse)

    adverse_abs = abs(mae)

    if mfe >= 1.0 and mfe >= 1.5 * adverse_abs:
        outcome = "REAL"
    elif adverse_abs >= 1.0 and mfe < 0.5:
        outcome = "FALSE"
    else:
        outcome = "WEAK"

    return outcome, mfe, adverse_abs


# ============================================================================
# MODEL
# ============================================================================

def make_matrix(feature_rows: List[Dict[str, float]]) -> np.ndarray:
    return np.asarray(
        [[row[name] for name in FEATURE_NAMES] for row in feature_rows],
        dtype=float,
    )


def train_and_predict(
    rows: List[dict],
    states: List[str],
    target_idx: int,
) -> Optional[Prediction]:
    """
    Train a walk-forward transition detector using both positive and
    negative examples.

    Labels:
        LONG  = LONG transition occurs within the next EARLY_WINDOW_BARS
        SHORT = SHORT transition occurs within the next EARLY_WINDOW_BARS
        NONE  = no directional transition occurs in that window

    IMPORTANT:
        Future state information is used ONLY to create training labels.
        It is never included in the feature vector.
    """
    current_features = build_features(rows, states, target_idx)

    if current_features is None:
        return None

    train_x: List[Dict[str, float]] = []
    train_y: List[str] = []

    train_end = target_idx - PURGE_BARS

    for idx in range(TREND_WINDOW + 1, train_end):
        features = build_features(rows, states, idx)

        if features is None:
            continue

        future_direction = future_transition_direction(
            states,
            idx,
            EARLY_WINDOW_BARS,
        )

        if future_direction is None:
            label = "NONE"
        else:
            label = future_direction

        train_x.append(features)
        train_y.append(label)

    if len(train_x) < MIN_TRAIN_CASES:
        return None

    if len(set(train_y)) < 2:
        return None

    # ------------------------------------------------------------------------
    # Balance NONE against the directional transition examples.
    #
    # Without this cap, NONE would normally dominate because most candles
    # are not immediately followed by a transition.
    # ------------------------------------------------------------------------
    directional_indices = [
        i for i, label in enumerate(train_y)
        if label in ("LONG", "SHORT")
    ]

    none_indices = [
        i for i, label in enumerate(train_y)
        if label == "NONE"
    ]

    if not directional_indices:
        return None

    max_none = max(
        len(directional_indices) * 2,
        MIN_TRAIN_CASES,
    )

    if len(none_indices) > max_none:
        rng = np.random.default_rng(RANDOM_STATE + target_idx)
        selected_none = rng.choice(
            none_indices,
            size=max_none,
            replace=False,
        ).tolist()
    else:
        selected_none = none_indices

    selected_indices = directional_indices + selected_none

    rng = np.random.default_rng(RANDOM_STATE + target_idx + 100000)
    rng.shuffle(selected_indices)

    train_x = [train_x[i] for i in selected_indices]
    train_y = [train_y[i] for i in selected_indices]

    if len(set(train_y)) < 2:
        return None

    x_train = make_matrix(train_x)

    model = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        random_state=RANDOM_STATE,
        class_weight="balanced",
        min_samples_leaf=3,
        n_jobs=-1,
    )

    model.fit(x_train, train_y)

    x_current = make_matrix([current_features])

    probabilities = model.predict_proba(x_current)[0]
    classes = list(model.classes_)

    best_idx = int(np.argmax(probabilities))
    direction = str(classes[best_idx])
    confidence = float(probabilities[best_idx])

    # NONE is a valid model decision. It is not a transition prediction.
    if direction == "NONE":
        return None

    if confidence < PREDICTION_THRESHOLD:
        return None

    return Prediction(
        index=target_idx,
        direction=direction,
        confidence=confidence,
    )

# ============================================================================
# DATABASE
# ============================================================================

def load_candles(symbol: str, timeframe: str, limit: int = 5000) -> List[dict]:
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
            (symbol, timeframe, int(limit)),
        )

        return list(cursor.fetchall())

    finally:
        cursor.close()
        conn.close()


# ============================================================================
# EVENT MATCHING
# ============================================================================

def recognize_events(
    transitions: List[Transition],
    rows: List[dict],
    states: List[str],
    execution_rows: List[dict],
) -> List[Recognition]:
    recognitions: List[Recognition] = []

    used_prediction_indices = set()

    for transition in transitions:
        start = max(TREND_WINDOW + 1, transition.index - EARLY_WINDOW_BARS)
        end = transition.index

        candidates: List[Prediction] = []

        for idx in range(start, end):
            if idx in used_prediction_indices:
                continue

            prediction = train_and_predict(rows, states, idx)

            if prediction is None:
                continue

            if prediction.direction != transition.after:
                continue

            candidates.append(prediction)

        if not candidates:
            continue

        # Choose the earliest valid prediction.
        prediction = min(candidates, key=lambda p: p.index)

        used_prediction_indices.add(prediction.index)

        outcome, mfe, mae = score_transition_outcome(
            transition,
            rows,
            execution_rows,
        )

        lead = transition.index - prediction.index

        recognitions.append(
            Recognition(
                transition=transition,
                prediction=prediction,
                lead_bars=lead,
                outcome=outcome,
                mfe_pct=mfe,
                mae_pct=mae,
            )
        )

    return recognitions


# ============================================================================
# REPORTING
# ============================================================================

def print_symbol_report(
    symbol: str,
    rows: List[dict],
    transitions: List[Transition],
    recognitions: List[Recognition],
) -> None:
    long_transitions = sum(1 for t in transitions if t.after == "LONG")
    short_transitions = sum(1 for t in transitions if t.after == "SHORT")

    long_recognized = sum(
        1 for r in recognitions if r.transition.after == "LONG"
    )

    short_recognized = sum(
        1 for r in recognitions if r.transition.after == "SHORT"
    )

    recognition_rate = (
        len(recognitions) / len(transitions) * 100.0
        if transitions
        else 0.0
    )

    avg_lead = (
        sum(r.lead_bars for r in recognitions) / len(recognitions)
        if recognitions
        else 0.0
    )

    max_lead = (
        max(r.lead_bars for r in recognitions)
        if recognitions
        else 0
    )

    real = sum(1 for r in recognitions if r.outcome == "REAL")
    weak = sum(1 for r in recognitions if r.outcome == "WEAK")
    false = sum(1 for r in recognitions if r.outcome == "FALSE")

    print()
    print("=" * 80)
    print(f"AATA TRANSITION RECOGNITION V3 — {symbol}")
    print("=" * 80)
    print(f"30m candles:             {len(rows)}")
    print(f"Existing transitions:    {len(transitions)}")
    print(f"LONG transitions:        {long_transitions}")
    print(f"SHORT transitions:       {short_transitions}")
    print(f"Recognized events:       {len(recognitions)}")
    print(f"Recognition rate:        {recognition_rate:.1f}%")
    print(f"LONG recognized:         {long_recognized}/{long_transitions}")
    print(f"SHORT recognized:        {short_recognized}/{short_transitions}")
    print(f"Average lead:            {avg_lead:.2f} x 30m")
    print(f"Maximum lead:            {max_lead:.2f} x 30m")

    print()
    print("RECOGNIZED OUTCOMES")
    print("-" * 80)
    print(
        f"REAL          {real:3d}   "
        f"{(real / len(recognitions) * 100 if recognitions else 0):5.1f}%"
    )
    print(
        f"WEAK          {weak:3d}   "
        f"{(weak / len(recognitions) * 100 if recognitions else 0):5.1f}%"
    )
    print(
        f"FALSE         {false:3d}   "
        f"{(false / len(recognitions) * 100 if recognitions else 0):5.1f}%"
    )

    print()
    print("RECOGNIZED TRANSITIONS")
    print("-" * 100)

    for r in recognitions:
        print(
            f"{r.transition.timestamp} | "
            f"{r.transition.before}->{r.transition.after} | "
            f"predicted={r.prediction.direction} | "
            f"lead={r.lead_bars} bars | "
            f"confidence={r.prediction.confidence * 100:.1f}% | "
            f"outcome={r.outcome} | "
            f"MFE={r.mfe_pct:.2f}% | "
            f"MAE={r.mae_pct:.2f}%"
        )


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    print("=" * 80)
    print("RESEARCH ONLY")
    print("No API")
    print("No trades")
    print("No engine changes")
    print("No DB writes")
    print()
    print("AATA TRANSITION RECOGNITION V3")
    print()
    print(f"Early-recognition window: {EARLY_WINDOW_BARS} x 30m")
    print(f"Outcome horizon:          {OUTCOME_HOURS} hours")
    print(f"Prediction threshold:     {PREDICTION_THRESHOLD * 100:.0f}%")
    print(f"Minimum training cases:   {MIN_TRAIN_CASES}")
    print()
    print("V3 goal:")
    print("Test whether transition evidence can be recognized")
    print("BEFORE the official KISS state transition.")
    print("=" * 80)

    combined_transitions = 0
    combined_recognized = 0
    combined_real = 0
    combined_weak = 0
    combined_false = 0
    combined_leads: List[int] = []

    combined_by_type: Dict[str, List[int]] = {}

    for symbol in SYMBOLS:
        rows = load_candles(symbol, "30m")

        if not rows:
            print()
            print(f"{symbol}: SKIP (30m candles=0)")
            continue

        execution_rows = load_candles(symbol, "5m")

        closes = [float(r["close"]) for r in rows]
        states = [get_market_state(closes, i) for i in range(len(rows))]

        transitions = find_transitions(rows)

        recognitions = recognize_events(
            transitions,
            rows,
            states,
            execution_rows,
        )

        print_symbol_report(
            symbol,
            rows,
            transitions,
            recognitions,
        )

        combined_transitions += len(transitions)
        combined_recognized += len(recognitions)

        combined_real += sum(
            1 for r in recognitions if r.outcome == "REAL"
        )
        combined_weak += sum(
            1 for r in recognitions if r.outcome == "WEAK"
        )
        combined_false += sum(
            1 for r in recognitions if r.outcome == "FALSE"
        )

        combined_leads.extend(
            r.lead_bars for r in recognitions
        )

        for r in recognitions:
            key = f"{r.transition.before}->{r.transition.after}"

            if key not in combined_by_type:
                combined_by_type[key] = [0, 0]

            combined_by_type[key][0] += 1
            combined_by_type[key][1] += 1

    recognition_rate = (
        combined_recognized / combined_transitions * 100.0
        if combined_transitions
        else 0.0
    )

    avg_lead = (
        sum(combined_leads) / len(combined_leads)
        if combined_leads
        else 0.0
    )

    max_lead = max(combined_leads) if combined_leads else 0

    print()
    print("=" * 80)
    print("AATA TRANSITION RECOGNITION V3 — COMBINED SUMMARY")
    print("=" * 80)
    print(f"Symbols tested:          {sum(1 for s in SYMBOLS if load_candles(s, '30m'))}")
    print(f"Transitions:             {combined_transitions}")
    print(f"Recognized events:       {combined_recognized}")
    print(f"Recognition rate:        {recognition_rate:.1f}%")
    print(f"Average lead:            {avg_lead:.2f} x 30m")
    print(f"Maximum lead:            {max_lead:.2f} x 30m")

    print()
    print("OUTCOME DISTRIBUTION")
    print("-" * 80)
    print(
        f"REAL          {combined_real:3d}   "
        f"{(combined_real / combined_recognized * 100 if combined_recognized else 0):5.1f}%"
    )
    print(
        f"WEAK          {combined_weak:3d}   "
        f"{(combined_weak / combined_recognized * 100 if combined_recognized else 0):5.1f}%"
    )
    print(
        f"FALSE         {combined_false:3d}   "
        f"{(combined_false / combined_recognized * 100 if combined_recognized else 0):5.1f}%"
    )

    print()
    print("TRANSITION TYPE — RECOGNITION")
    print("-" * 80)

    for transition_type in [
        "FLAT->LONG",
        "FLAT->SHORT",
        "LONG->SHORT",
        "SHORT->LONG",
    ]:
        total = 0
        recognized = 0

        for symbol in SYMBOLS:
            rows = load_candles(symbol, "30m")

            if not rows:
                continue

            transitions = find_transitions(rows)

            total += sum(
                1
                for t in transitions
                if f"{t.before}->{t.after}" == transition_type
            )

            # This section is intentionally informational only.
            # Event recognition was already performed above.
            # We do not rerun recognition here.

        print(
            f"{transition_type:<15} "
            f"{total:3d} transitions"
        )

    print()
    print("IMPORTANT:")
    print("This is research only.")
    print("Do NOT change the trading engine from this result.")
    print("=" * 80)


if __name__ == "__main__":
    main()
PYEOF