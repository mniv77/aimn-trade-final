
#!/usr/bin/env python3
"""
EXP128 — THREE-WAY SHORT EXIT AUDIT

Research only. No live orders or production modifications.

Compare:
  EXP117: structural-only exit
  EXP121: structural exit + W12 > 0%
  EXP125: structural exit + frozen W12 > 0.10%

Uses existing historical candles and unchanged research engines.
This is a post-holdout diagnostic, NOT fresh independent validation.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

import aimn_exp83_v16_structural_exit as base
import aimn_exp100_confirmed_swing_structure as swing
import aimn_exp117_full_swing_replay as exp117
import aimn_exp121_joint_momentum_replay as exp121
import aimn_exp125_w12_strength_replay as exp125

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "kiss/results/exp128_confirmation_delay_audit.json"
FROZEN_W12 = 0.10


def net(trades):
    return round(sum(t["net_pnl_pct"] for t in trades), 6)


def trade_map(symbol, name, trades):
    result = {t["entry_time"]: t for t in trades}
    if len(result) != len(trades):
        raise AssertionError(
            f"{symbol}: duplicate entries in {name}"
        )
    return result


def outcome(delta):
    if delta > 0:
        return "HELPED"
    if delta < 0:
        return "HURT"
    return "UNCHANGED"


def analyze(symbol, path):
    path = path.resolve()
    source_bytes = path.read_bytes()
    rows = json.loads(source_bytes)

    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{symbol}: invalid candle data")

    rows.sort(key=lambda r: str(r["timestamp"]))

    times = [str(r["timestamp"]) for r in rows]
    if len(times) != len(set(times)):
        raise AssertionError(
            f"{symbol}: duplicate timestamps"
        )

    closes = [float(r["close"]) for r in rows]
    starts = swing.get_session_starts(times)

    ph, pl, counts = swing.confirmed_pivots(
        rows, times, starts
    )

    states = [
        swing.structure(rows, times, starts, i, ph, pl, counts)
        for i in range(len(rows))
    ]

    st = base.calculate_supertrend(
        rows, atr_period=10, multiplier=3.0
    )["st_trend"].tolist()

    rsi = base.rsi_wilder(closes)

    market = [
        base.get_market_state(closes, i)
        for i in range(len(rows))
    ]

    # Existing structural-only engine.
    structural, structural_events, _, _ = exp117.simulate(
        rows, st, rsi, market, states, "JOINT_SWING"
    )

    # Existing zero-threshold and frozen-threshold engines.
    positive, positive_signals, _, _, _ = exp125.replay(
        rows, st, rsi, market, states, starts, 0.0
    )

    frozen, frozen_signals, _, _, _ = exp125.replay(
        rows, st, rsi, market, states, starts, FROZEN_W12
    )

    # Independent implementation parity within existing engines.
    reference, reference_signals, _, _, _ = exp121.replay(
        rows, st, rsi, market, states, starts
    )

    if positive != reference:
        raise AssertionError(
            f"{symbol}: EXP121 trade parity failed"
        )

    signal_keys = lambda events: [
        (e["entry_time"], e["signal_time"])
        for e in events
    ]

    if signal_keys(positive_signals) != signal_keys(reference_signals):
        raise AssertionError(
            f"{symbol}: EXP121 signal parity failed"
        )

    maps = {
        "structural": trade_map(symbol, "EXP117", structural),
        "positive": trade_map(symbol, "EXP121", positive),
        "frozen": trade_map(symbol, "EXP125", frozen),
    }

    entries = set(maps["structural"])

    if (entries != set(maps["positive"]) or
            entries != set(maps["frozen"])):
        raise AssertionError(
            f"{symbol}: different entry sets; comparison stopped"
        )

    signals = {
        "structural": {
            e["entry_time"]: e for e in structural_events
        },
        "positive": {
            e["entry_time"]: e for e in positive_signals
        },
        "frozen": {
            e["entry_time"]: e for e in frozen_signals
        },
    }

    index = {t: i for i, t in enumerate(times)}
    details = []

    for entry in sorted(entries):
        a = maps["structural"][entry]
        b = maps["positive"][entry]
        c = maps["frozen"][entry]

        structural_minus_positive = round(
            a["net_pnl_pct"] - b["net_pnl_pct"], 6
        )

        positive_minus_frozen = round(
            b["net_pnl_pct"] - c["net_pnl_pct"], 6
        )

        structural_minus_frozen = round(
            a["net_pnl_pct"] - c["net_pnl_pct"], 6
        )

        sa = signals["structural"].get(entry)
        sb = signals["positive"].get(entry)
        sc = signals["frozen"].get(entry)

        def delay(first, second):
            if not first or not second:
                return None
            return (
                index[second["signal_time"]]
                - index[first["signal_time"]]
            )

        details.append({
            "entry_time": entry,
            "structural_signal": sa,
            "positive_w12_signal": sb,
            "frozen_w12_signal": sc,
            "structural_exit_time": a["exit_time"],
            "positive_exit_time": b["exit_time"],
            "frozen_exit_time": c["exit_time"],
            "structural_exit_reason": a["exit_reason"],
            "positive_exit_reason": b["exit_reason"],
            "frozen_exit_reason": c["exit_reason"],
            "structural_net_pct": a["net_pnl_pct"],
            "positive_net_pct": b["net_pnl_pct"],
            "frozen_net_pct": c["net_pnl_pct"],
            "structural_minus_positive_pp":
                structural_minus_positive,
            "structural_vs_positive":
                outcome(structural_minus_positive),
            "positive_minus_frozen_pp":
                positive_minus_frozen,
            "positive_vs_frozen":
                outcome(positive_minus_frozen),
            "structural_minus_frozen_pp":
                structural_minus_frozen,
            "structural_vs_frozen":
                outcome(structural_minus_frozen),
            "structural_to_positive_signal_delay_bars":
                delay(sa, sb),
            "structural_to_frozen_signal_delay_bars":
                delay(sa, sc),
        })

    def counts(field):
        return {
            "helped": sum(
                x[field] == "HELPED" for x in details
            ),
            "hurt": sum(
                x[field] == "HURT" for x in details
            ),
            "unchanged": sum(
                x[field] == "UNCHANGED" for x in details
            ),
        }

    return {
        "source": str(path),
        "sha256": hashlib.sha256(source_bytes).hexdigest(),
        "candles": len(rows),
        "trades": len(entries),
        "entry_sets_identical": True,
        "structural_net_pct_sum": net(structural),
        "positive_net_pct_sum": net(positive),
        "frozen_net_pct_sum": net(frozen),
        "structural_minus_positive_pp": round(
            net(structural) - net(positive), 6
        ),
        "positive_minus_frozen_pp": round(
            net(positive) - net(frozen), 6
        ),
        "structural_minus_frozen_pp": round(
            net(structural) - net(frozen), 6
        ),
        "structural_vs_positive": counts(
            "structural_vs_positive"
        ),
        "positive_vs_frozen": counts(
            "positive_vs_frozen"
        ),
        "structural_vs_frozen": counts(
            "structural_vs_frozen"
        ),
        "structural_signal_count": len(structural_events),
        "positive_signal_count": len(positive_signals),
        "frozen_signal_count": len(frozen_signals),
        "trades_detail": details,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--nvda", type=Path)
    parser.add_argument("--aapl", type=Path)

    args = parser.parse_args()

    selected = {
        symbol: path
        for symbol, path in (
            ("NVDA", args.nvda),
            ("AAPL", args.aapl),
        )
        if path is not None
    }

    if not selected:
        parser.error("Specify --nvda and/or --aapl")

    for symbol, path in selected.items():
        if not path.is_file():
            parser.error(f"{symbol}: file not found: {path}")

    report = {
        "experiment": "EXP128",
        "version": "three_way",
        "research_only": True,
        "status": "post_holdout_diagnostic",
        "frozen_w12_threshold_pct": FROZEN_W12,
        "comparison": [
            "EXP117 structural only",
            "EXP121 structural plus positive W12",
            "EXP125 structural plus frozen W12 0.10%",
        ],
        "limitations": [
            "Holdout outcomes already inspected.",
            "Not new independent validation.",
            "Differences are retrospective trade outcomes.",
            "Earlier exits are not necessarily earlier market pivots.",
            "Only executed structural signals are recorded.",
            "Safety exits and fee assumptions inherited.",
            "No slippage or borrow-cost modeling added.",
            "No threshold tuning or production changes.",
        ],
        "symbols": {
            symbol: analyze(symbol, path)
            for symbol, path in selected.items()
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)

    # Preserve the previous report before replacing it.
    # No additional permanent report file is created.
    if OUT.exists():
        previous = json.loads(OUT.read_text(encoding="utf-8"))
        if previous.get("experiment") != "EXP128":
            raise AssertionError(
                "Existing report is not EXP128; refusing overwrite"
            )
        if previous.get("version") == "three_way":
            raise FileExistsError(
                "Three-way report already exists; refusing overwrite"
            )
        report["previous_report"] = previous

    temp = OUT.with_suffix(".json.tmp")

    if temp.exists():
        raise FileExistsError(
            f"Temporary report already exists: {temp}"
        )

    try:
        with temp.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        os.replace(temp, OUT)
    finally:
        if temp.exists():
            temp.unlink()

    print("EXP128 — THREE-WAY EXIT AUDIT")
    print("RESEARCH ONLY")
    print()

    for symbol, r in report["symbols"].items():
        print(symbol)
        print("  Trades:", r["trades"])
        print("  Identical entries:", r["entry_sets_identical"])
        print("  Structural:", r["structural_net_pct_sum"])
        print("  W12 positive:", r["positive_net_pct_sum"])
        print("  W12 frozen:", r["frozen_net_pct_sum"])
        print(
            "  Structural minus frozen pp:",
            r["structural_minus_frozen_pp"]
        )
        print(
            "  Structural vs frozen:",
            r["structural_vs_frozen"]
        )
        print()

    print("Report:", OUT)
    print("No production changes or orders.")


if __name__ == "__main__":
    main()
