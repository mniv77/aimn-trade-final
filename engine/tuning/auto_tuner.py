import json, pathlib, re
def run_analysis():
    """Fixed to use perfect cache - new good strategy"""
    symbols=[]
    cache_dir=pathlib.Path("./tmp_cache")
    for f in sorted(cache_dir.glob("last_tune_*.json")):
        try:
            sym=f.stem.replace("last_tune_","")
            data=json.load(open(f))
            m=re.search(r"trail=([\d.]+).*min_v=([\d.]+).*WR=([\d.]+).*total=([-\d.]+).*count=(\d+)", data['summary'])
            if m:
                trail,min_v,wr,total,count=m.groups()
                symbols.append({
                    "symbol":sym, "trail":trail, "min_v":min_v, 
                    "wr":float(wr), "total":float(total), "count":int(count),
                    "summary":data['summary']
                })
        except Exception as e:
            print(f"Skip {f}: {e}")
    symbols=sorted(symbols, key=lambda x: x['total'], reverse=True)
    total_trades=sum(s['count'] for s in symbols if s['total']>0)
    return symbols, total_trades

def tune_symbol(symbol):
    from engine.tuner_perfect_v3 import perfect_tune
    return perfect_tune(symbol)
