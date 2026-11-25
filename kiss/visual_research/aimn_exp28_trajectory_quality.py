"""EXP28: causal close-only directional changes; forward diagnostics are research only."""
import csv,json,statistics
from pathlib import Path
from datetime import datetime
from collections import defaultdict
ROOT=Path(__file__).resolve().parent

def main():
    bars=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda b:b['timestamp'])
    with (ROOT/'aimn_exp19_trend_position_audit.csv').open() as f: ref=list(csv.DictReader(f))
    ts=[datetime.fromisoformat(b['timestamp']) for b in bars]; c=[float(b['close']) for b in bars]
    assert len(bars)==len(ref)==4680 and len(set(ts))==len(ts)
    assert all(t.strftime('%Y-%m-%d %H:%M')==r['timestamp_ny'] and abs(p-float(r['close']))<1e-8 for t,p,r in zip(ts,c,ref)), 'Source mismatch'
    days=defaultdict(list)
    for i,t in enumerate(ts): days[t.date()].append(i)
    rows=[]
    for threshold in (.003,.005,.0075,.01):
        for day,ix in days.items():
            state='SEEK'; hi=lo=ix[0]; extreme=ix[0]; serial=0; last=None
            for i in ix:
                old=state; pivot=None
                if state=='SEEK':
                    if c[i]>c[hi]: hi=i
                    if c[i]<c[lo]: lo=i
                    if c[i]/c[lo]-1>=threshold: state='LONG'
                    elif 1-c[i]/c[hi]>=threshold: state='SHORT'
                elif state=='LONG':
                    if c[i]>c[extreme]: extreme=i
                    if 1-c[i]/c[extreme]>=threshold: pivot=extreme; state='SHORT'
                else:
                    if c[i]<c[extreme]: extreme=i
                    if c[i]/c[extreme]-1>=threshold: pivot=extreme; state='LONG'
                if state!=old:
                    serial+=1; extreme=i
                    if pivot is not None:
                        sign=1 if state=='LONG' else -1
                        row=dict(threshold_pct=threshold*100,split=ref[i]['split'],signal_time=ref[i]['timestamp_ny'],direction=state,trajectory_id=f'{day}:{serial}',pivot_time=ref[pivot]['timestamp_ny'],pivot_close=c[pivot],signal_close=c[i],delay_minutes=(ts[i]-ts[pivot]).total_seconds()/60,confirmation_move_pct=sign*(c[i]/c[pivot]-1)*100,prior_state_minutes=(ts[i]-ts[last]).total_seconds()/60 if last is not None else '',exp13_same_candle_short=int(ref[i]['entry_signal']) if state=='SHORT' else '',forward_30m_directional_pct_RESEARCH_ONLY=sign*(c[i+6]/c[i]-1)*100 if i+6<=ix[-1] else '',next_reversal_minutes_RESEARCH_ONLY='',quick_reverse_15m_RESEARCH_ONLY='')
                        if rows and rows[-1]['threshold_pct']==threshold*100 and rows[-1]['signal_time'][:10]==str(day):
                            prev=rows[-1]; duration=(ts[i]-datetime.fromisoformat(prev['signal_time'])).total_seconds()/60; prev['next_reversal_minutes_RESEARCH_ONLY']=duration;prev['quick_reverse_15m_RESEARCH_ONLY']=int(duration<=15)
                        rows.append(row)
                    last=i
            # No future session information used in recognition; end-of-day censoring for diagnostics.
            for row in reversed(rows):
                if row['threshold_pct']!=threshold*100 or row['signal_time'][:10]!=str(day): break
                if row['quick_reverse_15m_RESEARCH_ONLY']=='':
                    if (ts[ix[-1]]-datetime.fromisoformat(row['signal_time'])).total_seconds()>=15: row['quick_reverse_15m_RESEARCH_ONLY']=0
    out=ROOT/'aimn_exp28_trajectory_quality_audit.csv'
    with out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(len(bars),'candles',len(days),'sessions')
    for th in (.3,.5,.75,1.):
        for split in ('ALL','DEVELOPMENT_JUN_JUL','EVALUATION_AUG'):
            g=[r for r in rows if r['threshold_pct']==th and (split=='ALL' or r['split']==split)]
            s=[r for r in g if r['direction']=='SHORT']; l=[r for r in g if r['direction']=='LONG']; q=[r['quick_reverse_15m_RESEARCH_ONLY'] for r in g if r['quick_reverse_15m_RESEARCH_ONLY']!='']; f=[r['forward_30m_directional_pct_RESEARCH_ONLY'] for r in s if r['forward_30m_directional_pct_RESEARCH_ONLY']!='']
            print(th,split,len(s),len(l),statistics.median(r['delay_minutes'] for r in s),statistics.median(r['delay_minutes'] for r in l),sum(q),len(q),sum(r['exp13_same_candle_short'] for r in s),len(f),round(statistics.mean(f),4))
    print('Saved',out)
if __name__=='__main__':main()
