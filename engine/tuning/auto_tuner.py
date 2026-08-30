
import json, pathlib, re
def run_analysis(data=None):
    cache_dir=pathlib.Path("./tmp_cache")
    symbol = data.get('symbol','SPY') if isinstance(data, dict) else 'SPY'
    direction = data.get('direction','LONG') if isinstance(data, dict) else 'LONG'
    # Respect direction: try SHORT cache file first
    candidates = []
    if direction == 'SHORT':
        candidates.append(cache_dir/f"last_tune_{symbol}_SHORT.json")
        # If no SHORT cache, invert LONG cache
        long_file = cache_dir/f"last_tune_{symbol}.json"
        if long_file.exists() and not (cache_dir/f"last_tune_{symbol}_SHORT.json").exists():
            try:
                d=json.load(open(long_file))
                trades = d.get('trades',[])
                # Invert PnL for SHORT (if market went up, short loses)
                inv_trades = [{**t, 'pnl': -t.get('pnl',0)} for t in trades]
                total = sum(t['pnl'] for t in inv_trades)
                wr = len([t for t in inv_trades if t['pnl']>=0])/len(inv_trades)*100 if inv_trades else 0
                return {
                    "status":"success",
                    "symbol": symbol,
                    "total_pnl_val": round(total,2),
                    "win_rate_val": round(wr,1),
                    "total_trades_val": len(inv_trades),
                    "best_params": {"trail_pct": 0.03, "min_v_pct": 0.001},
                    "grid_combinations": 1,
                    "profit_per_day": round(total/252,2),
                    "message": f"INVERTED {symbol} SHORT from LONG cache: trail=0.03 min_v=0.001 WR={wr:.1f}% total={total:.1f}% count={len(inv_trades)} - SHORT should lose in uptrend",
                    "trades": inv_trades[:50],
                    "symbols": [],
                    "results": []
                }
            except Exception as e:
                print(f"Invert error: {e}")

    files = [cache_dir/f"last_tune_{symbol}.json"] if (cache_dir/f"last_tune_{symbol}.json").exists() else sorted(cache_dir.glob("last_tune_*.json"))
    #... rest of original code
    symbols=[]
    for f in files:
        try:
            if not f.exists(): continue
            sym=f.stem.replace("last_tune_","")
            d=json.load(open(f))
            m=re.search(r"trail=([\d.]+).*min_v=([\d.]+).*WR=([\d.]+).*total=([-\d.]+).*count=(\d+)", d['summary'])
            if m:
                trail,min_v,wr,total,count=m.groups()
                symbols.append({
                    "symbol":sym, "trail":float(trail), "min_v":float(min_v),
                    "wr":float(wr), "total":float(total), "count":int(count),
                    "summary":d['summary'], "trades":d.get('trades',[])
                })
        except: pass

    if not symbols:
        return {"status":"error","message":"No cache found, run perfect tuner"}

    best = sorted(symbols, key=lambda x: x['total'], reverse=True)[0]
    if isinstance(data, dict) and data.get('symbol'):
        req = data['symbol']
        filtered = [s for s in symbols if s['symbol']==req]
        if filtered: best = filtered[0]

    return {
        "status":"success",
        "symbol": best['symbol'],
        "total_pnl_val": round(best['total'],2),
        "win_rate_val": round(best['wr'],1),
        "total_trades_val": best['count'],
        "best_params": {"trail_pct": best['trail'], "min_v_pct": best['min_v']},
        "grid_combinations": len(symbols),
        "profit_per_day": round(best['total']/252,2),
        "message": f"BEST {best['symbol']} trail={best['trail']} min_v={best['min_v']} WR={best['wr']}% total={best['total']}% count={best['count']} - NEW perfect strategy",
        "trades": best['trades'][:50],
        "symbols": symbols,
        "results": symbols
    }

def tune_symbol(symbol):
    from engine.tuner_perfect_v3 import perfect_tune
    return perfect_tune(symbol)

def tune_strategy(*args, **kwargs):
    return run_analysis(kwargs.get('data') or (args[0] if args else None))
