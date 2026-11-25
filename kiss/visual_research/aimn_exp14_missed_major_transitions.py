"""EXP14: offline teacher alignment diagnostic; no trading or new signals."""
import csv
from pathlib import Path
from datetime import datetime
from collections import Counter
from zipfile import ZipFile
ROOT = Path(__file__).resolve().parent

def main():
    source = ROOT / 'aimn_exp13_major_trajectory_audit.csv'
    with source.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    def time(r): return datetime.fromisoformat(r['timestamp_ny'])
    rows.sort(key=time)
    if len({time(r) for r in rows}) != len(rows):
        raise ValueError('Duplicate timestamps')
    signals = [r for r in rows if int(r['exp13_signal']) == 1]
    teachers = [r for r in rows if int(r['teacher_entry']) == 1]
    out = []
    for t in teachers:
        ts = time(t)
        same = [s for s in signals if time(s).date() == ts.date()]
        before = [s for s in same if time(s) < ts]
        after = [s for s in same if time(s) > ts]
        nearest = min(same, key=lambda s: abs(time(s)-ts)) if same else None
        r = dict(teacher_timestamp_ny=t['timestamp_ny'], split=t['split'], teacher_close=t['close'], state_before=t['state_before'], state_after=t['state_after'], reason=t['reason'], rise24_pct=t['rise24_pct'], rise6_pct=t['rise6_pct'], peak_age=t['peak_age'], drawdown_pct=t['drawdown_pct'], warmup_blocked=int(t['state_after']=='WARMUP'), same_day_signals=len(same))
        for label,s in [('earlier',before[-1] if before else None),('later',after[0] if after else None),('nearest',nearest)]:
            r[label+'_timestamp_AUDIT_ONLY']=s['timestamp_ny'] if s else ''
            r[label+'_minutes_AUDIT_ONLY']=int((time(s)-ts).total_seconds()/60) if s else ''
            r[label+'_close_AUDIT_ONLY']=s['close'] if s else ''
            r[label+'_short_price_advantage_pct_AUDIT_ONLY']=round(100*(float(s['close'])/float(t['close'])-1),6) if s else ''
        r['teacher_forward_60m_pct_AUDIT_ONLY']=t['forward_60m_pct_AUDIT_ONLY']
        r['note']='Nearest same-session signal is not proof of same reversal; no execution or risk simulation.'
        out.append(r)
    if not out: raise ValueError('No teacher entries found')
    target=ROOT/'aimn_exp14_missed_major_transitions_audit.csv'
    with target.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    print('Candles:',len(rows),'Signals:',len(signals),'Teachers:',len(teachers))
    print('Teacher states:',dict(Counter(r['state_after'] for r in out)))
    print('Saved:',target)
if __name__=='__main__': main()
