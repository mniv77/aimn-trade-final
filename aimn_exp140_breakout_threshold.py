#!/usr/bin/env python3
"""EXP140: Sequential breakout-strength threshold sensitivity.
Research only. No production changes.
"""

from collections import Counter
import aimn_exp135_breakout_confirmation as exp135

exp129 = exp135.exp129
exp117 = exp135.exp117
exp79 = exp135.exp79
base = exp135.base

THRESHOLDS = (0.05, 0.10, 0.15, 0.20, 0.25)


def replay(rows, times, states, st, rsi, market, threshold):
    opens = [float(r["open"]) for r in rows]
    closes = [float(r["close"]) for r in rows]
    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]

    n = len(rows)
    pos = None
    pending = None
    trades = []
    signals = []

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

                if gross > 2 * exp79.FEE:
                    pos["fee_cover_seen"] = True

                first_break = (
                    not pos["first_high_break_seen"]
                    and states[i][
                        "close_above_last_confirmed_high"
                    ] == 1
                )

                qualifies = False

                if first_break:
                    pos["first_high_break_seen"] = True

                    confirmed_high = states[i][
                        "latest_high_price"
                    ]

                    # Include only completed candles from
                    # the current session.
                    session_start = i

                    while (
                        session_start > 0
                        and times[session_start - 1][:10]
                        == day
                    ):
                        session_start -= 1

                    start = max(session_start, i - 11)

                    ranges = [
                        highs[j] - lows[j]
                        for j in range(start, i + 1)
                    ]

                    average_range = (
                        sum(ranges) / len(ranges)
                        if len(ranges) == 12
                        else None
                    )

                    strength = (
                        (closes[i] - float(confirmed_high))
                        / average_range
                        if (
                            confirmed_high is not None
                            and average_range is not None
                            and average_range > 0
                        )
                        else None
                    )

                    qualifies = (
                        strength is not None
                        and strength >= threshold
                        and gross > 2 * exp79.FEE
                    )

                    signals.append({
                        "entry_time": pos["entry_time"],
                        "warning_time": times[i],
                        "strength": strength,
                        "eligible": gross > 2 * exp79.FEE,
                        "qualifies": qualifies,
                    })

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

                    elif qualifies:
                        pending = "STRONG_HIGH_BREAK"

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
                    "STRONG_HIGH_BREAK",
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

    return trades, signals


def total_net(trades):
    return sum(
        float(t["net_pnl_pct"]) for t in trades
    )


def main():
    print("=" * 80)
    print("EXP140 - SEQUENTIAL BREAKOUT THRESHOLD SENSITIVITY")
    print("RESEARCH ONLY")
    print("=" * 80)

    combined = Counter()

    for symbol, period, path in exp135.CASES:
        rows, times, states, st, rsi, market = (
            exp129.prepare(path)
        )

        baseline, _, _, _ = exp117.simulate(
            rows, st, rsi, market, states,
            "JOINT_SWING"
        )

        baseline_net = total_net(baseline)
        baseline_entries = [
            t["entry_time"] for t in baseline
        ]

        combined["baseline"] += baseline_net

        print("\n", symbol, period)
        print("BASELINE_TRADES:", len(baseline))
        print("BASELINE_NET:", round(baseline_net, 6))

        for threshold in THRESHOLDS:
            trades, signals = replay(
                rows, times, states, st, rsi,
                market, threshold
            )

            net = total_net(trades)
            delta = net - baseline_net

            entries = [
                t["entry_time"] for t in trades
            ]

            same_entries = (
                entries == baseline_entries
            )

            confirmed_exits = sum(
                t["exit_reason"] == "STRONG_HIGH_BREAK"
                for t in trades
            )

            combined[threshold] += net

            print(
                "THRESHOLD", threshold,
                "TRADES", len(trades),
                "NET", round(net, 6),
                "DELTA", round(delta, 6),
                "NEW_EXITS", confirmed_exits,
                "ENTRY_PARITY", same_entries
            )

            if not same_entries:
                print(
                    "ENTRY_DIFFERENCES:",
                    "NEW",
                    sorted(
                        set(entries)
                        - set(baseline_entries)
                    ),
                    "MISSING",
                    sorted(
                        set(baseline_entries)
                        - set(entries)
                    )
                )

    print("\n" + "=" * 80)
    print("COMBINED RESULTS")
    print("EXP117_BASELINE:",
          round(combined["baseline"], 6))

    for threshold in THRESHOLDS:
        print(
            "THRESHOLD", threshold,
            "NET", round(combined[threshold], 6),
            "DELTA_VS_EXP117",
            round(
                combined[threshold]
                - combined["baseline"], 6
            )
        )

    print("NO PRODUCTION CHANGES")


if __name__ == "__main__":
    main()
