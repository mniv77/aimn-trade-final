"""EXP27: causal directional-change identity, fixed candidate audit only."""
import csv,json
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parent
POLICIES=('baseline','mem60','mti1','mti2','mti3')
def read(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def identities(bars,ts,threshold):
    # Close-only directional change; no intrabar ordering assumptions.
    result=[]; day=None; direction='SEEK'; serial=0; high=low=0.; peak=0.; peak_i=0
    for i,(b,t) in enumerate(zip(bars,ts)):
        c=float(b['close'])
        if t.date()!=day:
            day=t.date();direction='SEEK';serial=0;high=low=c;peak=c;peak_i=i
        high=max(high,c);low=min(low,c)
        if direction=='SEEK':
            if c/low-1>=threshold:direction='LONG';serial+=1;high=c;peak=c;peak_i=i
            elif 1-c/high>=threshold:direction='SHORT';serial+=1;low=c
        elif direction=='LONG':
            if c>=peak:peak=c;peak_i=i
            if 1-c/high>=threshold:direction='SHORT';serial+=1;low=c
        elif c/low-1>=threshold:
            direction='LONG';serial+=1;high=c;peak=c;peak_i=i
        result.append((f'{day}:{serial}',direction,peak,peak_i))
    return result

def main():
    path=ROOT/'aimn_nvda_candles.json'
    bars=sorted(json.loads(path.read_text(encoding='utf-8-sig')),key=lambda b:b['timestamp'])
    ts=[datetime.fromisoformat(b['timestamp']) for b in bars];idx={t.strftime('%Y-%m-%d %H:%M'):i for i,t in enumerate(ts)}
    audit=read('aimn_exp19_trend_position_audit.csv')
    if len(idx)!=len(bars) or len(audit)!=len(bars) or any(a['timestamp_ny']!=t.strftime('%Y-%m-%d %H:%M') or abs(float(a['close'])-float(b['close']))>1e-8 for a,t,b in zip(audit,ts,bars)):raise ValueError('Candle audit mismatch')
    source=read('aimn_exp26_intelligent_rearming_audit.csv'); prior={r['episode']:r for r in read('aimn_exp23_failed_continuation_quality_audit.csv')}
    states=identities(bars,ts,.005); history={p:[] for p in POLICIES};rows=[]
    for r in sorted(source,key=lambda r:r['signal_time']):
        s,e,x=(idx[r[k]] for k in ('signal_time','entry_time','exit_time'));net=float(r['net_pct']);a=prior[r['episode']]
        if not s+1==e<=x or abs(float(bars[e]['open'])-float(r['entry_price']))>1e-8 or a['quality_profit_exit_time']!=r['exit_time'] or abs(float(a['quality_profit_net_pct'])-net)>1e-8:raise ValueError('Episode mismatch')
        identity,direction,peak,k=states[s]; close=float(bars[s]['close']); context=s>=6 and ts[s].date()==ts[s-6].date() and close<float(bars[s-6]['close']); breakdown=s>=3 and close<min(float(bars[j]['low']) for j in range(s-3,s));row=dict(r,trajectory_id=identity,trajectory_direction=direction,trajectory_peak=peak,trajectory_peak_time=ts[k].isoformat(),context_down=int(context),breakdown=int(breakdown))
        for p in POLICIES:
            losses=[(j,n,i) for j,n,i in history[p] if j<s and ts[j].date()==ts[s].date() and n<=0];last=losses[-1] if losses else None
            age=(ts[s]-ts[last[0]]).total_seconds()/60 if last else None
            # New SHORT identity must be confirmed after the failed exit; peak must also form after exit for MTI2/3.
            new=bool(last and direction=='SHORT' and identity!=states[last[0]][0] and identity!=states[last[2]][0]); fresh=bool(new and k>last[0] and breakdown)
            accept=not last or {'baseline':True,'mem60':age is not None and age>60,'mti1':new,'mti2':fresh,'mti3':fresh and context}[p]
            row[p+'_accept']=int(accept);row[p+'_net_pct']=net if accept else 0.;row[p+'_last_loss_age']=age;row[p+'_new_identity']=int(new);row[p+'_fresh_peak']=int(fresh)
            if accept:history[p].append((x,net,s))
        if row['mem60_accept']!=int(r['mem60_accept']):raise ValueError('Memory mismatch')
        rows.append(row)
    out=ROOT/'aimn_exp27_trajectory_identity_audit.csv'
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for label,g in [('ALL',rows)]+[(k,[r for r in rows if r['split']==k]) for k in sorted({r['split'] for r in rows})]:
        print(label)
        for p in POLICIES:
            a=[r for r in g if r[p+'_accept']];print(p,len(a),sum(float(r['net_pct'])>0 for r in a),sum(float(r['net_pct'])<0 for r in a),round(sum(r[p+'_net_pct'] for r in g),4))
    for r in rows:
        if any(not r[p+'_accept'] for p in POLICIES):print(r['episode'],r['signal_time'],r['trajectory_id'],r['trajectory_direction'],[r[p+'_accept'] for p in POLICIES])
    print('Saved',out)
if __name__=='__main__':main()
