"""Offline EXP19: causal trend stages around unchanged EXP13 signals."""
import csv,json
from pathlib import Path
from datetime import datetime,timedelta
from collections import Counter
from statistics import mean
ROOT=Path(__file__).resolve().parent

def main():
    bars=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text()),key=lambda b:b['timestamp'])
    with (ROOT/'aimn_exp13_major_trajectory_audit.csv').open(newline='') as f: base=list(csv.DictReader(f))
    assert len(bars)==len(base)
    times=[datetime.fromisoformat(b['timestamp']) for b in bars]
    assert len(set(times))==len(times)
    rows=[]; peak=low=None; start=None; low_i=None; hist=[]
    for i,(b,r,t) in enumerate(zip(bars,base,times)):
        p,h,l=map(float,(b['close'],b['high'],b['low']))
        assert t.strftime('%Y-%m-%d %H:%M')==r['timestamp_ny'] and abs(p-float(r['close']))<1e-5
        if i==0 or t-times[i-1]!=timedelta(minutes=5):
            peak=low=start=low_i=None; hist=[]
        signal=int(r['exp13_signal']); state=r['state_after']; stage=state; dd=rebound=age=''; exit_signal=0
        if signal:
            peak=p/(1-float(r['drawdown_pct'])/100); start=i; low=p; low_i=i; stage='EARLY_SHORT'
        elif start is not None:
            if l<low: low=l; low_i=i
            dd=100*(peak-p)/peak; rebound=100*(p-low)/low; age=i-start
            # Require a close above the preceding three highs for structural reversal.
            reverse=len(hist)>=3 and p>max(x['high'] for x in hist[-3:]) and rebound>=0.30
            if reverse or state=='LONG': stage='REVERSE_TRANSITION'; exit_signal=1; start=None
            elif rebound>=0.30: stage='POTENTIAL_EXHAUSTION'
            elif rebound>=0.15: stage='V_NOISE_CANDIDATE'
            elif age<=3: stage='EARLY_SHORT'
            else: stage='ESTABLISHED_SHORT'
        if signal: dd=100*(peak-p)/peak; rebound=0; age=0
        hist.append(b)
        rows.append(dict(timestamp_ny=r['timestamp_ny'],split=r['split'],close=p,baseline_state=state,entry_signal=signal,teacher_entry=r['teacher_entry'],stage=stage,age_bars=age,drawdown_from_peak_pct=dd,rebound_from_running_low_pct=rebound,reverse_signal=exit_signal))
    # Separate forward outcomes, never inputs to stage recognition.
    for i,r in enumerate(rows):
        r['forward_30m_short_pct_AUDIT_ONLY']=''
        if i+6<len(rows) and times[i+6]-times[i]==timedelta(minutes=30): r['forward_30m_short_pct_AUDIT_ONLY']=100*(r['close']-rows[i+6]['close'])/r['close']
    out=ROOT/'aimn_exp19_trend_position_audit.csv'
    with out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print('Candles',len(rows),'sessions',len({t.date() for t in times}),'entries',sum(r['entry_signal'] for r in rows),'reverse signals',sum(r['reverse_signal'] for r in rows))
    for split in sorted({r['split'] for r in rows}):
        print(split)
        for stage in sorted({r['stage'] for r in rows}):
            g=[r for r in rows if r['split']==split and r['stage']==stage]; v=[r['forward_30m_short_pct_AUDIT_ONLY'] for r in g if r['forward_30m_short_pct_AUDIT_ONLY']!='']; print(stage,len(g),len(v),round(mean(v),4) if v else None)
    print('Saved',out)
if __name__=='__main__': main()
