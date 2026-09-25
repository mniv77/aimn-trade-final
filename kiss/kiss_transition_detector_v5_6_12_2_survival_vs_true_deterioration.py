#!/usr/bin/env python3
"""
V5.6.12.2 — Survival vs True Deterioration
============================================
Research only. No DB writes. No orders. No engine changes.

QUESTION
--------
After ONE uniquely assigned first-warning episode, can we distinguish:

    WARNING -> SURVIVES
    WARNING -> CONTINUED DETERIORATION

using only completed 5m candles that were available at the decision time?

The official 30m KISS transition remains the reference T0.  It is NOT used
as a decision feature.  It is used only as the eventual reference event.

METHODOLOGY
-----------
1. Rebuild the same 30m directional transitions as V5.6.12.1-A.
2. Rebuild the same causal 5m warning observations.
3. Cluster warnings into 15m episodes.
4. Assign one episode to at most one transition.
5. For each assigned first warning, examine the post-warning path at
   15, 30, 45 and 60 minutes.
6. At each checkpoint, classify the OLD trend as:
       RECOVERING
       CONTINUING
       UNRESOLVED
   using only candles completed by that checkpoint.
7. Only AFTER the checkpoint is the next 60m old-direction return used as
   the outcome.  This prevents future leakage at the decision point.
8. Also report the eventual transition direction, but never use it to make
   the checkpoint classification.

This is deliberately a research instrument, not a trading rule.
"""

from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from db import get_db_connection


# ============================================================
# CONFIGURATION
# ============================================================

TREND_WINDOW = 20
TREND_BAND = 0.002
RSI_PERIOD = 14

LOOKBACK_MINUTES = 480
MAX_WARNING_LEAD_MINUTES = 480
MIN_WARNING_LEAD_MINUTES = 0
EPISODE_GAP_MINUTES = 15

# Post-warning checkpoints.  These are observation times, not forced waits.
CHECKPOINTS = (15, 30, 45, 60)

# Outcome after a checkpoint.  Future data begins strictly after the
# checkpoint decision and is used only for evaluation.
OUTCOME_MINUTES = 60
OUTCOME_THRESHOLD_PCT = 0.10

# Recovery evidence available by a checkpoint.
RECOVERY_RETURN_PCT = 0.15
RECOVERY_FAVORABLE_BARS = 2
RECOVERY_MAX_ADVERSE_PCT = 0.25

# Continued-deterioration evidence available by a checkpoint.
CONTINUATION_RETURN_PCT = -0.40
CONTINUATION_ADVERSE_BARS = 2
CONTINUATION_STRUCTURE_BARS = 3


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Transition:
    symbol: str
    timestamp: datetime
    old_state: str
    new_state: str
    direction: str
    index_30m: int


@dataclass
class WarningObservation:
    symbol: str
    timestamp: datetime
    old_direction: str
    health: str
    score: float
    adverse_count: int
    consecutive_adverse: int
    net_signed_move_pct: float
    structure_break: bool
    severe_balance: bool
    persistent_adverse: bool
    repeated_adverse: bool
    reason: str


@dataclass
class WarningEpisode:
    symbol: str
    first_timestamp: datetime
    last_timestamp: datetime
    observations: List[WarningObservation]

    @property
    def first(self) -> WarningObservation:
        return self.observations[0]


@dataclass
class Assignment:
    transition: Transition
    episode: WarningEpisode
    lead_minutes: float


@dataclass
class CheckpointResult:
    checkpoint_minutes: int
    state: str
    signed_return_from_warning: Optional[float]
    min_signed_from_warning: Optional[float]
    max_signed_from_warning: Optional[float]
    favorable_bars: int
    adverse_bars: int
    consecutive_adverse: int
    structure_break: bool
    next60_outcome: Optional[str]
    next60_return: Optional[float]


# ============================================================
# BASIC HELPERS
# ============================================================

def pct_change(start: float, end: float) -> Optional[float]:
    if start is None or end is None or start == 0:
        return None
    return (end / start - 1.0) * 100.0


def safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def fmt_num(value: Optional[float], digits: int = 3) -> str:
    if value is None or not math.isfinite(value):
        return "N/A"
    return f"{value:.{digits}f}"


def fmt_pct(value: Optional[float], digits: int = 3) -> str:
    if value is None or not math.isfinite(value):
        return "N/A"
    return f"{value:.{digits}f}%"


def mean(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None and math.isfinite(v)]
    if not vals:
        return None
    return sum(vals) / len(vals)


def median(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = sorted(v for v in values if v is not None and math.isfinite(v))
    if not vals:
        return None
    n = len(vals)
    if n % 2:
        return vals[n // 2]
    return (vals[n // 2 - 1] + vals[n // 2]) / 2.0


def direction_sign(direction: str) -> int:
    return 1 if direction == "LONG" else -1 if direction == "SHORT" else 0


# ============================================================
# DATABASE
# ============================================================

def load_rows(symbol: str, timeframe: str) -> List[Candle]:
    conn, _ = get_db_connection()
    cur = None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol=%s AND timeframe=%s
            ORDER BY timestamp ASC
            """,
            (symbol, timeframe),
        )
        result: List[Candle] = []
        for row in cur.fetchall():
            ts = row.get("timestamp")
            if not isinstance(ts, datetime):
                continue
            result.append(
                Candle(
                    timestamp=ts,
                    open=safe_float(row.get("open")),
                    high=safe_float(row.get("high")),
                    low=safe_float(row.get("low")),
                    close=safe_float(row.get("close")),
                    volume=safe_float(row.get("volume")),
                )
            )
        return result
    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# KISS 30M STATE / TRANSITIONS
# ============================================================

def get_market_state(closes: Sequence[float], idx: int) -> str:
    if idx < TREND_WINDOW or idx >= len(closes):
        return "FLAT"
    window = closes[idx - TREND_WINDOW:idx]
    ma = sum(window) / len(window)
    if closes[idx] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[idx] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def build_directional_transitions(symbol: str, rows: Sequence[Candle]) -> List[Transition]:
    if len(rows) <= TREND_WINDOW:
        return []
    closes = [r.close for r in rows]
    states = [get_market_state(closes, i) for i in range(len(rows))]
    result: List[Transition] = []
    for i in range(1, len(states)):
        old_state = states[i - 1]
        new_state = states[i]
        if old_state == "LONG" and new_state == "SHORT":
            result.append(Transition(symbol, rows[i].timestamp + timedelta(minutes=30), old_state, new_state, "LONG", i))
        elif old_state == "SHORT" and new_state == "LONG":
            result.append(Transition(symbol, rows[i].timestamp + timedelta(minutes=30), old_state, new_state, "SHORT", i))
    return result


# ============================================================
# 5M TIMING / STRUCTURE
# ============================================================

def candle_close_time(row: Candle) -> datetime:
    return row.timestamp + timedelta(minutes=5)


def build_close_map(rows: Sequence[Candle]) -> Dict[datetime, int]:
    return {candle_close_time(r): i for i, r in enumerate(rows)}


def find_close_index(rows: Sequence[Candle], target: datetime) -> Optional[int]:
    for i, row in enumerate(rows):
        if candle_close_time(row) == target:
            return i
    return None


def structure_break_for_direction(rows: Sequence[Candle], idx: int, direction: str, bars: int = 3) -> bool:
    if idx < bars:
        return False
    current = rows[idx]
    previous = rows[idx - bars:idx]
    if direction == "LONG":
        return current.close < min(r.low for r in previous)
    if direction == "SHORT":
        return current.close > max(r.high for r in previous)
    return False


def recent_adverse_statistics(rows: Sequence[Candle], idx: int, direction: str) -> Tuple[int, int, float]:
    if idx <= 0:
        return 0, 0, 0.0
    lookback_bars = min(idx, LOOKBACK_MINUTES // 5)
    start = max(1, idx - lookback_bars)
    adverse_count = 0
    consecutive = 0
    max_consecutive = 0
    signed_moves: List[float] = []
    for j in range(start, idx + 1):
        raw = pct_change(rows[j - 1].close, rows[j].close)
        if raw is None:
            continue
        signed = raw if direction == "LONG" else -raw
        signed_moves.append(signed)
        if signed < 0:
            adverse_count += 1
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0
    return adverse_count, max_consecutive, sum(signed_moves) if signed_moves else 0.0


def severe_balance_for_direction(rows: Sequence[Candle], idx: int, direction: str) -> bool:
    if idx < 6:
        return False
    start = max(0, idx - 6)
    favorable = 0.0
    adverse = 0.0
    for j in range(start + 1, idx + 1):
        raw = pct_change(rows[j - 1].close, rows[j].close)
        if raw is None:
            continue
        signed = raw if direction == "LONG" else -raw
        if signed >= 0:
            favorable += signed
        else:
            adverse += abs(signed)
    total = favorable + adverse
    return total > 0 and adverse / total >= 0.65 and adverse >= 0.40


# ============================================================
# WARNING MODEL — SAME FAMILY AS V5.6.12.1-A
# ============================================================

def classify_health(adverse_count: int, consecutive_adverse: int, net_signed_move_pct: float,
                    structure_break: bool, severe_balance: bool) -> Tuple[str, float, str]:
    score = 0.0
    reasons: List[str] = []
    if structure_break:
        score += 3.0
        reasons.append("structure_break")
    if consecutive_adverse >= 2:
        score += 2.0
        reasons.append("persistent_adverse")
    if severe_balance:
        score += 2.0
        reasons.append("severe_balance")
    if adverse_count >= 3:
        score += 1.0
        reasons.append("repeated_adverse")
    if net_signed_move_pct <= -0.20:
        score += 1.0
    elif net_signed_move_pct <= -0.05:
        score += 0.5

    if severe_balance and structure_break and score >= 5.0:
        health = "CRITICAL"
    elif score >= 3.0 or net_signed_move_pct <= -0.20:
        health = "DETERIORATING"
    elif adverse_count >= 1 or net_signed_move_pct < -0.05:
        health = "STRESSED"
    else:
        health = "HEALTHY"

    if not reasons:
        reasons.append("health_change")
    return health, score, "+".join(reasons)


def build_warning_observations(symbol: str, rows: Sequence[Candle]) -> List[WarningObservation]:
    if len(rows) < 10:
        return []
    result: List[WarningObservation] = []
    for direction in ("LONG", "SHORT"):
        previous_health = "HEALTHY"
        for idx in range(max(TREND_WINDOW, 10), len(rows)):
            adverse_count, consecutive, net_move = recent_adverse_statistics(rows, idx, direction)
            structure_break = structure_break_for_direction(rows, idx, direction)
            severe_balance = severe_balance_for_direction(rows, idx, direction)
            health, score, reason = classify_health(adverse_count, consecutive, net_move, structure_break, severe_balance)
            if health not in ("STRESSED", "DETERIORATING", "CRITICAL"):
                previous_health = health
                continue
            if health != previous_health or score >= 2.0 or structure_break or consecutive >= 2:
                result.append(
                    WarningObservation(
                        symbol=symbol,
                        timestamp=candle_close_time(rows[idx]),
                        old_direction=direction,
                        health=health,
                        score=score,
                        adverse_count=adverse_count,
                        consecutive_adverse=consecutive,
                        net_signed_move_pct=net_move,
                        structure_break=structure_break,
                        severe_balance=severe_balance,
                        persistent_adverse=consecutive >= 2,
                        repeated_adverse=adverse_count >= 3,
                        reason=reason,
                    )
                )
            previous_health = health
    result.sort(key=lambda x: (x.symbol, x.timestamp, x.old_direction))
    return result


# ============================================================
# WARNING EPISODES / UNIQUE ASSIGNMENT
# ============================================================

def cluster_warning_episodes(observations: Sequence[WarningObservation]) -> List[WarningEpisode]:
    by_key: Dict[Tuple[str, str], List[WarningObservation]] = defaultdict(list)
    for obs in observations:
        by_key[(obs.symbol, obs.old_direction)].append(obs)
    episodes: List[WarningEpisode] = []
    for (symbol, direction), items in by_key.items():
        items = sorted(items, key=lambda x: x.timestamp)
        current: Optional[WarningEpisode] = None
        for obs in items:
            if current is None:
                current = WarningEpisode(symbol, obs.timestamp, obs.timestamp, [obs])
                continue
            gap = (obs.timestamp - current.last_timestamp).total_seconds() / 60.0
            if gap <= EPISODE_GAP_MINUTES:
                current.observations.append(obs)
                current.last_timestamp = obs.timestamp
            else:
                episodes.append(current)
                current = WarningEpisode(symbol, obs.timestamp, obs.timestamp, [obs])
        if current is not None:
            episodes.append(current)
    episodes.sort(key=lambda e: (e.symbol, e.first.old_direction, e.first_timestamp))
    return episodes


def eligible_episode_for_transition(episode: WarningEpisode, transition: Transition) -> bool:
    if episode.symbol != transition.symbol:
        return False
    if episode.first.old_direction != transition.direction:
        return False
    lead = (transition.timestamp - episode.first_timestamp).total_seconds() / 60.0
    return MIN_WARNING_LEAD_MINUTES <= lead <= MAX_WARNING_LEAD_MINUTES


def assign_one_episode_per_transition(transitions: Sequence[Transition], episodes: Sequence[WarningEpisode]) -> List[Tuple[Transition, WarningEpisode]]:
    transitions_sorted = sorted(transitions, key=lambda t: (t.symbol, t.timestamp))
    episodes_sorted = sorted(episodes, key=lambda e: (e.symbol, e.first.old_direction, e.first_timestamp))
    candidates: List[Tuple[float, datetime, datetime, int, int]] = []
    for ti, transition in enumerate(transitions_sorted):
        for ei, episode in enumerate(episodes_sorted):
            if not eligible_episode_for_transition(episode, transition):
                continue
            lead = (transition.timestamp - episode.first_timestamp).total_seconds() / 60.0
            candidates.append((lead, episode.first_timestamp, transition.timestamp, ti, ei))
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    used_t = set()
    used_e = set()
    result: List[Tuple[Transition, WarningEpisode]] = []
    for lead, episode_time, transition_time, ti, ei in candidates:
        if ti in used_t or ei in used_e:
            continue
        used_t.add(ti)
        used_e.add(ei)
        result.append((transitions_sorted[ti], episodes_sorted[ei]))
    result.sort(key=lambda x: (x[0].symbol, x[0].timestamp))
    return result


# ============================================================
# POST-WARNING PATH
# ============================================================

def signed_close_return(start_price: float, end_price: float, direction: str) -> Optional[float]:
    raw = pct_change(start_price, end_price)
    if raw is None:
        return None
    return raw if direction == "LONG" else -raw


def path_statistics(rows: Sequence[Candle], start_idx: int, end_idx: int, direction: str) -> Tuple[Optional[float], Optional[float], Optional[float], int, int, int, bool]:
    if end_idx <= start_idx:
        return None, None, None, 0, 0, 0, False
    start_price = rows[start_idx].close
    signed_return = signed_close_return(start_price, rows[end_idx].close, direction)
    min_signed = 0.0
    max_signed = 0.0
    favorable = 0
    adverse = 0
    consecutive = 0
    max_consecutive = 0
    for j in range(start_idx + 1, end_idx + 1):
        raw = pct_change(rows[j - 1].close, rows[j].close)
        if raw is None:
            continue
        signed = raw if direction == "LONG" else -raw
        from_start = signed_close_return(start_price, rows[j].close, direction)
        if from_start is not None:
            min_signed = min(min_signed, from_start)
            max_signed = max(max_signed, from_start)
        if signed >= 0:
            favorable += 1
            consecutive = 0
        else:
            adverse += 1
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
    structure = structure_break_for_direction(rows, end_idx, direction, CONTINUATION_STRUCTURE_BARS)
    return signed_return, min_signed, max_signed, favorable, adverse, max_consecutive, structure


def classify_post_warning_state(signed_return: Optional[float], min_signed: Optional[float], max_signed: Optional[float],
                                favorable_bars: int, adverse_bars: int, consecutive_adverse: int,
                                structure_break: bool) -> str:
    if signed_return is None:
        return "UNRESOLVED"

    recovery = (
        signed_return >= RECOVERY_RETURN_PCT
        and favorable_bars >= RECOVERY_FAVORABLE_BARS
        and (min_signed is None or min_signed > -RECOVERY_MAX_ADVERSE_PCT)
    )

    continuation = (
        signed_return <= CONTINUATION_RETURN_PCT
        and adverse_bars >= CONTINUATION_ADVERSE_BARS
        and (consecutive_adverse >= CONTINUATION_ADVERSE_BARS or structure_break)
    )

    if recovery and not continuation:
        return "RECOVERING"
    if continuation and not recovery:
        return "CONTINUING"

    # If both appear, prefer the stronger present-time evidence.
    if recovery and continuation:
        if abs(signed_return) >= CONTINUATION_RETURN_PCT + RECOVERY_RETURN_PCT:
            return "CONTINUING" if signed_return < 0 else "RECOVERING"

    return "UNRESOLVED"


def outcome_after_checkpoint(rows: Sequence[Candle], checkpoint_idx: int, direction: str) -> Tuple[Optional[str], Optional[float]]:
    target = candle_close_time(rows[checkpoint_idx]) + timedelta(minutes=OUTCOME_MINUTES)
    end_idx = find_close_index(rows, target)
    if end_idx is None or end_idx <= checkpoint_idx:
        return None, None
    ret = signed_close_return(rows[checkpoint_idx].close, rows[end_idx].close, direction)
    if ret is None:
        return None, None
    if ret <= -OUTCOME_THRESHOLD_PCT:
        return "GOOD", ret
    if ret >= OUTCOME_THRESHOLD_PCT:
        return "FALSE", ret
    return "NEUTRAL", ret


def evaluate_assignment(rows_5m: Sequence[Candle], assignment: Assignment) -> List[CheckpointResult]:
    warning = assignment.episode.first
    warning_idx = find_close_index(rows_5m, warning.timestamp)
    if warning_idx is None:
        return []
    results: List[CheckpointResult] = []
    for minutes in CHECKPOINTS:
        target_time = warning.timestamp + timedelta(minutes=minutes)
        checkpoint_idx = find_close_index(rows_5m, target_time)
        if checkpoint_idx is None or checkpoint_idx <= warning_idx:
            continue
        signed_return, min_signed, max_signed, favorable, adverse, consecutive, structure = path_statistics(
            rows_5m, warning_idx, checkpoint_idx, assignment.transition.direction
        )
        state = classify_post_warning_state(
            signed_return, min_signed, max_signed, favorable, adverse, consecutive, structure
        )
        outcome, next60 = outcome_after_checkpoint(rows_5m, checkpoint_idx, assignment.transition.direction)
        results.append(
            CheckpointResult(
                checkpoint_minutes=minutes,
                state=state,
                signed_return_from_warning=signed_return,
                min_signed_from_warning=min_signed,
                max_signed_from_warning=max_signed,
                favorable_bars=favorable,
                adverse_bars=adverse,
                consecutive_adverse=consecutive,
                structure_break=structure,
                next60_outcome=outcome,
                next60_return=next60,
            )
        )
    return results


# ============================================================
# ANALYSIS
# ============================================================

def analyze_symbol(symbol: str) -> Tuple[List[Transition], List[WarningEpisode], List[Assignment], List[CheckpointResult]]:
    rows_30m = load_rows(symbol, "30m")
    rows_5m = load_rows(symbol, "5m")
    transitions = build_directional_transitions(symbol, rows_30m)
    observations = build_warning_observations(symbol, rows_5m)
    episodes = cluster_warning_episodes(observations)
    raw_assignments = assign_one_episode_per_transition(transitions, episodes)
    assignments: List[Assignment] = []
    checkpoint_results: List[CheckpointResult] = []

    for transition, episode in raw_assignments:
        lead = (transition.timestamp - episode.first_timestamp).total_seconds() / 60.0
        assignment = Assignment(transition, episode, lead)
        evaluated = evaluate_assignment(rows_5m, assignment)
        if not evaluated:
            continue
        assignments.append(assignment)
        checkpoint_results.extend(evaluated)

    print(
        f"\n[{symbol}] 30m={len(rows_30m):,} 5m={len(rows_5m):,} "
        f"transitions={len(transitions):3d} episodes={len(episodes):3d} "
        f"assigned={len(assignments):3d} checkpoints={len(checkpoint_results):3d}"
    )
    return transitions, episodes, assignments, checkpoint_results


# ============================================================
# REPORTING
# ============================================================

def report_checkpoint_summary(results: Sequence[CheckpointResult]) -> None:
    print("\n" + "=" * 90)
    print("SURVIVAL vs TRUE DETERIORATION — CHECKPOINT TEST")
    print("=" * 90)
    print("State is determined ONLY from data available by that checkpoint.")
    print("NEXT60 is future evaluation AFTER the checkpoint.")
    print()
    for minutes in CHECKPOINTS:
        group = [r for r in results if r.checkpoint_minutes == minutes]
        if not group:
            continue
        states = Counter(r.state for r in group)
        valid = [r for r in group if r.next60_outcome is not None]
        good = sum(r.next60_outcome == "GOOD" for r in valid)
        false = sum(r.next60_outcome == "FALSE" for r in valid)
        neutral = sum(r.next60_outcome == "NEUTRAL" for r in valid)
        print(f"CHECKPOINT +{minutes:2d}m  N={len(group):3d}  VALID={len(valid):3d}")
        print(
            f"  STATES: RECOVERING={states.get('RECOVERING',0):3d} "
            f"CONTINUING={states.get('CONTINUING',0):3d} "
            f"UNRESOLVED={states.get('UNRESOLVED',0):3d}"
        )
        if valid:
            print(
                f"  NEXT60: GOOD={good:3d} ({good/len(valid)*100:5.1f}%) "
                f"FALSE={false:3d} ({false/len(valid)*100:5.1f}%) "
                f"NEUTRAL={neutral:3d} ({neutral/len(valid)*100:5.1f}%) "
                f"AVG={fmt_pct(mean(r.next60_return for r in valid))}"
            )
        print()


def report_state_separation(results: Sequence[CheckpointResult]) -> None:
    print("=" * 90)
    print("STATE -> FUTURE OUTCOME")
    print("=" * 90)
    for minutes in CHECKPOINTS:
        print(f"\n+{minutes}m")
        group = [r for r in results if r.checkpoint_minutes == minutes and r.next60_outcome is not None]
        for state in ("RECOVERING", "CONTINUING", "UNRESOLVED"):
            sub = [r for r in group if r.state == state]
            if not sub:
                continue
            counts = Counter(r.next60_outcome for r in sub)
            good = counts.get("GOOD", 0)
            false = counts.get("FALSE", 0)
            neutral = counts.get("NEUTRAL", 0)
            avg = mean(r.next60_return for r in sub)
            print(
                f"  {state:11s} N={len(sub):3d} "
                f"GOOD={good:3d} ({good/len(sub)*100:5.1f}%) "
                f"FALSE={false:3d} ({false/len(sub)*100:5.1f}%) "
                f"NEUTRAL={neutral:3d} AVG60={fmt_pct(avg)}"
            )


def report_direction(results_by_assignment: Dict[Tuple[str, datetime, str], List[CheckpointResult]]) -> None:
    print("\n" + "=" * 90)
    print("DIRECTIONAL SURVIVAL TEST")
    print("=" * 90)
    for direction in ("LONG", "SHORT"):
        all_results = [
            r for key, vals in results_by_assignment.items()
            if key[2] == direction
            for r in vals
        ]
        if not all_results:
            continue
        print(f"\n{direction}")
        for minutes in CHECKPOINTS:
            group = [r for r in all_results if r.checkpoint_minutes == minutes and r.next60_outcome is not None]
            if not group:
                continue
            states = Counter(r.state for r in group)
            print(
                f"  +{minutes:2d}m N={len(group):3d} "
                f"REC={states.get('RECOVERING',0):3d} "
                f"CONT={states.get('CONTINUING',0):3d} "
                f"UNRES={states.get('UNRESOLVED',0):3d} "
                f"AVG60={fmt_pct(mean(r.next60_return for r in group))}"
            )


def report_transition_reference(assignments: Sequence[Assignment]) -> None:
    print("\n" + "=" * 90)
    print("UNIQUE ASSIGNMENT AUDIT")
    print("=" * 90)
    transition_keys = [(a.transition.symbol, a.transition.timestamp, a.transition.direction) for a in assignments]
    episode_keys = [(a.episode.symbol, a.episode.first.old_direction, a.episode.first_timestamp) for a in assignments]
    tc = Counter(transition_keys)
    ec = Counter(episode_keys)
    print(f"ASSIGNMENTS:             {len(assignments)}")
    print(f"UNIQUE TRANSITIONS:      {len(set(transition_keys))}")
    print(f"UNIQUE WARNING EPISODES: {len(set(episode_keys))}")
    print(f"DUPLICATE TRANSITIONS:   {sum(v > 1 for v in tc.values())}")
    print(f"DUPLICATE EPISODES:      {sum(v > 1 for v in ec.values())}")
    print("OK: one warning episode is assigned to at most one transition." if len(episode_keys) == len(set(episode_keys)) else "WARNING: episode reuse detected.")


def report_representatives(assignments: Sequence[Assignment], results_by_assignment: Dict[Tuple[str, datetime, str], List[CheckpointResult]], limit: int = 20) -> None:
    print("\n" + "=" * 90)
    print("REPRESENTATIVE SURVIVAL CASES")
    print("=" * 90)
    rows = []
    for a in assignments:
        key = (a.transition.symbol, a.transition.timestamp, a.transition.direction)
        vals = results_by_assignment.get(key, [])
        for r in vals:
            if r.next60_outcome in ("GOOD", "FALSE"):
                rows.append((r.next60_outcome, a, r))
    rows.sort(key=lambda x: (x[0], x[1].transition.symbol, x[1].transition.timestamp))
    for outcome, a, r in rows[:limit]:
        w = a.episode.first
        print(f"\n{a.transition.symbol:5s} {a.transition.direction:5s} {outcome:7s} CHECKPOINT +{r.checkpoint_minutes}m")
        print(f"  WARNING: {w.timestamp}")
        print(f"  T0:      {a.transition.timestamp}")
        print(f"  LEAD:    {a.lead_minutes:.1f}m")
        print(f"  STATE:   {r.state}")
        print(f"  FROM WARNING: {fmt_pct(r.signed_return_from_warning)}")
        print(f"  MIN:     {fmt_pct(r.min_signed_from_warning)}")
        print(f"  MAX:     {fmt_pct(r.max_signed_from_warning)}")
        print(f"  NEXT60:  {fmt_pct(r.next60_return)}")
        print(f"  STRUCT:  {r.structure_break}")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="V5.6.12.2 survival vs true deterioration research")
    parser.add_argument(
        "--symbols", nargs="+",
        default=["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "SPY", "QQQ"],
    )
    args = parser.parse_args()

    all_transitions: List[Transition] = []
    all_episodes: List[WarningEpisode] = []
    all_assignments: List[Assignment] = []
    all_results: List[CheckpointResult] = []
    results_by_assignment: Dict[Tuple[str, datetime, str], List[CheckpointResult]] = {}

    print("\n" + "#" * 90)
    print("V5.6.12.2 — SURVIVAL vs TRUE DETERIORATION")
    print("#" * 90)
    print("Research only — no DB writes / no orders / no engine changes.")
    print("RULE: ONE transition -> ONE first warning episode -> post-warning checkpoints")
    print(f"CHECKPOINTS: {CHECKPOINTS}m | NEXT OUTCOME: {OUTCOME_MINUTES}m")
    print()

    for symbol in args.symbols:
        try:
            transitions, episodes, assignments, results = analyze_symbol(symbol)
            all_transitions.extend(transitions)
            all_episodes.extend(episodes)
            all_assignments.extend(assignments)
            all_results.extend(results)
            # Reconstruct assignment keys from the checkpoint list by matching
            # against assignments in chronological order.  Each assignment has
            # at most four checkpoint results; evaluation order is deterministic.
            for a in assignments:
                key = (a.transition.symbol, a.transition.timestamp, a.transition.direction)
                vals = [r for r in results if True]
                # Filter by the warning-to-checkpoint sequence using the exact
                # expected count/order.  The symbol-level result list is rebuilt
                # below from direct reevaluation to avoid ambiguous matching.
                # This block is intentionally replaced after the main symbol loop.
                results_by_assignment.setdefault(key, [])
        except Exception as exc:
            print(f"[{symbol}] ERROR: {exc}")

    # Re-evaluate assignments cleanly for the per-assignment reports.  This is
    # read-only and keeps the global statistics above independent of reporting.
    for symbol in args.symbols:
        try:
            rows_5m = load_rows(symbol, "5m")
            symbol_assignments = [a for a in all_assignments if a.transition.symbol == symbol]
            for a in symbol_assignments:
                key = (a.transition.symbol, a.transition.timestamp, a.transition.direction)
                results_by_assignment[key] = evaluate_assignment(rows_5m, a)
        except Exception as exc:
            print(f"[{symbol}] REPORT ERROR: {exc}")

    print("\n" + "#" * 90)
    print("GLOBAL RESULTS")
    print("#" * 90)
    print(f"KNOWN DIRECTIONAL TRANSITIONS: {len(all_transitions)}")
    print(f"WARNING EPISODES:               {len(all_episodes)}")
    print(f"UNIQUELY ASSIGNED TRANSITIONS:  {len(all_assignments)}")
    print(f"TRANSITIONS WITHOUT ASSIGNMENT: {len(all_transitions) - len(all_assignments)}")

    report_transition_reference(all_assignments)
    report_checkpoint_summary(all_results)
    report_state_separation(all_results)
    report_direction(results_by_assignment)
    report_representatives(all_assignments, results_by_assignment, limit=30)

    print("\n" + "#" * 90)
    print("V5.6.12.2 INTERPRETATION")
    print("#" * 90)
    print("This is a research test, not a trading rule.")
    print("The key question is whether RECOVERING and CONTINUING states separate")
    print("future old-trend outcomes better than treating every warning as an exit.")
    print("The checkpoint state uses only information available through that time.")
    print("NEXT60 is strictly future evaluation after the checkpoint.")
    print("Do NOT change the live KISS engine from this run alone.")
    print()


if __name__ == "__main__":
    main()
