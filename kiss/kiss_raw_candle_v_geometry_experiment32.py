#!/usr/bin/env python3
"""
AIMn KISS - Experiment #32: Raw-Candle V Reconstruction

RESEARCH ONLY.

Purpose:
Measure the raw 5m market shape after each exact 30m KISS transition
WITHOUT using the trailing-entry mechanism to define the V.

The experiment starts after the completed 30m advisor candle is known and
measures the actual subsequent 5m candles.

Measurements:
- raw adverse excursion / V depth
- time to adverse extreme
- recovery from that extreme
- time to recovery
- recovery speed
- dwell near the adverse extreme
- post-recovery favorable movement
- whether configurable descriptive thresholds were reached

These are retrospective research measurements, NOT trading rules.
No live orders, broker calls, production changes, or parameter promotion.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from db import get_db_connection


SYMBOLS = ["SPY", "QQQ", "NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "GOOGL"]

TREND_WINDOW = 20
TREND_BAND = 0.002

DEFAULT_HORIZON_MINUTES = 60
DEFAULT_RECOVERY_PCT = 0.25
DEFAULT_NEAR_EXTREME_PCT = 0.10
DEFAULT_FAVORABLE_PCT = 0.50

ET = ZoneInfo("America/New_York")
UTC = timezone.utc


def num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def utc_from_db_5m(ts: Any) -> datetime:
    if isinstance(ts, datetime):
        if ts.tzinfo is not None:
            return ts.astimezone(UTC)
        return ts.replace(tzinfo=ET).astimezone(UTC)
    dt = datetime.fromisoformat(str(ts))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ET)
    return dt.astimezone(UTC)


def load_5m(symbol: str) -> List[Dict[str, Any]]:
    conn, cursor = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")
    try:
        cursor.execute(
            """SELECT timestamp, open, high, low, close, volume
               FROM candles
               WHERE symbol=%s AND timeframe='5m'
               ORDER BY timestamp ASC""",
            (symbol,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [
        {
            "timestamp": r["timestamp"],
            "utc": utc_from_db_5m(r["timestamp"]),
            "open": num(r["open"]),
            "high": num(r["high"]),
            "low": num(r["low"]),
            "close": num(r["close"]),
            "volume": num(r["volume"]),
        }
        for r in rows
    ]


def reconstruct_30m(rows5: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []

    for row in rows5:
        local = row["utc"].astimezone(ET)

        if local.hour < 9 or (local.hour == 9 and local.minute < 30):
            continue
        if local.hour > 16 or (local.hour == 16 and local.minute > 0):
            continue

        if not current:
            current = [row]
            continue

        prev = current[-1]
        same_day = prev["utc"].astimezone(ET).date() == local.date()
        contiguous = row["utc"] - prev["utc"] == timedelta(minutes=5)

        if same_day and contiguous:
            current.append(row)
        else:
            if len(current) == 6:
                groups.append(current)
            current = [row]

        if len(current) == 6:
            groups.append(current)
            current = []

    if len(current) == 6:
        groups.append(current)

    return [
        {
            "timestamp": g[0]["utc"],
            "known_utc": g[-1]["utc"] + timedelta(minutes=5),
            "open": g[0]["open"],
            "high": max(x["high"] for x in g),
            "low": min(x["low"] for x in g),
            "close": g[-1]["close"],
            "volume": sum(x["volume"] for x in g),
        }
        for g in groups
    ]


def market_state(closes: List[float], i: int) -> str:
    if i < TREND_WINDOW:
        return "FLAT"
    ma = sum(closes[i - TREND_WINDOW:i]) / TREND_WINDOW

    if closes[i] > ma * (1.0 + TREND_BAND):
        return "LONG"
    if closes[i] < ma * (1.0 - TREND_BAND):
        return "SHORT"
    return "FLAT"


def transitions_for(rows30: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(rows30) <= TREND_WINDOW:
        return []

    closes = [x["close"] for x in rows30]
    states = [market_state(closes, i) for i in range(len(rows30))]

    events = []
    for i in range(TREND_WINDOW + 1, len(rows30)):
        old = states[i - 1]
        new = states[i]

        if new in {"LONG", "SHORT"} and new != old:
            events.append(
                {
                    "timestamp": rows30[i]["timestamp"],
                    "known_utc": rows30[i]["known_utc"],
                    "close": rows30[i]["close"],
                    "from": old,
                    "to": new,
                }
            )

    return events


def pct_change(a: float, b: float) -> float:
    if not math.isfinite(a) or not math.isfinite(b) or b == 0:
        return float("nan")
    return (a / b - 1.0) * 100.0


@dataclass
class RawV:
    case_id: str
    symbol: str
    direction: str
    transition_time_utc: str
    transition_known_utc: str
    transition_close: float
    horizon_minutes: int

    adverse_extreme_time_utc: str
    adverse_extreme_price: float
    v_depth_pct: float
    time_to_extreme_min: float

    recovery_time_utc: str
    recovery_price: float
    recovery_from_extreme_pct: float
    recovery_time_from_extreme_min: float
    recovery_speed_pct_per_min: float

    near_extreme_dwell_min: float
    max_post_recovery_favorable_pct: float
    max_favorable_from_transition_pct: float
    max_adverse_from_transition_pct: float

    reached_recovery: bool
    reached_favorable: bool
    candles_measured: int


def measure_raw_v(
    symbol: str,
    transition: Dict[str, Any],
    rows5: List[Dict[str, Any]],
    horizon_minutes: int,
    recovery_pct: float,
    near_extreme_pct: float,
    favorable_pct: float,
    case_number: int,
) -> tuple[RawV, List[Dict[str, Any]]]:

    start = transition["known_utc"]
    end = start + timedelta(minutes=horizon_minutes)
    direction = transition["to"]
    reference = transition["close"]

    # IMPORTANT: the V is measured directly from raw 5m candles.
    # No entry_extreme, entry_price, trade_id, or trailing-trade field is used.
    window = [r for r in rows5 if start < r["utc"] <= end]

    if direction == "LONG":
        adverse_price = float("inf")
    else:
        adverse_price = float("-inf")

    adverse_time: Optional[datetime] = None

    for row in window:
        if direction == "LONG" and row["low"] < adverse_price:
            adverse_price = row["low"]
            adverse_time = row["utc"]
        elif direction == "SHORT" and row["high"] > adverse_price:
            adverse_price = row["high"]
            adverse_time = row["utc"]

    if adverse_time is None:
        adverse_price = reference
        adverse_time = start

    if direction == "LONG":
        v_depth = pct_change(reference, adverse_price)
    else:
        v_depth = pct_change(adverse_price, reference)

    v_depth = max(0.0, v_depth) if math.isfinite(v_depth) else float("nan")
    time_to_extreme = max(
        0.0, (adverse_time - start).total_seconds() / 60.0
    )

    # Recovery is based on candle CLOSE, not an intrabar wick.
    if direction == "LONG":
        recovery_level = adverse_price * (1.0 + recovery_pct / 100.0)
    else:
        recovery_level = adverse_price * (1.0 - recovery_pct / 100.0)

    recovery_time: Optional[datetime] = None
    recovery_price = float("nan")

    for row in window:
        if row["utc"] <= adverse_time:
            continue

        if direction == "LONG" and row["close"] >= recovery_level:
            recovery_time = row["utc"]
            recovery_price = row["close"]
            break

        if direction == "SHORT" and row["close"] <= recovery_level:
            recovery_time = row["utc"]
            recovery_price = row["close"]
            break

    if recovery_time is not None:
        if direction == "LONG":
            recovery_from_extreme = pct_change(
                recovery_price, adverse_price
            )
        else:
            recovery_from_extreme = pct_change(
                adverse_price, recovery_price
            )

        recovery_time_min = (
            recovery_time - adverse_time
        ).total_seconds() / 60.0

        recovery_speed = (
            recovery_from_extreme / recovery_time_min
            if recovery_time_min > 0
            else float("inf")
        )
    else:
        recovery_from_extreme = float("nan")
        recovery_time_min = float("nan")
        recovery_speed = float("nan")

    # Dwell = number of completed 5m observations whose CLOSE remains
    # within near_extreme_pct of the raw adverse extreme.
    dwell_min = 0.0

    if direction == "LONG":
        near_level = adverse_price * (1.0 + near_extreme_pct / 100.0)
        for row in window:
            if row["utc"] >= adverse_time and row["close"] <= near_level:
                dwell_min += 5.0
    else:
        near_level = adverse_price * (1.0 - near_extreme_pct / 100.0)
        for row in window:
            if row["utc"] >= adverse_time and row["close"] >= near_level:
                dwell_min += 5.0

    max_favorable = 0.0
    max_adverse = 0.0
    max_post_recovery_favorable = 0.0
    favorable_reached = False

    for row in window:
        if direction == "LONG":
            favorable = pct_change(row["high"], reference)
            adverse = pct_change(row["low"], reference)
        else:
            favorable = pct_change(reference, row["low"])
            adverse = pct_change(reference, row["high"])

        if math.isfinite(favorable):
            max_favorable = max(max_favorable, favorable)
            if favorable >= favorable_pct:
                favorable_reached = True

        if math.isfinite(adverse):
            max_adverse = min(max_adverse, adverse)

        if recovery_time is not None and row["utc"] >= recovery_time:
            if math.isfinite(favorable):
                max_post_recovery_favorable = max(
                    max_post_recovery_favorable, favorable
                )

    trajectory: List[Dict[str, Any]] = []

    for row in window:
        if direction == "LONG":
            adverse_from_ref = pct_change(row["low"], reference)
            favorable_from_ref = pct_change(row["high"], reference)
            recovery_from_extreme = pct_change(
                row["close"], adverse_price
            )
        else:
            adverse_from_ref = pct_change(reference, row["high"])
            favorable_from_ref = pct_change(reference, row["low"])
            recovery_from_extreme = pct_change(
                adverse_price, row["close"]
            )

        trajectory.append(
            {
                "case_id": f"{symbol}-{case_number:03d}",
                "symbol": symbol,
                "direction": direction,
                "transition_known_utc": start.isoformat(),
                "candle_utc": row["utc"].isoformat(),
                "minutes_after_known": int(
                    (row["utc"] - start).total_seconds() / 60
                ),
                "open": round(row["open"], 8),
                "high": round(row["high"], 8),
                "low": round(row["low"], 8),
                "close": round(row["close"], 8),
                "adverse_from_transition_pct": round(
                    adverse_from_ref, 6
                ),
                "favorable_from_transition_pct": round(
                    favorable_from_ref, 6
                ),
                "recovery_from_raw_extreme_pct": round(
                    recovery_from_extreme, 6
                ),
            }
        )

    result = RawV(
        case_id=f"{symbol}-{case_number:03d}",
        symbol=symbol,
        direction=direction,
        transition_time_utc=transition["timestamp"].isoformat(),
        transition_known_utc=start.isoformat(),
        transition_close=round(reference, 8),
        horizon_minutes=horizon_minutes,
        adverse_extreme_time_utc=adverse_time.isoformat(),
        adverse_extreme_price=round(adverse_price, 8),
        v_depth_pct=round(v_depth, 6),
        time_to_extreme_min=round(time_to_extreme, 2),
        recovery_time_utc=(
            recovery_time.isoformat() if recovery_time else ""
        ),
        recovery_price=(
            round(recovery_price, 8)
            if math.isfinite(recovery_price)
            else float("nan")
        ),
        recovery_from_extreme_pct=(
            round(recovery_from_extreme, 6)
            if math.isfinite(recovery_from_extreme)
            else float("nan")
        ),
        recovery_time_from_extreme_min=(
            round(recovery_time_min, 2)
            if math.isfinite(recovery_time_min)
            else float("nan")
        ),
        recovery_speed_pct_per_min=(
            round(recovery_speed, 6)
            if math.isfinite(recovery_speed)
            else float("nan")
        ),
        near_extreme_dwell_min=round(dwell_min, 2),
        max_post_recovery_favorable_pct=round(
            max_post_recovery_favorable, 6
        ),
        max_favorable_from_transition_pct=round(
            max_favorable, 6
        ),
        max_adverse_from_transition_pct=round(
            max_adverse, 6
        ),
        reached_recovery=recovery_time is not None,
        reached_favorable=favorable_reached,
        candles_measured=len(window),
    )

    return result, trajectory


def finite(values: List[float]) -> List[float]:
    return [v for v in values if math.isfinite(v)]


def avg(values: List[float]) -> Optional[float]:
    values = finite(values)
    return round(sum(values) / len(values), 6) if values else None


def summarize(results: List[RawV]) -> Dict[str, Any]:
    depths = finite([x.v_depth_pct for x in results])
    times = finite([x.time_to_extreme_min for x in results])
    speeds = finite([x.recovery_speed_pct_per_min for x in results])

    depth_buckets = {
        "<0.25": [
            x for x in results if x.v_depth_pct < 0.25
        ],
        "0.25-0.50": [
            x for x in results
            if 0.25 <= x.v_depth_pct < 0.50
        ],
        "0.50-1.00": [
            x for x in results
            if 0.50 <= x.v_depth_pct < 1.00
        ],
        "1.00-1.50": [
            x for x in results
            if 1.00 <= x.v_depth_pct < 1.50
        ],
        ">=1.50": [
            x for x in results if x.v_depth_pct >= 1.50
        ],
    }

    def bucket_stats(items: List[RawV]) -> Dict[str, Any]:
        return {
            "cases": len(items),
            "recovered": sum(x.reached_recovery for x in items),
            "favorable_reached": sum(
                x.reached_favorable for x in items
            ),
            "avg_depth_pct": avg(
                [x.v_depth_pct for x in items]
            ),
            "avg_recovery_speed_pct_per_min": avg(
                [x.recovery_speed_pct_per_min for x in items]
            ),
            "avg_max_favorable_pct": avg(
                [x.max_favorable_from_transition_pct for x in items]
            ),
            "avg_max_adverse_pct": avg(
                [x.max_adverse_from_transition_pct for x in items]
            ),
        }

    by_symbol: Dict[str, Dict[str, Any]] = {}

    for symbol in SYMBOLS:
        items = [x for x in results if x.symbol == symbol]

        by_symbol[symbol] = {
            "cases": len(items),
            "long": sum(x.direction == "LONG" for x in items),
            "short": sum(x.direction == "SHORT" for x in items),
            "recovered": sum(
                x.reached_recovery for x in items
            ),
            "favorable_reached": sum(
                x.reached_favorable for x in items
            ),
            "avg_depth_pct": avg(
                [x.v_depth_pct for x in items]
            ),
            "avg_time_to_extreme_min": avg(
                [x.time_to_extreme_min for x in items]
            ),
            "avg_recovery_speed_pct_per_min": avg(
                [x.recovery_speed_pct_per_min for x in items]
            ),
        }

    return {
        "research_only": True,
        "experiment": "#32 Raw-Candle V Reconstruction",
        "method": (
            "Raw 5m candles after completed 30m transition; "
            "no entry-trail fields used"
        ),
        "trend_window": TREND_WINDOW,
        "trend_band_pct": TREND_BAND * 100.0,
        "case_count": len(results),
        "complete_horizon_cases": sum(
            x.candles_measured >= 12 for x in results
        ),
        "avg_depth_pct": avg(depths),
        "median_depth_pct": (
            round(sorted(depths)[len(depths) // 2], 6)
            if depths else None
        ),
        "avg_time_to_extreme_min": avg(times),
        "avg_recovery_speed_pct_per_min": avg(speeds),
        "recovered_cases": sum(
            x.reached_recovery for x in results
        ),
        "favorable_threshold_reached_cases": sum(
            x.reached_favorable for x in results
        ),
        "depth_buckets": {
            key: bucket_stats(value)
            for key, value in depth_buckets.items()
        },
        "by_symbol": by_symbol,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AIMn KISS Experiment #32"
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=DEFAULT_HORIZON_MINUTES,
        help="Forward raw-candle measurement horizon in minutes.",
    )
    parser.add_argument(
        "--recovery",
        type=float,
        default=DEFAULT_RECOVERY_PCT,
        help="Recovery distance from raw extreme in percent.",
    )
    parser.add_argument(
        "--near-extreme",
        type=float,
        default=DEFAULT_NEAR_EXTREME_PCT,
        help="Near-extreme close band in percent.",
    )
    parser.add_argument(
        "--favorable",
        type=float,
        default=DEFAULT_FAVORABLE_PCT,
        help="Descriptive favorable threshold from transition in percent.",
    )

    args = parser.parse_args()

    if args.horizon <= 0:
        raise SystemExit("--horizon must be > 0")
    if (
        args.recovery <= 0
        or args.near_extreme <= 0
        or args.favorable <= 0
    ):
        raise SystemExit(
            "--recovery, --near-extreme and --favorable must be > 0"
        )

    results_dir = Path(
        "kiss/results/exp32_raw_candle_v_geometry"
    )
    results_dir.mkdir(parents=True, exist_ok=True)

    all_results: List[RawV] = []
    all_trajectory: List[Dict[str, Any]] = []

    for symbol in SYMBOLS:
        print(f"[LOAD] {symbol}")

        rows5 = load_5m(symbol)
        if not rows5:
            print(f"[SKIP] {symbol}: no 5m data")
            continue

        rows30 = reconstruct_30m(rows5)
        events = transitions_for(rows30)

        print(
            f"[DATA] {symbol}: "
            f"5m={len(rows5)} "
            f"30m={len(rows30)} "
            f"transitions={len(events)}"
        )

        for n, event in enumerate(events, start=1):
            result, trajectory = measure_raw_v(
                symbol=symbol,
                transition=event,
                rows5=rows5,
                horizon_minutes=args.horizon,
                recovery_pct=args.recovery,
                near_extreme_pct=args.near_extreme,
                favorable_pct=args.favorable,
                case_number=n,
            )

            all_results.append(result)
            all_trajectory.extend(trajectory)

    geometry_csv = (
        results_dir / "raw_v_geometry.csv"
    )
    trajectory_csv = (
        results_dir / "raw_v_trajectory.csv"
    )
    summary_json = (
        results_dir / "raw_v_summary.json"
    )

    if all_results:
        with geometry_csv.open(
            "w", newline="", encoding="utf-8"
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=list(asdict(all_results[0]).keys()),
            )
            writer.writeheader()
            for item in all_results:
                writer.writerow(asdict(item))

    if all_trajectory:
        with trajectory_csv.open(
            "w", newline="", encoding="utf-8"
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=list(all_trajectory[0].keys()),
            )
            writer.writeheader()
            writer.writerows(all_trajectory)

    summary = summarize(all_results)

    summary["parameters"] = {
        "horizon_minutes": args.horizon,
        "recovery_pct_from_raw_extreme": args.recovery,
        "near_extreme_pct": args.near_extreme,
        "favorable_pct_from_transition": args.favorable,
    }

    summary["outputs"] = {
        "geometry_csv": str(geometry_csv),
        "trajectory_csv": str(trajectory_csv),
        "summary_json": str(summary_json),
    }

    with summary_json.open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(
            summary,
            f,
            indent=2,
            allow_nan=True,
        )

    complete_cases = sum(
        x.candles_measured >= args.horizon // 5
        for x in all_results
    )

    print()
    print(
        "=== AIMn KISS EXPERIMENT #32: "
        "RAW-CANDLE V RECONSTRUCTION ==="
    )
    print(f"Cases               : {summary['case_count']}")
    print(f"Complete horizon    : {complete_cases}")
    print(
        f"Avg V depth         : "
        f"{summary['avg_depth_pct']}"
    )
    print(
        f"Median V depth      : "
        f"{summary['median_depth_pct']}"
    )
    print(
        f"Avg time to extreme : "
        f"{summary['avg_time_to_extreme_min']} min"
    )
    print(
        f"Recovered cases     : "
        f"{summary['recovered_cases']}"
    )
    print(
        f"Favorable reached   : "
        f"{summary['favorable_threshold_reached_cases']}"
    )
    print(f"Geometry CSV        : {geometry_csv}")
    print(f"Trajectory CSV      : {trajectory_csv}")
    print(f"Summary JSON        : {summary_json}")


if __name__ == "__main__":
    main()
