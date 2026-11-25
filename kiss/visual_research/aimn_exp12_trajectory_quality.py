"""EXP12: offline causal feature audit of EXP11 new signals. No trading."""
import csv, json, sys
from pathlib import Path
from datetime import datetime, timedelta
from statistics import mean, median
from collections import defaultdict
ROOT = Path(__file__).resolve().parent
FEATURES = ['rise6_pct','rise12_pct','rise24_pct','prior6_rise_pct','momentum_change_pct','efficiency12','up_fraction12','peak_age12','drawdown12_pct','lower_high_fraction6','lower_low_fraction6','rsi14_simple']
def pct(a,b): return 100*(a/b-1)
def main():
    source = Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'aimn_nvda_candles.json'
    audit = Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'aimn_exp11_signal_quality_audit.csv'
    output = Path(sys.argv[3]) if len(sys.argv)>3 else ROOT/'aimn_exp12_trajectory_quality_audit.csv'
    candles=json.loads(source.read_text(encoding='utf-8-sig'))
    candles.sort(key=lambda c:c['timestamp'])
    times=[datetime.fromisoformat(c['timestamp']) for c in candles]
    idx={t.strftime('%Y-%m-%d %H:%M'):i for i,t in enumerate(times)}
    if len(idx)!=len(candles): raise ValueError('Duplicate candle timestamps')
    with audit.open(newline='',encoding='utf-8-sig') as f: signals=list(csv.DictReader(f))
    out=[]
    for s in signals:
        if s['category']!='NEW': continue
        i=idx[s['timestamp_ny']]; t=times[i]; price=float(candles[i]['close'])
        if abs(price-float(s['close']))>0.00001: raise ValueError('Price mismatch '+str(t))
        def window(n):
            if i<n or any(times[j]!=t-timedelta(minutes=5*(i-j)) or times[j].date()!=t.date() for j in range(i-n,i+1)): return None
            return candles[i-n:i+1]
        f={k:'' for k in FEATURES}
        for n in (6,12,24):
            w=window(n)
            if w: f[f'rise{n}_pct']=pct(price,float(w[0]['close']))
        w=window(12)
        if w:
            c=[float(x['close']) for x in w]; d=[b-a for a,b in zip(c,c[1:])]; h=[float(x['high']) for x in w]
            f.update(prior6_rise_pct=pct(c[6],c[0]),momentum_change_pct=pct(c[-1],c[6])-pct(c[6],c[0]),efficiency12=(c[-1]-c[0])/sum(map(abs,d)) if any(d) else 0,up_fraction12=sum(x>0 for x in d)/12,peak_age12=12-max(j for j,x in enumerate(h) if x==max(h)),drawdown12_pct=100*(max(h)-price)/max(h))
        w=window(6)
        if w:
            for k in ('high','low'): f[f'lower_{k}_fraction6']=sum(float(b[k])<float(a[k]) for a,b in zip(w,w[1:]))/6
        w=window(14)
        if w:
            c=[float(x['close']) for x in w]; d=[b-a for a,b in zip(c,c[1:])]; gain=sum(max(x,0) for x in d); loss=sum(max(-x,0) for x in d)
            f['rsi14_simple']=100*gain/(gain+loss) if gain+loss else 50
        raw=s['forward_12_candle_short_pct_AUDIT_ONLY']; v=float(raw) if raw else None
        if v is not None:
            if i+12>=len(times) or any(times[i+j]!=t+timedelta(minutes=5*j) or times[i+j].date()!=t.date() for j in range(1,13)): raise ValueError('Invalid outcome horizon '+str(t))
            actual=100*(price-float(candles[i+12]['close']))/price
            if abs(actual-v)>0.00011: raise ValueError('Outcome mismatch '+str(t))
        out.append(dict(timestamp_ny=s['timestamp_ny'],split=s['split'],close=price,reason=s['exp10_reason'],minutes_since_recovery=s['minutes_since_recovery'],**{k:round(x,6) if x!='' else '' for k,x in f.items()},forward_return_pct_AUDIT_ONLY=raw,outcome_AUDIT_ONLY='MISSING' if v is None else 'POSITIVE' if v>0 else 'NEGATIVE' if v<0 else 'FLAT'))
    if not out: raise ValueError('No NEW signals')
    with output.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    groups=defaultdict(list)
    for r in out: groups[r['split'],r['outcome_AUDIT_ONLY']].append(r)
    for key, rows in sorted(groups.items()):
        print(*key,len(rows))
        for k in FEATURES:
            vals=[r[k] for r in rows if r[k]!='']; print(k, 'median',round(median(vals),4) if vals else None,'n',len(vals))
    print('Saved:',output)
if __name__=='__main__': main()
