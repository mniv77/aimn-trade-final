#!/usr/bin/env python3
"""EXP135: One-candle confirmation of first confirmed-high breakout.

Research only. No production orders or modifications.
"""

from collections import Counter
import aimn_exp129_first_breakout_profit_protection as exp129

exp117 = exp129.exp117
exp79 = exp117.exp79
base = exp129.base

CASES = [
    ("NVDA", "JUN_AUG",
     "kiss/visual_research/aimn_nvda_candles.json"),
    ("AAPL", "JUN_AUG",
     "kiss/visual_research/aimn_aapl_candles.json"),
    ("NVDA", "SEP_OCT",
     "kiss/visual_research/independent_holdout_exp127/nvda_sep_oct_2026_5m_iex.json"),
    ("AAPL", "SEP_OCT",
     "kiss/visual_research/independent_holdout_exp127/aapl_sep_oct_2026_5m_iex.json"),
]


def replay(rows, times, states, st, rsi, market):
    opens = [float(r["open"]) for r in rows]
    closes = [float(r["close"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]

    n = len(rows)
    pos = None
    pending = None
    trades = []
    warnings = []
    confirmations = []

    for i in range(35, n):
        day = times[i][:10]

        if day != times[i - 1][:10]:
            if pos is not None:
                trades.append(exp79.finish(
                    pos, i - 1, closes[i - 1],
                    "SESSION_END", times
                ))
                pos = None
            pending = None

        exited_at_open = False

        if pending is not None:
            action = pending
            pending = None

            if action == "ENTER" and pos is None:
                pos = {
                    "entry_time": times[i],
                    "entry_price": opens[i],
                    "entry_index": i,
                    "lowest_close": opens[i],
                    "fee_cover_seen": False,
                    "first_high_break_seen": False,
                    "confirmation_due": None,
                    "frozen_high": None,
                }

            elif action != "ENTER" and pos is not None:
                trades.append(exp79.finish(
                    pos, i, opens[i], action, times
                ))
                pos = None
                exited_at_open = True

        if pos is not None:
            stop = pos["entry_price"] * (
                1 + exp79.STOP_PCT / 100
            )

            if highs[i] >= stop:
                trades.append(exp79.finish(
                    pos, i, max(stop, opens[i]),
                    "STOP_LOSS", times
                ))
                pos = None
                pending = None

            else:
                pos["lowest_close"] = min(
                    pos["lowest_close"], closes[i]
                )

                gross = (
                    pos["entry_price"] / closes[i] - 1
                ) * 100

                profitable = gross > 2 * exp79.FEE

                if profitable:
                    pos["fee_cover_seen"] = True

                # Check the previously scheduled confirmation.
                # This decision uses the current completed close.
                confirmed = False

                if pos["confirmation_due"] == i:
                    frozen_high = pos["frozen_high"]
                    held = closes[i] > frozen_high

                    confirmations.append({
                        "entry_time": pos["entry_time"],
                        "confirmation_time": times[i],
                        "frozen_high": frozen_high,
                        "confirmation_close": closes[i],
                        "held": held,
                        "profitable": profitable,
                    })

                    confirmed = held and profitable
                    pos["confirmation_due"] = None

                # First warning only, as in EXP129.
                first_break = (
                    not pos["first_high_break_seen"]
                    and states[i][
                        "close_above_last_confirmed_high"
                    ] == 1
                )

                if first_break:
                    pos["first_high_break_seen"] = True

                    frozen = states[i]["latest_high_price"]

                    warnings.append({
                        "entry_time": pos["entry_time"],
                        "warning_time": times[i],
                        "frozen_high": frozen,
                        "net_at_warning_close": round(
                            gross - 2 * exp79.FEE, 6
                        ),
                    })

                    # Confirm on the following completed candle,
                    # but never across a session boundary.
                    if (
                        frozen is not None
                        and i + 1 < n
                        and times[i + 1][:10] == day
                    ):
                        pos["frozen_high"] = float(frozen)
                        pos["confirmation_due"] = i + 1

                # Original exit priorities take precedence.
                if (
                    i + 1 < n
                    and times[i + 1][:10] == day
                ):
                    if st[i - 1] == "SHORT" and st[i] == "LONG":
                        pending = "ST_REVERSE"

                    elif (
                        rsi[i] is not None
                        and rsi[i] >= exp79.RSI_LIMIT
                    ):
                        pending = "RSI_RESCUE"

                    elif (
                        pos["fee_cover_seen"]
                        and states[i]["low_sequence"]
                        == "HIGHER_LOW"
                        and states[i][
                            "close_above_last_confirmed_high"
                        ] == 1
                    ):
                        pending = "CONFIRMED_SWING_REVERSE"

                    elif confirmed:
                        pending = "CONFIRMED_HIGH_BREAK"

        # Match EXP117 candidate evaluation and entry gating.
        candidate = (
            base.is_major_long_to_short_reversal(
                highs, lows, closes, market, i
            ) is not None
        )

        if candidate:
            if (
                pos is not None
                or exited_at_open
                or pending in (
                    "ST_REVERSE",
                    "RSI_RESCUE",
                    "CONFIRMED_SWING_REVERSE",
                    "CONFIRMED_HIGH_BREAK",
                )
            ):
                pass
            elif pending == "ENTER":
                pass
            elif st[i] != "LONG":
                pass
            elif (
                i + 1 >= n
                or times[i + 1][:10] != day
            ):
                pass
            else:
                pending = "ENTER"

    if pos is not None:
        trades.append(exp79.finish(
            pos, n - 1, closes[-1],
            "DATA_END", times
        ))

    return trades, warnings, confirmations


def net(trade):
    # EXP117/EXP129 finish() returns net_pct.
    return float(trade["net_pnl_pct"])


def trade_key(trade):
    return trade["entry_time"]


def summarize(trades):
    return round(sum(net(t) for t in trades), 6)


def main():
    print("=" * 76)
    print("EXP135 - FIRST BREAKOUT / ONE-CANDLE CONFIRMATION")
    print("RESEARCH ONLY - NO PRODUCTION CHANGES")
    print("=" * 76)

    totals = Counter()

    for symbol, period, path in CASES:
        rows, times, states, st, rsi, market = (
            exp129.prepare(path)
        )

        baseline, _, _, _ = exp117.simulate(
            rows, st, rsi, market, states, "JOINT_SWING"
        )

        original129, original_warnings = (
            exp129.candidate_replay(
                rows, times, states, st, rsi, market
            )
        )

        candidate, warnings, confirmations = replay(
            rows, times, states, st, rsi, market
        )

        baseline_net = summarize(baseline)
        exp129_net = summarize(original129)
        candidate_net = summarize(candidate)

        totals["baseline"] += baseline_net
        totals["exp129"] += exp129_net
        totals["exp135"] += candidate_net
        totals["baseline_trades"] += len(baseline)
        totals["exp135_trades"] += len(candidate)

        print()
        print(symbol, period)
        print("CANDLES:", len(rows))
        print("EXP117:", len(baseline), baseline_net)
        print("EXP129:", len(original129), exp129_net)
        print("EXP135:", len(candidate), candidate_net)
        print("DELTA_VS_EXP117:",
              round(candidate_net - baseline_net, 6))
        print("WARNINGS:", len(warnings))
        print("CONFIRMATIONS:", len(confirmations))
        print("HELD:", sum(x["held"] for x in confirmations))
        print("HELD_AND_PROFITABLE:",
              sum(x["held"] and x["profitable"]
                  for x in confirmations))

        original_entries = {
            trade_key(t) for t in baseline
        }
        candidate_entries = {
            trade_key(t) for t in candidate
        }

        print("NEW_ENTRIES:",
              sorted(candidate_entries - original_entries))
        print("MISSING_ENTRIES:",
              sorted(original_entries - candidate_entries))

        original_by_entry = {
            trade_key(t): t for t in baseline
        }
        candidate_by_entry = {
            trade_key(t): t for t in candidate
        }

        for entry in sorted(
            original_entries & candidate_entries
        ):
            a = original_by_entry[entry]
            b = candidate_by_entry[entry]

            if (
                a["exit_time"] != b["exit_time"]
                or a["exit_reason"] != b["exit_reason"]
                or abs(net(a) - net(b)) > 0.000001
            ):
                print(
                    "CHANGED:",
                    entry,
                    "BASE", a["exit_time"],
                    a["exit_reason"], round(net(a), 6),
                    "EXP135", b["exit_time"],
                    b["exit_reason"], round(net(b), 6),
                    "DELTA", round(net(b) - net(a), 6)
                )

    print()
    print("=" * 76)
    print("COMBINED RESULTS")
    print("EXP117_TRADES:", totals["baseline_trades"])
    print("EXP135_TRADES:", totals["exp135_trades"])

    for key in ("baseline", "exp129", "exp135"):
        print(key.upper() + "_NET:",
              round(totals[key], 6))

    print("EXP135_MINUS_EXP117:",
          round(
              totals["exp135"] - totals["baseline"], 6
          ))
    print("EXP135_MINUS_EXP129:",
          round(
              totals["exp135"] - totals["exp129"], 6
          ))
    print("NO PRODUCTION FILES MODIFIED")


if __name__ == "__main__":
    main()
