#!/usr/bin/env python3
"""EXP127 — read-only Alpaca 5-minute holdout data collector.

Fetch NVDA/AAPL Sep-Oct 2026, US/Eastern regular session only.
No orders. Does not modify existing candle files or trading code.
Requires Alpaca historical data entitlement for requested feed.
"""
import argparse,datetime as dt,json,os,time,urllib.parse,urllib.request
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"kiss/visual_research/independent_holdout_exp127"
NY=ZoneInfo("America/New_York")
UTC=dt.timezone.utc
START="2026-09-01T00:00:00Z"
END="2026-11-01T00:00:00Z"
SYMBOLS=("NVDA","AAPL")

def credentials():
    # Existing AIMn clients use both APCA_* and ALPACA_KEY/ALPACA_SECRET.
    # PythonAnywhere console sessions may not inherit web-app variables.
    # Read a local .env file if python-dotenv is installed; otherwise parse
    # only simple KEY=VALUE lines without executing any shell or Python code.
    candidates=(ROOT/".env", ROOT/".env.local")
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv=None
    if load_dotenv is not None:
        for path in candidates:
            if path.is_file():
                load_dotenv(dotenv_path=path,override=False)
    else:
        recognized={"APCA_API_KEY_ID","APCA_API_SECRET_KEY",
                    "ALPACA_API_KEY","ALPACA_API_KEY_ID","ALPACA_KEY",
                    "ALPACA_SECRET","ALPACA_SECRET_KEY","ALPACA_API_SECRET_KEY"}
        for path in candidates:
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                line=line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name,value=line.split("=",1)
                name=name.removeprefix("export ").strip()
                if name in recognized and name not in os.environ:
                    os.environ[name]=value.strip().strip('"').strip("'")
    key_names=("APCA_API_KEY_ID","ALPACA_API_KEY","ALPACA_API_KEY_ID","ALPACA_KEY")
    secret_names=("APCA_API_SECRET_KEY","ALPACA_SECRET_KEY","ALPACA_API_SECRET_KEY","ALPACA_SECRET")
    key=next((v for name in key_names if (v:=os.environ.get(name)) and
              not v.upper().startswith(("YOUR_","PK_DEFAULT"))),None)
    secret=next((v for name in secret_names if (v:=os.environ.get(name)) and
                 not v.upper().startswith(("YOUR_","SK_DEFAULT"))),None)
    if not key or not secret:
        found=[p.name for p in candidates if p.is_file()]
        raise RuntimeError(
            "Alpaca credentials unavailable to this PythonAnywhere console. "
            "Checked environment variables ALPACA_KEY/ALPACA_SECRET, APCA_* "
            "and local .env/.env.local. Local env files present: "+
            (", ".join(found) if found else "none")+
            ". Existing AIMn web-app credentials may be stored separately. "
            "Do not paste secrets into chat or commit them to Git.")
    return key,secret

def fetch(symbol,feed,key,secret):
    collected=[];page=None;seen=set()
    for _ in range(100):
        q={"symbols":symbol,"timeframe":"5Min","start":START,"end":END,
           "limit":10000,"adjustment":"raw","feed":feed,"sort":"asc"}
        if page:q["page_token"]=page
        url="https://data.alpaca.markets/v2/stocks/bars?"+urllib.parse.urlencode(q)
        req=urllib.request.Request(url,headers={
            "APCA-API-KEY-ID":key,"APCA-API-SECRET-KEY":secret,
            "Accept":"application/json","User-Agent":"AIMn-EXP127-readonly"})
        try:
            with urllib.request.urlopen(req,timeout=40) as response:
                payload=json.load(response)
        except Exception as exc:
            raise RuntimeError(f"Alpaca historical data request failed for {symbol} (feed={feed}): {exc}. Check data permissions, credentials and feed.") from exc
        batch=payload.get("bars",{}).get(symbol,[])
        if not isinstance(batch,list):raise RuntimeError("Unexpected Alpaca bars format")
        collected.extend(batch)
        next_page=payload.get("next_page_token")
        if not next_page:break
        if next_page in seen:raise RuntimeError("Repeated Alpaca page token")
        seen.add(next_page);page=next_page
        time.sleep(0.15)
    else:raise RuntimeError("Too many pagination pages")
    return collected

def convert(raw):
    out=[];duplicates=0;outside=0
    for bar in raw:
        stamp=str(bar["t"]).replace("Z","+00:00")
        moment=dt.datetime.fromisoformat(stamp).astimezone(NY)
        # 5-minute candle open timestamps; regular session 09:30..15:55.
        if moment.weekday()>=5 or not(dt.time(9,30)<=moment.time()<dt.time(16,0)):
            outside+=1;continue
        row={"timestamp":moment.strftime("%Y-%m-%d %H:%M:%S"),
             "open":float(bar["o"]),"high":float(bar["h"]),
             "low":float(bar["l"]),"close":float(bar["c"]),
             "volume":float(bar.get("v",0))}
        if min(row[k] for k in ("open","high","low","close"))<=0:
            raise ValueError("Nonpositive price in Alpaca data")
        if row["high"]<max(row[k] for k in ("open","low","close")) or row["low"]>min(row[k] for k in ("open","high","close")):
            raise ValueError("Invalid OHLC")
        out.append(row)
    out.sort(key=lambda x:x["timestamp"])
    times=[r["timestamp"] for r in out]
    if len(set(times))!=len(times):raise ValueError("Duplicate candle timestamps")
    return out,outside

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feed",choices=("iex","sip"),default="iex",
                   help="IEX may differ materially from consolidated SIP prices; SIP requires entitlement")
    args=p.parse_args()
    key,secret=credentials()
    # Reject accidental overwrite of existing holdout files.
    OUT.mkdir(parents=True,exist_ok=True)
    planned={sym:OUT/(sym.lower()+"_sep_oct_2026_5m_"+args.feed+".json") for sym in SYMBOLS}
    for f in planned.values():
        if f.exists():raise FileExistsError(f"Refusing to overwrite existing holdout: {f}")
    metadata={"experiment":"EXP127","feed":args.feed,"adjustment":"raw",
              "start_utc":START,"end_utc_exclusive":END,
              "timezone":"America/New_York","session":"09:30 through 15:55 NY time",
              "note":"IEX and SIP feeds can differ. Original research feed must be verified before treating results as comparable.",
              "symbols":{}}
    for sym in SYMBOLS:
        bars=fetch(sym,args.feed,key,secret)
        rows,outside=convert(bars)
        if not rows:raise RuntimeError(f"No regular-session candles for {sym}")
        path=planned[sym]
        # Exclusive file creation; no production or old research data touched.
        with path.open("x",encoding="utf-8") as f:json.dump(rows,f,indent=2)
        days=Counter(r["timestamp"][:10] for r in rows)
        metadata["symbols"][sym]={"path":str(path),"candles":len(rows),
                                  "days":len(days),"first":rows[0]["timestamp"],
                                  "last":rows[-1]["timestamp"],
                                  "min_candles_per_day":min(days.values()),
                                  "max_candles_per_day":max(days.values()),
                                  "outside_regular_session_removed":outside}
        print(sym,"saved:",path,"candles:",len(rows),"days:",len(days),
              "first:",rows[0]["timestamp"],"last:",rows[-1]["timestamp"])
    (OUT/("manifest_"+args.feed+".json")).write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    print("DATA ONLY — no orders, no production changes.")
    print("Next: python3 aimn_exp126_independent_validation.py --nvda "+
          str(planned["NVDA"])+" --aapl "+str(planned["AAPL"]))

if __name__=="__main__":main()
