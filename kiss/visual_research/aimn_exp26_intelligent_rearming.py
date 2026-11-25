"""EXP26 offline fixed-candidate audit; run beside EXP25 CSV and candles."""
import csv,json,zipfile
from pathlib import Path
from datetime import datetime,timedelta
ROOT=Path(__file__).resolve().parent
POLICIES=('baseline','mem30','mem60','mem90','int1','int2','int3')
def main():
    bars=sorted(json.loads((ROOT/'aimn_nvda_candles.json').read_text(encoding='utf-8-sig')),key=lambda b:b['timestamp'])
    times=[datetime.fromisoformat(b['timestamp']) for b in bars]
    idx={t.strftime('%Y-%m-%d %H:%M'):i for i,t in enumerate(times)}
    if len(idx)!=len(bars):raise ValueError('Duplicate candle timestamps')
    with (ROOT/'aimn_exp25_major_local_trend_audit.csv').open(encoding='utf-8-sig',newline='') as f: source=list(csv.DictReader(f))
    history={p:[] for p in POLICIES}; rows=[]
    for r in sorted(source,key=lambda r:r['signal_time']):
        s,e,x=(idx[r[k]] for k in ('signal_time','entry_time','exit_time')); net=float(r['net_pct'])
        if not s+1==e<=x or abs(float(bars[e]['open'])-float(r['entry_price']))>1e-8:raise ValueError('Entry mismatch')
        row=dict(r)
        for p in POLICIES:
            losses=[(j,n) for j,n in history[p] if j<s and times[j].date()==times[s].date() and n<=0]
            j=losses[-1][0] if losses else None
            age=(times[s]-times[j]).total_seconds()/60 if j is not None else None
            long=False; structure=False; rise=0.; pullback=0.
            if j is not None and s-j>=4:
                # Exclude the exit candle and signal candle from peak formation.
                k=max(range(j+1,s),key=lambda i:float(bars[i]['high']))
                low=min(float(bars[i]['low']) for i in range(j+1,k+1))
                peak=float(bars[k]['high']); close=float(bars[s]['close'])
                rise=100*(peak/low-1); pullback=100*(1-close/peak)
                long=k>=j+3 and rise>=.50 and float(bars[k]['close'])>float(bars[j+1]['close'])
                structure=k<s and peak>float(bars[j]['high']) and pullback>=.30 and close<min(float(bars[i]['low']) for i in range(s-3,s))
            limit={'mem30':30,'mem60':60,'mem90':90}.get(p,60)
            rearm={'int1':long,'int2':structure,'int3':long and structure}.get(p,False)
            accept=p=='baseline' or age is None or age>limit or rearm
            row.update({p+'_accept':int(accept),p+'_net_pct':net if accept else 0.,p+'_loss_age_minutes':age,p+'_recovery_pct':rise,p+'_pullback_pct':pullback,p+'_early_rearm':int(bool(age is not None and age<=limit and rearm))})
            if accept:history[p].append((x,net))
        if row['mem60_accept']!=int(r['mtl3_accept']):raise ValueError('EXP25 memory mismatch '+r['episode'])
        rows.append(row)
    out=ROOT/'aimn_exp26_intelligent_rearming_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for label,g in [('ALL',rows)]+[(k,[r for r in rows if r['split']==k]) for k in sorted({r['split'] for r in rows})]:
        print(label)
        for p in POLICIES:
            a=[r for r in g if r[p+'_accept']];print(p,len(a),sum(float(r['net_pct'])>0 for r in a),sum(float(r['net_pct'])<0 for r in a),round(sum(r[p+'_net_pct'] for r in g),4),sum(r[p+'_early_rearm'] for r in g))
    for r in rows:
        if any(not r[p+'_accept'] for p in POLICIES):print(r['episode'],r['signal_time'],r['net_pct'],[r[p+'_accept'] for p in POLICIES])
    print('Saved',out)
if __name__=='__main__':main()
