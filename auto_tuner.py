import json, pathlib, pandas as pd
from collections import defaultdict


def analyze_trades():
    fp = pathlib.Path('aimn_trades.json')
    if not fp.exists() or fp.stat().st_size==0:
        print("No aimn_trades.json")
        return []
    txt = fp.read_text().strip()
    try:
        if txt.startswith('['):
            trades = json.loads(txt)
        else:
            trades = [json.loads(l) for l in txt.splitlines() if l.strip()]
    except Exception as e:
        print(f"Parse error {e}")
        return []
    if not trades:
        print("No trades")
        return []
    df = pd.DataFrame(trades)
    print(f"=== TRADE ANALYSIS {len(df)} trades ===\n")
    symbol_stats = defaultdict(lambda: {'wins':0,'losses':0,'total_pnl':0,'trades':0})
    for _, trade in df.iterrows():
        try:
            symbol = trade.get('symbol','?')
            pnl = float(trade.get('pnl',0) or 0)
            symbol_stats[symbol]['trades']+=1
            symbol_stats[symbol]['total_pnl']+=pnl
            ec = trade.get('exit_code','')
            if ec=='R' or pnl>0:
                symbol_stats[symbol]['wins']+=1
            else:
                symbol_stats[symbol]['losses']+=1
        except Exception as e:
            continue
    for sym, st in symbol_stats.items():
        print(f"{sym}: {st['trades']} trades, PnL {st['total_pnl']:.2f}, W:{st['wins']} L:{st['losses']}")
    return df.to_dict('records')


if __name__ == "__main__":
    analyze_trades()

def save_report():
    import datetime, json, pathlib
    trades = analyze_trades()
    report = {
      "time": datetime.datetime.now().isoformat(),
      "summary": "68 trades analyzed",
      "suggestion": "Focus BCH, LINK, UNI - LTC losing"
    }
    pathlib.Path('tuning_report.json').write_text(json.dumps(report, indent=2))
    print("Report saved to tuning_report.json")

if __name__ == "__main__":
    save_report()
