"""Research-only SHORT trade execution simulator."""

def simulate_short_trades(candles, signals):
    """Prepare next-candle SHORT entries without overlapping positions."""
    trades = []
    next_available = 0
    for i in sorted(set(signals)):
        if i + 1 < next_available:
            continue
        if i + 1 >= len(candles):
            continue
        signal = candles[i]
        entry = candles[i + 1]
        if signal["timestamp"][:10] != entry["timestamp"][:10]:
            continue
        exit_data = find_short_exit(
            candles, i + 1, short_stop_price(entry["open"])
        )
        next_available = exit_data["exit_index"] + 1
        trades.append({
            "signal_time": signal["timestamp"],
            "entry_time": entry["timestamp"],
            "entry_price": entry["open"],
            "stop_price": short_stop_price(entry["open"]),
            "exit_time": exit_data["exit_time"],
            "exit_price": exit_data["exit_price"],
            "exit_reason": exit_data["exit_reason"],
            **calculate_short_pnl(
                entry["open"], exit_data["exit_price"]
            ),
        })
    return trades

def short_stop_price(entry_price, stop_pct=0.015):
    """Calculate protective stop above a SHORT entry."""
    return entry_price * (1 + stop_pct)

def check_short_stop(candle, stop_price):
    """Return SHORT stop fill price, or None."""
    if candle["open"] >= stop_price:
        return candle["open"]
    if candle["high"] >= stop_price:
        return stop_price
    return None

def find_short_stop(candles, entry_index, stop_price, max_hold=6):
    """Find the first SHORT stop within the holding window."""
    session = candles[entry_index]["timestamp"][:10]
    end = min(entry_index + max_hold, len(candles))

    for j in range(entry_index, end):
        candle = candles[j]

        if candle["timestamp"][:10] != session:
            break

        fill = check_short_stop(candle, stop_price)

        if fill is not None:
            return {
                "exit_index": j,
                "exit_time": candle["timestamp"],
                "exit_price": fill,
                "exit_reason": "STOP_LOSS",
            }

    return None

def find_short_exit(candles, entry_index, stop_price, max_hold=6):
    """Exit on stop, holding limit, or session end."""
    stopped = find_short_stop(candles, entry_index, stop_price, max_hold)
    if stopped is not None:
        return stopped

    session = candles[entry_index]["timestamp"][:10]
    j = entry_index

    while j + 1 < len(candles) and j + 1 < entry_index + max_hold:
        if candles[j + 1]["timestamp"][:10] != session:
            break
        j += 1

    candle = candles[j]
    return {
        "exit_index": j,
        "exit_time": candle["timestamp"],
        "exit_price": candle["close"],
        "exit_reason": "TIME_EXIT" if j == entry_index + max_hold - 1 else "SESSION_END",
    }

def calculate_short_pnl(entry_price, exit_price, commission_per_side=0.001):
    """Calculate SHORT gross and net returns as percentages."""
    gross_pct = (entry_price - exit_price) / entry_price * 100
    commission_pct = commission_per_side * 2 * 100
    net_pct = gross_pct - commission_pct
    return {
        "gross_pnl_pct": round(gross_pct, 4),
        "commission_pct": round(commission_pct, 4),
        "net_pnl_pct": round(net_pct, 4),
    }
