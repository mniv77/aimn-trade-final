import json, pathlib, re
def run_analysis(data=None):
    """Fixed to use perfect cache - new good strategy - accepts app.py param"""
    symbols=[]
    cache_dir=pathlib.Path("./tmp_cache")
    # If specific symbol requested from UI
    if data and isinstance(data, dict) and data.get('symbol'):
        sym_filter=data.get('symbol')
        files=[cache_dir/f"last_tune_{sym_filter}.json"] if (cache_dir/f"last_tune_{sym_filter}.json").exists() else sorted(cache_dir.glob("last_tune_*.json"))
    else:
        files=sorted(cache_dir.glob("last_tune_*.json"))

    for f in files:
        try:
            if not f.exists(): continue
            sym=f.stem.replace("last_tune_","")
            d=json.load(open(f))
            m=re.search(r"trail=([\d.]+).*min_v=([\d.]+).*WR=([\d.]+).*total=([-\d.]+).*count=(\d+)", d['summary'])
            if m:
                trail,min_v,wr,total,count=m.groups()
                symbols.append({
                    "symbol":sym, "trail":trail, "min_v":min_v,
                    "wr":float(wr), "total":float(total), "count":int(count),
                    "summary":d['summary'], "trades":d.get('trades',[])[:20]
                })
        except Exception as e:
            print(f"Skip {f}: {e}")

    symbols=sorted(symbols, key=lambda x: x['total'], reverse=True)
    total_trades=sum(s['count'] for s in symbols if s['total']>0)

    # Return format app.py expects
    return {
        "symbols": symbols,
        "total_trades": total_trades,
        "best": symbols[0] if symbols else None,
        "status": "success",
        "message": f"{len(symbols)} symbols, {total_trades} trades - NEW perfect strategy",
        "grid_combinations": len(symbols),
        "results": symbols # for chart
    }

def tune_symbol(symbol):
    from engine.tuner_perfect_v3 import perfect_tune
    return perfect_tune(symbol)

def tune_strategy(*args, **kwargs):
    return run_analysis(kwargs.get('data') or (args[0] if args else None))
