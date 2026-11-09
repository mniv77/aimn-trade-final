def short_continuation(rows, states, i):
    if i < 2 or states[i] != "SHORT":
        return False
    previous = rows[i - 1]
    current = rows[i]
    recovery = previous["close"] > previous["open"]
    breakdown = current["close"] < previous["low"]
    return recovery and breakdown
