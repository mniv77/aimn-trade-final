#!/usr/bin/env python3
"""AIMn Exp3: teacher vs August 4 V2 false-signal diagnostic. Research only.
Usage: python aimn_exp3_transition_diagnostic.py CANDLES.json TEACHING.json V2_AUDIT.csv OUTPUT.csv
All feature columns use current/prior completed candles; forward return is audit-only.
"""
import csv,json,sys
from collections import Counter

def pct(a,b): return (a/b-1)*100 if b else 0.0

def run(candles, lessons, v2rows):
    candles=sorted(candles,key=lambda c:c['timestamp']); bytime={c['timestamp'][:16]:i for i,c in enumerate(candles)}
    v2={r['timestamp_ny']:r for r in v2rows}
    teacher={x['market_timestamp']:x for x in lessons if x['kind']=='ENTER_SHORT'}
    targets=set(teacher)|{t for t,r in v2.items() if t.startswith('2026-08-04') and r['v2_entry_signal']=='1'}
    out=[]
    for t in sorted(targets):
        if t not in bytime: continue
        i=bytime[t]; c=candles[i]; day=t[:10]
        if i<36:continue
        prev=candles[i-1]; pre=candles[i-12:i]; prior30=candles[i-30:i]
        # slopes in sequential 6-candle windows; no future candles in these features
        slope_early=pct(candles[i-6]['close'],candles[i-12]['close'])
        slope_late=pct(c['close'],candles[i-6]['close'])
        peak=max(x['high'] for x in prior30)
        body=pct(c['close'],c['open'])
        span=c['high']-c['low']
        close_location=(c['close']-c['low'])/span if span else 0.5
        future=''
        if i+12<len(candles) and candles[i+12]['timestamp'][:10]==day:
            future=round(pct(c['close'],candles[i+12]['close']),4)
        label=teacher.get(t)
        out.append(dict(timestamp_ny=t,case_type='TEACHER_ENTRY' if label else 'AUG04_V2_SIGNAL',
          confidence=label['confidence'] if label else '',teacher_note=label['note'] if label else '',
          close=c['close'],v2_signal=v2.get(t,{}).get('v2_entry_signal',''),
          v2_score=v2.get(t,{}).get('score',''),
          prior_12_return_pct=round(pct(prev['close'],candles[i-12]['close']),4),
          early_6_slope_pct=round(slope_early,4),late_6_slope_pct=round(slope_late,4),
          trajectory_bend_pct=round(slope_late-slope_early,4),
          distance_below_30bar_high_pct=round(pct(peak,c['close']),4),
          current_body_pct=round(body,4),close_location_in_range=round(close_location,4),
          prior_12_high=max(x['high'] for x in pre),
          forward_12_short_pct_AUDIT_ONLY=future))
    return out

def main():
    if len(sys.argv)!=5:raise SystemExit('Usage: python script.py CANDLES.json TEACHING.json V2_AUDIT.csv OUTPUT.csv')
    with open(sys.argv[1]) as f:candles=json.load(f)
    with open(sys.argv[2]) as f:lessons=json.load(f)['lessons']
    with open(sys.argv[3],newline='') as f:v2rows=list(csv.DictReader(f))
    rows=run(candles,lessons,v2rows)
    with open(sys.argv[4],'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('cases:',dict(Counter(r['case_type'] for r in rows)))
    print('teacher V2 exact:',sum(r['case_type']=='TEACHER_ENTRY' and r['v2_signal']=='1' for r in rows))
    print('Audit only; no fitted model, no new entry rule, no live trading.')
if __name__=='__main__':main()
