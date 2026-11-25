#!/usr/bin/env python3
"""AIMn Experiment 5: continuous causal SHORT transition episodes (research only).
Usage: python aimn_exp5_continuous_transition.py CANDLES.json TEACHING.json OUTPUT.csv
No broker calls. Labels and future prices are audit-only, never signal inputs.
Rules fixed before viewing evaluation results; not a trained predictive model.
"""
import csv, json, sys
from collections import Counter

def pct(a,b): return 100*(a/b-1) if b else 0.0

def run(candles, lessons):
    candles=sorted(candles,key=lambda x:x['timestamp'])
    assert len({c['timestamp'] for c in candles})==len(candles)
    teachers={x['market_timestamp']:x for x in lessons if x['kind']=='ENTER_SHORT'}
    rows=[]; state='SEEK'; episode=0; peak=None; peak_i=-1; weak_count=0; low_breaks=0; last_signal=-9999; day=None
    for i,c in enumerate(candles):
        t=c['timestamp'][:16]; d=t[:10]
        if d!=day:
            state='SEEK'; peak=None; peak_i=-1; weak_count=0; low_breaks=0; last_signal=-9999; day=d
        if i<24: continue
        prev=candles[i-1]; hist=candles[max(0,i-12):i]; recent6=candles[i-6:i]
        rise12=pct(prev['close'],candles[i-12]['close']); rise6=pct(prev['close'],candles[i-6]['close'])
        change1=pct(c['close'],prev['close']); change3=pct(c['close'],candles[i-3]['close'])
        prior_low=min(x['low'] for x in recent6); prior_high=max(x['high'] for x in hist)
        near_high=pct(prior_high,c['close'])<=0.70
        approach=rise12>=0.30 and rise6>=0.05 and near_high
        signal=0; reason=''; before=state
        if state=='SEEK':
            if approach:
                episode+=1; state='TRACK'; peak=c['high']; peak_i=i; weak_count=0; low_breaks=0
        elif state=='TRACK':
            if c['high']>peak:
                peak=c['high']; peak_i=i; weak_count=0; low_breaks=0
            drawdown=pct(peak,c['close']); age=i-peak_i
            if change1< -0.06: weak_count+=1
            elif change1>0.12: weak_count=max(0,weak_count-1)
            if c['close']<prior_low: low_breaks+=1
            # A small failed-recovery decline OR structural break, both requiring
            # a tracked peak and observable weakening. No future confirmation.
            early=(2<=age<=12 and 0.18<=drawdown<=1.50 and weak_count>=2 and change3<=-0.10)
            confirmed=(age>=1 and drawdown>=0.30 and low_breaks>=1 and change3<=-0.18)
            if early or confirmed:
                signal=1; reason='EARLY_FAILED_RECOVERY' if early else 'STRUCTURAL_BREAK'; state='LOCKED'; last_signal=i
            elif age>24 or drawdown>3.0:
                state='SEEK'
        else:  # locked; do not emit again until a new sustained upward setup
            if i-last_signal>=12 and approach and change3>0.15:
                state='TRACK'; episode+=1; peak=c['high']; peak_i=i; weak_count=0; low_breaks=0
        drawdown=pct(peak,c['close']) if peak is not None else ''
        future=''
        if i+12<len(candles) and candles[i+12]['timestamp'][:10]==d:
            future=round(-pct(candles[i+12]['close'],c['close']),4)
        teacher=teachers.get(t)
        rows.append(dict(timestamp_ny=t,split='EVALUATION_AUG' if t[:7]=='2026-08' else 'DEVELOPMENT_JUN_JUL',
            close=c['close'],rise12_pct=round(rise12,4),rise6_pct=round(rise6,4),change1_pct=round(change1,4),change3_pct=round(change3,4),
            prior_6_low=prior_low,prior_12_high=prior_high,episode_id=episode if state!='SEEK' else '',
            state_before=before,state_after=state,peak_price=round(peak,4) if peak is not None else '',
            candles_since_peak=i-peak_i if peak_i>=0 else '',drawdown_from_peak_pct=round(drawdown,4) if drawdown!='' else '',
            weakening_count=weak_count,structural_break_count=low_breaks,v5_signal=signal,v5_reason=reason,
            teacher_entry=int(teacher is not None),teacher_confidence=teacher['confidence'] if teacher else '',
            forward_12_candle_short_pct_RESEARCH_ONLY=future))
    return rows,teachers

def main():
    if len(sys.argv)!=4: raise SystemExit('Usage: python aimn_exp5_continuous_transition.py CANDLES.json TEACHING.json OUTPUT.csv')
    with open(sys.argv[1],encoding='utf8') as f: candles=json.load(f)
    with open(sys.argv[2],encoding='utf8') as f: lessons=json.load(f)['lessons']
    rows,teachers=run(candles,lessons)
    with open(sys.argv[3],'w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('Experiment 5 — causal research, not trading')
    for split in ['DEVELOPMENT_JUN_JUL','EVALUATION_AUG']:
        r=[x for x in rows if x['split']==split];s=[x for x in r if x['v5_signal']]
        obs=[x['forward_12_candle_short_pct_RESEARCH_ONLY'] for x in s if x['forward_12_candle_short_pct_RESEARCH_ONLY']!='']
        print(split,'signals',len(s),'paths',dict(Counter(x['v5_reason'] for x in s)),'exact_teacher',sum(x['teacher_entry'] for x in s),'/',sum(x['teacher_entry'] for x in r),'one_hour_positive',sum(x>0 for x in obs),'/',len(obs),'mean_gross',round(sum(obs)/len(obs),4) if obs else None)
    aug4=[x for x in rows if x['timestamp_ny'].startswith('2026-08-04') and x['v5_signal']]
    print('August 4 signals',[(x['timestamp_ny'],x['forward_12_candle_short_pct_RESEARCH_ONLY']) for x in aug4])
    print('Teacher rows matched',sum(x['teacher_entry'] for x in rows),'of',len(teachers))
if __name__=='__main__':main()
