"""Research-only blind AI scoring runner for KISS transition cases."""
from __future__ import annotations
import argparse,json,os,time
from collections import Counter
from pathlib import Path
from typing import Any,Dict,List
from openai import OpenAI
from kiss_ai_transition_research import SYMBOLS,_db_rows,build_states,transition_events,make_case,TREND_WINDOW,FUTURE_BARS

RESULTS_FILE=Path("kiss_ai_blind_results.jsonl")
DEFAULT_MODEL=os.environ.get("OPENAI_MODEL","gpt-5.6-luna")
SYSTEM_INSTRUCTIONS="""You are the transition-recognition component of an autonomous trading research system. Classify ONE market trend transition using ONLY information available at that transition.
REAL: evidence supports a meaningful move in the new direction.
WEAK: plausible but evidence is mixed or insufficient.
FALSE: evidence suggests the transition is likely to fail or reverse.
Do not use future information. Do not invent missing data. Consider transition type, price location, RSI, MA relationship, prior state duration, churn, recent price movement, and V-shape only when supplied. Confidence is 0-100 for the CLASS. Give a short evidence-based reason."""
SCHEMA={"type":"object","properties":{"prediction":{"type":"string","enum":["REAL","WEAK","FALSE"]},"confidence":{"type":"integer","minimum":0,"maximum":100},"reason":{"type":"string"}},"required":["prediction","confidence","reason"],"additionalProperties":False}

def load_cases()->List[Dict[str,Any]]:
    cases=[]
    for symbol in SYMBOLS:
        trend=_db_rows(symbol,"30m"); execution=_db_rows(symbol,"5m")
        if len(trend)<TREND_WINDOW+2 or len(execution)<FUTURE_BARS: continue
        states=build_states(trend)
        for event in transition_events(trend,states):
            case=make_case(symbol,event,execution)
            if case: cases.append(case)
    return cases

def case_id(c): return f"{c['symbol']}|{c['direction']}|{c['transition_time']}"

def load_done():
    done={}
    if not RESULTS_FILE.exists(): return done
    with RESULTS_FILE.open(encoding="utf-8") as f:
        for line in f:
            try:
                r=json.loads(line); done[r["case_id"]]=r
            except Exception: pass
    return done

def model_input(c):
    return json.dumps({"symbol":c["symbol"],"timeframe":c["timeframe"],"execution_timeframe":c["execution_timeframe"],"transition_time":c["transition_time"],"direction":c["direction"],"features_available_at_transition":c["features_available_at_transition"]},sort_keys=True,separators=(",",":"))

def call_ai(client,model,c):
    response=client.responses.create(model=model,instructions=SYSTEM_INSTRUCTIONS,input=model_input(c),text={"format":{"type":"json_schema","name":"transition_classification","strict":True,"schema":SCHEMA},"verbosity":"low"},reasoning={"effort":"low"},store=False)
    r=json.loads(response.output_text)
    if r["prediction"] not in {"REAL","WEAK","FALSE"}: raise ValueError("invalid prediction")
    r["confidence"]=int(r["confidence"])
    if not 0<=r["confidence"]<=100: raise ValueError("invalid confidence")
    return r

def score(rows):
    if not rows: return
    correct=sum(r["prediction"]==r["actual"] for r in rows)
    print("\n"+"="*80); print("BLIND AI SCORING RESULTS"); print(f"Scored: {len(rows)}"); print(f"Accuracy: {correct/len(rows)*100:.2f}%")
    m=Counter((r["actual"],r["prediction"]) for r in rows)
    print("\nCONFUSION MATRIX (actual -> predicted)")
    for a in ("REAL","WEAK","FALSE"): print(f"{a:5s}: REAL={m[(a,'REAL')]:3d} WEAK={m[(a,'WEAK')]:3d} FALSE={m[(a,'FALSE')]:3d}")
    print("\nPER CLASS")
    for cls in ("REAL","WEAK","FALSE"):
        tp=m[(cls,cls)]; pred=sum(m[(a,cls)] for a in ("REAL","WEAK","FALSE")); act=sum(m[(cls,p)] for p in ("REAL","WEAK","FALSE"))
        print(f"{cls:5s}: precision={tp/pred*100 if pred else 0:6.2f}% recall={tp/act*100 if act else 0:6.2f}%")
    print("\nACCURACY BY TRANSITION")
    groups={}
    for r in rows: groups.setdefault(f"{r['transition_from']}->{r['transition_to']}",[]).append(r)
    for name,g in sorted(groups.items()): print(f"{name:15s} N={len(g):3d} accuracy={sum(x['prediction']==x['actual'] for x in g)/len(g)*100:6.2f}%")
    print("\nHIGH-CONFIDENCE MISTAKES (>=80)")
    bad=[r for r in rows if r["prediction"]!=r["actual"] and r["confidence"]>=80]
    if not bad: print("None")
    for r in bad[:20]: print(f"{r['case_id']} AI={r['prediction']} conf={r['confidence']} actual={r['actual']} reason={r['reason']}")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--limit",type=int,default=0); p.add_argument("--model",default=DEFAULT_MODEL); p.add_argument("--fresh",action="store_true"); p.add_argument("--delay",type=float,default=0.0); a=p.parse_args()
    if not os.environ.get("OPENAI_API_KEY"): raise SystemExit("OPENAI_API_KEY is not set. Export it in your shell first.")
    cases=load_cases(); done={} if a.fresh else load_done(); pending=[c for c in cases if case_id(c) not in done]
    if a.limit>0: pending=pending[:a.limit]
    print("AI VISION BLIND SCORING RUNNER"); print(f"Model: {a.model}"); print(f"Total cases available: {len(cases)}"); print(f"Already scored locally: {len(done)}"); print(f"New cases this run: {len(pending)}"); print("FUTURE OUTCOME IS NOT SENT TO THE MODEL.")
    client=OpenAI(api_key=os.environ["OPENAI_API_KEY"]); mode="w" if a.fresh else "a"
    with RESULTS_FILE.open(mode,encoding="utf-8") as out:
        for n,c in enumerate(pending,1):
            cid=case_id(c)
            try:
                ai=call_ai(client,a.model,c); actual=c["future_outcome"]["label"]
                row={"case_id":cid,"symbol":c["symbol"],"transition_time":c["transition_time"],"direction":c["direction"],"transition_from":c["features_available_at_transition"]["from"],"transition_to":c["features_available_at_transition"]["to"],"prediction":ai["prediction"],"confidence":ai["confidence"],"reason":ai["reason"],"actual":actual,"mfe_pct":c["future_outcome"]["mfe_pct"],"mae_pct":c["future_outcome"]["mae_pct"]}
                out.write(json.dumps(row,sort_keys=True)+"\n"); out.flush(); done[cid]=row
                print(f"[{n}/{len(pending)}] {cid} AI={ai['prediction']} conf={ai['confidence']} actual={actual}")
            except Exception as e: print(f"[{n}/{len(pending)}] {cid} ERROR: {type(e).__name__}: {e}")
            if a.delay>0 and n<len(pending): time.sleep(a.delay)
    score(list(done.values()))

if __name__=="__main__": main()
