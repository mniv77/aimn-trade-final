#!/usr/bin/env python3
"""EXP126 — frozen W12=0.10% independent validation gate.

Research only. Requires explicitly supplied, independently sourced 5-minute
OHLC JSON files. Rejects all overlap with original research candles.
Runs full EXP125 replay unchanged; no threshold selection.
Usage: python3 aimn_exp126_independent_validation.py --nvda PATH [--aapl PATH]
"""
import argparse,csv,hashlib,json
from pathlib import Path
import aimn_exp83_v16_structural_exit as base
import aimn_exp125_w12_strength_replay as exp125

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/results/exp126_independent_validation"
FROZEN_THRESHOLD=0.10

def load(path):
    rows=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows,list) or not rows:raise ValueError("Expected nonempty JSON array: "+str(path))
    required=("timestamp","open","high","low","close")
    for i,r in enumerate(rows):
        if not isinstance(r,dict) or any(k not in r for k in required):
            raise ValueError(f"{path}: row {i} missing OHLC/timestamp")
        o,h,l,c=(float(r[k]) for k in ("open","high","low","close"))
        if min(o,h,l,c)<=0 or h<max(o,c,l) or l>min(o,c,h):
            raise ValueError(f"{path}: invalid OHLC row {i}")
    rows.sort(key=lambda r:str(r["timestamp"]))
    ts=[str(r["timestamp"]) for r in rows]
    if len(set(ts))!=len(ts):raise ValueError("Duplicate timestamps: "+str(path))
    return rows

def audit(symbol,path):
    original=Path(base.DATA[symbol]).resolve()
    target=path.resolve()
    if original==target:raise ValueError("Refusing original training file")
    train=load(original);test=load(target)
    old={str(r["timestamp"]) for r in train}
    new={str(r["timestamp"]) for r in test}
    overlap=old&new
    if overlap:
        raise ValueError(f"{symbol}: {len(overlap)} overlapping timestamps; example {min(overlap)}")
    # Require validation period AFTER the entire original research period.
    # This is deliberately stricter than non-overlap to avoid historical
    # selection of favorable dates from the training era.
    if min(new)<=max(old):
        raise ValueError(f"{symbol}: holdout must begin after training end {max(old)}; got {min(new)}")
    if len(test)<100:
        raise ValueError(f"{symbol}: fewer than 100 candles; insufficient to run indicators reliably")
    # EXP125's unchanged replay includes all safety exits and original entry
    # logic; zero-threshold parity against EXP121 is asserted internally.
    outcome=exp125.run(symbol,target)
    frozen=outcome["thresholds"][str(FROZEN_THRESHOLD)]
    reference=outcome["thresholds"]["0.0"]
    return {
        "input_path":str(target),"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
        "train_last_timestamp":max(old),"holdout_first_timestamp":min(new),
        "holdout_last_timestamp":max(new),"holdout_candles":len(test),
        "baseline":outcome["baseline"],
        "exp121_reference":reference,
        "frozen_w12_0p10":frozen,
        "frozen_minus_exp121_pp":round(frozen["net_pct_sum"]-reference["net_pct_sum"],6),
        "holdout_entries":frozen["trades"],
        "evidence_warning":"One new period does not prove generalization; zero-trade holdout is inconclusive."
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nvda",type=Path,help="Independent NVDA 5-minute OHLC JSON")
    p.add_argument("--aapl",type=Path,help="Independent AAPL 5-minute OHLC JSON")
    args=p.parse_args()
    chosen={k:v for k,v in (("NVDA",args.nvda),("AAPL",args.aapl)) if v is not None}
    if not chosen:p.error("Provide --nvda PATH and/or --aapl PATH. No holdout is bundled.")
    for sym,path in chosen.items():
        if not path.is_file():p.error(f"{sym} file not found: {path}")
    OUT.mkdir(parents=True,exist_ok=True)
    # Preserve EXP125's output directory; run() writes its detailed trade
    # reports under this experiment's folder instead of overwriting EXP125.
    exp125.OUT=OUT
    report={"experiment":"EXP126","research_only":True,
            "frozen_w12_threshold_pct":FROZEN_THRESHOLD,
            "dataset_policy":"Explicit external 5-minute OHLC JSON, strict timestamp disjointness and chronologically later than training.",
            "limitations":["No threshold selection on validation results.",
                           "No slippage or borrow costs beyond baseline model.",
                           "The underlying original entry/exit engine remains unchanged.",
                           "Small holdout trade counts cannot establish reliability."],
            "symbols":{}}
    for sym,path in chosen.items():
        report["symbols"][sym]=audit(sym,path)
    (OUT/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("EXP126 — FROZEN 0.10% W12 INDEPENDENT VALIDATION — RESEARCH ONLY")
    for sym,r in report["symbols"].items():
        print(sym,"holdout candles:",r["holdout_candles"],
              "dates:",r["holdout_first_timestamp"],"to",r["holdout_last_timestamp"])
        print(" baseline net:",r["baseline"]["net_pct_sum"],
              "EXP121 net:",r["exp121_reference"]["net_pct_sum"],
              "frozen 0.10 net:",r["frozen_w12_0p10"]["net_pct_sum"],
              "trades:",r["holdout_entries"],
              "frozen minus EXP121 pp:",r["frozen_minus_exp121_pp"])
    print("Reports:",OUT)
    print("Production code unchanged.")

if __name__=="__main__":main()
