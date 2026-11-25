# aimn_exp151_step14_alpaca_iex_collector.py
#!/usr/bin/env python3
"""EXP151 Step 14: Alpaca IEX 5-minute research snapshot collector.

GET requests only. No trading endpoints, no orders, no strategy changes.
Requires APCA_API_KEY_ID and APCA_API_SECRET_KEY environment variables.
Outputs independent, timestamped JSON snapshots compatible with Steps 12/13.
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone, time as clock_time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API = "https://data.alpaca.markets/v2/stocks/bars"
NY = ZoneInfo("America/New_York")
SYMBOLS = ("NVDA", "AAPL")
FORWARD_START = "2026-11-16"


def request_json(url, headers):
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers=headers, method="GET"), timeout=35) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Alpaca HTTP {exc.code}; check credentials, feed and limits") from None
        except (URLError, TimeoutError) as exc:
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Alpaca connection failed: {type(exc).__name__}") from None
    raise RuntimeError("Request retry limit exceeded")


def utc_iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def fetch_symbol(symbol, start_utc, end_utc, headers):
    token = None
    seen_tokens = set()
    result = []
    while True:
        params = {
            "symbols": symbol,
            "timeframe": "5Min",
            "start": utc_iso(start_utc),
            "end": utc_iso(end_utc),
            "limit": "10000",
            "adjustment": "raw",
            "feed": "iex",
            "sort": "asc",
        }
        if token:
            params["page_token"] = token
        payload = request_json(API + "?" + urlencode(params), headers)
        result.extend(payload.get("bars", {}).get(symbol, []))
        next_token = payload.get("next_page_token")
        if not next_token:
            return result
        if next_token in seen_tokens:
            raise RuntimeError("Alpaca returned a repeated pagination token")
        seen_tokens.add(next_token)
        token = next_token


def convert(raw, symbol, cutoff):
    result = []
    seen = set()
    for item in raw:
        raw_time = str(item["t"])
        utc_dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        if utc_dt.tzinfo is None:
            raise ValueError("Alpaca timestamp missing timezone")
        utc_dt = utc_dt.astimezone(timezone.utc)
        if utc_dt + timedelta(minutes=5) > cutoff:
            continue  # Do not include a bar that may still be forming.
        local = utc_dt.astimezone(NY)
        if local.weekday() >= 5 or not (clock_time(9, 30) <= local.time() < clock_time(16, 0)):
            continue
        if local.minute % 5 or local.second or local.microsecond:
            raise ValueError(f"Non-5-minute bar label for {symbol}: {raw_time}")
        label = local.replace(tzinfo=None).isoformat(timespec="seconds")
        if label in seen:
            raise ValueError(f"Duplicate exchange-local timestamp: {label}")
        seen.add(label)
        o, h, l, c = (float(item[k]) for k in ("o", "h", "l", "c"))
        v = float(item["v"])
        if not all(math.isfinite(x) for x in (o, h, l, c, v)):
            raise ValueError(f"Nonfinite OHLCV at {label}")
        if not (0 < l <= min(o, c) <= max(o, c) <= h and v >= 0):
            raise ValueError(f"Invalid OHLCV at {label}")
        result.append({"timestamp": label, "open": o, "high": h,
                       "low": l, "close": c, "volume": v})
    result.sort(key=lambda x: x["timestamp"])
    return result


def main():
    parser = argparse.ArgumentParser(description="EXP151 read-only Alpaca IEX 5-minute snapshot")
    parser.add_argument("--days", type=int, default=90,
                        help="Calendar days to retrieve, including warmup (default: 90)")
    parser.add_argument("--output-dir", default="kiss/visual_research/exp151_forward_intake",
                        help="Research-only snapshot directory")
    args = parser.parse_args()
    if not 35 <= args.days <= 365:
        parser.error("--days must be between 35 and 365")
    print("EXP151 STEP 14 - ALPACA IEX DATA COLLECTION")
    print("READ-ONLY API GET | NO ORDERS | NO PRODUCTION CHANGES")
    print("FORWARD VALIDATION START:", FORWARD_START)
    print("FEED: IEX | ADJUSTMENT: RAW | TIMEFRAME: 5Min")
    print("TIMESTAMPS: America/New_York, naive, BAR START")
    key = os.environ.get("APCA_API_KEY_ID", "").strip()
    secret = os.environ.get("APCA_API_SECRET_KEY", "").strip()
    if not key or not secret:
        print("STATUS: CREDENTIALS MISSING")
        print("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY securely in your environment.")
        print("Do not paste API secrets into chat or Python files.")
        return 2
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
               "Accept": "application/json"}
    # Freeze the upper bound once. Leave a five-minute safety margin.
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    start = cutoff - timedelta(days=args.days)
    print("REQUEST WINDOW UTC:", utc_iso(start), "to", utc_iso(cutoff))
    snapshots = {}
    for symbol in SYMBOLS:
        raw = fetch_symbol(symbol, start, cutoff, headers)
        rows = convert(raw, symbol, cutoff)
        if not rows:
            raise RuntimeError(f"No eligible regular-session candles for {symbol}")
        snapshots[symbol] = rows
        forward = sum(x["timestamp"][:10] >= FORWARD_START for x in rows)
        print(f"{symbol}: {len(rows)} bars; forward-labeled bars: {forward}; "
              f"first={rows[0]['timestamp']}; last={rows[-1]['timestamp']}")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for symbol, rows in snapshots.items():
        destination = output_dir / f"exp151_{symbol.lower()}_iex_5m_{stamp}.json"
        data = (json.dumps(rows, indent=2, allow_nan=False) + "\n").encode("utf-8")
        # Exclusive creation: never replace an existing snapshot.
        with destination.open("xb") as handle:
            handle.write(data)
        print("SAVED:", destination)
        print("SHA256:", hashlib.sha256(data).hexdigest())
        print(f"STEP 13: python3 aimn_exp151_step13_forward_data_audit.py --{symbol.lower()} {destination}")
        print(f"STEP 12: python3 aimn_exp151_step12_forward_evaluator.py --{symbol.lower()} {destination}")
    print("STATUS: SNAPSHOTS SAVED; DATA QUALITY NOT YET CERTIFIED")
    print("NOTE: IEX may omit intervals with no trades; Step 13 will flag missing bars.")
    print("NOTE: Step 13 currently uses a limited half-day calendar; verify exchange holidays separately.")
    print("ORDERS PLACED: NONE | PRODUCTION FILES MODIFIED: NONE")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("STEP 14 FAILED:", str(exc), file=sys.stderr)
        sys.exit(1)
