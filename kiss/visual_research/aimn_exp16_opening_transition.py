"""Offline opening diagnostic. Bar timestamps assumed to denote bar starts, NY time."""
import csv,json
from pathlib import Path
from datetime import datetime,timedelta
from collections import defaultdict,Counter
from statistics import mean
ROOT=Path(__file__).resolve().parent
STEP=timedelta(minutes=5)
# Fixed exploratory choices, not fitted: 30-minute prior move, 0.20% deadband.
DEADBAND=.20

def pct(a,b): return 100*(a/b-1)
def direction(x): return 'LONG' if x>=DEADBAND else 'SHORT' if x<=-DEADBAND else 'UNCLEAR'
def main():
    candles=json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig'))
    sessions=defaultdict(list)
    with (ROOT/'aimn_exp15_continuous_market_memory_audit.csv').open(newline='',encoding='utf-8-sig') as f:
        audit={r['timestamp_ny']:r for r in csv.DictReader(f)}
    for c in sorted(candles,key=lambda c:c['timestamp']):
        t=datetime.fromisoformat(c['timestamp']); k=t.strftime('%Y-%m-%d %H:%M')
        if abs(float(c['close'])-float(audit[k]['close']))>1e-5: raise ValueError('Price mismatch '+k)
        sessions[t.date()].append((t,c,audit[k]))
    if sum(map(len,sessions.values()))!=len(audit): raise ValueError('Audit length mismatch')
    rows=[]; prev=None
    for day,s in sorted(sessions.items()):
        if len(s)!=78 or s[0][0].strftime('%H:%M')!='09:30' or any(s[i][0]-s[i-1][0]!=STEP for i in range(1,len(s))): raise ValueError('Incomplete session '+str(day))
        for i,(t,c,a) in enumerate(s[:24]):
            p=float(c['close']); op=float(s[0][1]['open']); move=pct(p,op)
            prior=pct(float(prev[-1][1]['close']),float(prev[-7][1]['close'])) if prev else None
            gap=pct(op,float(prev[-1][1]['close'])) if prev else None
            old=direction(prior) if prior is not None else 'UNCLEAR'; new=direction(move)
            cls='UNCONFIRMED' if 'UNCLEAR' in (old,new) else old+'_CONTINUATION' if old==new else old+'_TO_'+new
            r=dict(timestamp_ny=a['timestamp_ny'],decision_time_ny=(t+STEP).strftime('%Y-%m-%d %H:%M'),split=a['split'],minutes_after_open=(i+1)*5,checkpoint=int(i+1 in (1,2,3,6)),prior_30m_pct=prior,overnight_gap_pct=gap,opening_move_pct=move,prior_direction=old,opening_direction=new,classification=cls,short_reversal_candidate=int(cls=='LONG_TO_SHORT'),close=p,teacher_entry=a['teacher_entry'],BASE_signal=a['BASE_signal'],A_signal=a['A_signal'],B_signal=a['B_signal'],forward_60m_short_pct_AUDIT_ONLY=100*(p-float(s[i+12][1]['close']))/p)
            rows.append(r)
        prev=s
    out=ROOT/'aimn_exp16_opening_transition_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print('Sessions',len(sessions),'candles',len(candles),'opening rows',len(rows))
    for minute in (5,10,15,30):
        for split in sorted({r['split'] for r in rows}):
            group=[r for r in rows if r['minutes_after_open']==minute and r['split']==split]; picks=[r for r in group if r['short_reversal_candidate']]; vals=[r['forward_60m_short_pct_AUDIT_ONLY'] for r in picks]
            print(minute,split,dict(Counter(r['classification'] for r in group)), 'SHORT positive',sum(v>0 for v in vals),'of',len(vals),'mean',round(mean(vals),4) if vals else None)
    for r in rows:
        if r['teacher_entry']=='1': print('Teacher',r['timestamp_ny'],r['classification'],r['prior_30m_pct'],r['opening_move_pct'])
    for m in ('BASE','A','B'):
        picks=[r for r in rows if r[m+'_signal']=='1']; print(m,'morning signals',len(picks),'mean',mean(r['forward_60m_short_pct_AUDIT_ONLY'] for r in picks) if picks else None)
    print('Saved',out)
if __name__=='__main__': main()
