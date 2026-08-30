import json, pathlib, re

def run_analysis(data=None):
    cache_dir = pathlib.Path("./tmp_cache")
    symbol = (data.get('symbol','MSFT') if isinstance(data, dict) else 'MSFT').upper()
    direction = (data.get('direction','LONG') if isinstance(data, dict) else 'LONG').upper()
    timeframe = data.get('timeframe','1hr') if isinstance(data, dict) else '1hr'

    # Try direction-specific cache first
    specific_file = cache_dir/f"last_tune_{symbol}_{direction}.json"
    base_file = cache_dir/f"last_tune_{symbol}.json"

    target_file = None
    if specific_file.exists():
        target_file = specific_file
    elif base_file.exists():
        target_file = base_file
    else:
        # Symbol not tuned yet - return error, DON'T fallback to other symbol
        return {
            "status":"error",
            "symbol": symbol,
            "message": f"No cache for {symbol} {direction}. Run perfect_tune {symbol} first",
            "total_pnl_val": 0,
            "win_rate_val": 0,
            "total_trades_val": 0,
            "avg_pnl_val": 0,
            "trades": [],
            "trades_val": 0,
            "avg_pnl_val": 0
        }

    try:
        d = json.loads(target_file.read_text())
        trades = d.get('trades', [])

        # Parse summary: BEST trail=0.03 min_v=0.001 WR=53.8% total=62.9% count=26
        m = re.search(r"WR=([\d.]+)%.*total=([-\d.]+)%.*count=(\d+)", d.get('summary',''))
        if m:
            wr, total, count = m.groups()
            wr_f = float(wr)
            total_f = float(total)
            count_i = int(count)
        else:
            # Calculate from trades if summary fails
            total_f = sum(t.get('pnl',0) for t in trades)
            wr_f = len([t for t in trades if t.get('pnl',0)>=0])/len(trades)*100 if trades else 0
            count_i = len(trades)

        # HANDLE SHORT: invert if we only have LONG cache
        is_inverted = False
        if direction == 'SHORT' and target_file == base_file:
            # Invert LONG trades for SHORT
            total_f = -total_f
            wr_f = 100 - wr_f
            trades = [{**t, 'pnl': -t.get('pnl',0)} for t in trades]
            is_inverted = True

        avg_f = total_f / count_i if count_i else 0

        # Build full response with ALL field names frontend expects
        summary_prefix = "INVERTED " if is_inverted else ""
        return {
            "status":"success",
            "symbol": symbol,
            "direction": direction,
            "timeframe": timeframe,
            "total_pnl_val": round(total_f,2),
            "win_rate_val": round(wr_f,1),
            "total_trades_val": count_i,
            "avg_pnl_val": round(avg_f,2),
            # Duplicates for old frontend compat
            "trades_val": count_i,
            "total_pnl": f"{total_f:.1f}%",
            "win_rate": f"{wr_f:.1f}%",
            "avg_pnl": f"{avg_f:.2f}%",
            "best_params": {"trail_pct": 0.03, "min_v_pct": 0.001},
            "grid_combinations": 1,
            "profit_per_day": round(total_f/252,2),
            "message": f"{summary_prefix}BEST {symbol} {direction} trail=0.03 min_v=0.001 WR={wr_f:.1f}% total={total_f:.1f}% count={count_i}",
            "trades": trades[:100],
            "symbols": [{"symbol": symbol, "total": total_f, "wr": wr_f, "count": count_i}],
            "results": []
        }
    except Exception as e:
        return {"status":"error","message":f"Cache error {e}: {target_file}","total_pnl_val":0,"total_trades_val":0,"win_rate_val":0,"avg_pnl_val":0,"trades":[],"trades_val":0}

def tune_symbol(symbol):
    from engine.tuner_perfect_v3 import perfect_tune
    return perfect_tune(symbol)

def tune_strategy(*a, **kw):
    return run_analysis(kw.get('data') or (a[0] if a else None))
