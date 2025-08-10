# /run_worker.py  (FULL, drop-in)
"""
Worker entrypoint for PythonAnywhere Always-on Task.

Env vars:
- AIMN_POLL_SEC   : loop sleep seconds (default 60)
- AIMN_TIMEFRAME  : default timeframe string (default "1m")
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime

from app.db import init_db
from app.worker import run_forever

def main() -> int:
    # ensure DB tables exist
    init_db()

    poll_sec = int(os.getenv("AIMN_POLL_SEC", "60"))
    timeframe = os.getenv("AIMN_TIMEFRAME", "1m")

    print(f"[{datetime.utcnow().isoformat()}Z] AIMn worker starting… poll={poll_sec}s tf={timeframe}", flush=True)
    try:
        run_forever(poll_sec=poll_sec, timeframe=timeframe)
    except KeyboardInterrupt:
        print(f"[{datetime.utcnow().isoformat()}Z] AIMn worker stopped (KeyboardInterrupt).", flush=True)
    except Exception as exc:
        # why: surface unexpected crash to PA logs
        print(f"[{datetime.utcnow().isoformat()}Z] FATAL: {exc}", file=sys.stderr, flush=True)
        raise
    return 0

if __name__ == "__main__":
    raise SystemExit(main())