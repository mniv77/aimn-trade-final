"""Offline EXP17. No live trading. Signal-close reference and next-open sensitivity."""
import csv,json,statistics as st
from pathlib import Path
from datetime import datetime,timedelta
from collections import defaultdict
ROOT=Path(__file__).resolve().parent
FEE=.001
STEP=timedelta(minutes=5)
def net(p,q): return 100*((p-q)-FEE*(p+q))/p
def main():
    candles=json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig'))
    days=defaultdict(list)
    for c in sorted(candles,key=lambda c:c['timestamp']):
        t=datetime.fromisoformat(c['timestamp']); days[t.date()].append((t,c))
    with (ROOT/'aimn_exp16_opening_transition_audit.csv').open(newline='',encoding='utf-8-sig') as f: audit=list(csv.DictReader(f))
    lookup={t.strftime('%Y-%m-%d %H:%M'):(t,c) for s in days.values() for t,c in s}
    for r in audit:
        if abs(float(r['close'])-float(lookup[r['timestamp_ny']][1]['close']))>1e-5: raise ValueError('Price mismatch '+r['timestamp_ny'])
    rows=[]
    for r in audit:
        if r['minutes_after_open']!='5' or r['short_reversal_candidate']!='1': continue
        t,c=lookup[r['timestamp_ny']]; s=days[t.date()]; path=s[1:13]
        if t!=s[0][0] or len(path)!=12 or any(u!=t+STEP*(i+1) for i,(u,b) in enumerate(path)): raise ValueError('Incomplete opening path')
        p=float(c['close']); o=float(c['open']); h=float(c['high']); l=float(c['low']); q=float(path[-1][1]['close'])
        gross=100*(p-q)/p
        if abs(gross-float(r['forward_60m_short_pct_AUDIT_ONLY']))>1e-6: raise ValueError('EXP16 outcome mismatch')
        row={k:r[k] for k in ('timestamp_ny','decision_time_ny','split','prior_30m_pct','overnight_gap_pct','opening_move_pct')}
        row.update(entry_reference_close=p,opening_body_pct=100*(p-o)/o,upper_wick_pct=100*(h-max(o,p))/o,lower_wick_pct=100*(min(o,p)-l)/o,opening_range_pct=100*(h-l)/o,gross_60m_pct=gross,net_60m_pct=net(p,q),next_open_net_60m_pct=net(float(path[0][1]['open']),q),mae_pct=max(0,100*(max(float(b['high']) for _,b in path)-p)/p),mfe_pct=max(0,100*(p-min(float(b['low']) for _,b in path))/p))
        for stop,label in ((.005,'05'),(.01,'10')):
            level=p*(1+stop); hit=next(((u,b) for u,b in path if float(b['high'])>=level),None)
            row['stop_'+label+'_touch']=int(hit is not None)
            row['stop_'+label+'_time']=hit[0].isoformat() if hit else ''
            row['stop_'+label+'_net_pct']=net(p,max(level,float(hit[1]['open'])) if hit else q)
        rows.append(row)
    if not rows: raise ValueError('No EXP16 candidates')
    out=ROOT/'aimn_exp17_opening_reversal_quality_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for split in ['ALL']+sorted({r['split'] for r in rows}):
        g=[r for r in rows if split=='ALL' or r['split']==split]
        print(split,len(g))
        for k in ('gross_60m_pct','net_60m_pct','next_open_net_60m_pct','stop_05_net_pct','stop_10_net_pct'):
            print(k,'positive',sum(r[k]>0 for r in g),'mean',round(st.mean(r[k] for r in g),4))
        print('stop touches',sum(r['stop_05_touch'] for r in g),sum(r['stop_10_touch'] for r in g))
    for positive in (True,False):
        g=[r for r in rows if (r['gross_60m_pct']>0)==positive]
        if g: print('Gross positive?',positive,'medians', {k:round(st.median(float(r[k]) for r in g),4) for k in ('prior_30m_pct','overnight_gap_pct','opening_body_pct','upper_wick_pct','mae_pct','mfe_pct')})
    print('Saved',out)
if __name__=='__main__': main()
