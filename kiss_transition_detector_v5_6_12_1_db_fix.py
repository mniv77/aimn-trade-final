#!/usr/bin/env python3
"""
V5.6.12.1 — DB connection fix only.

This wrapper does NOT change V5.6.12 research logic.
It fixes only the db.py contract: get_db_connection() returns
(conn, cursor), while V5.6.12 expected only conn.
"""

import mysql.connector

import kiss_transition_detector_v5_6_12_trend_health_persistence as v5612
from db import get_db_connection


def fixed_load_rows(symbol, timeframe):
    conn, _ = get_db_connection()
    cur = None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT timestamp, open, high, low, close, volume "
            "FROM candles WHERE symbol=%s AND timeframe=%s ORDER BY timestamp ASC",
            (symbol, timeframe),
        )
        return list(cur.fetchall())
    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:
            pass
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


# Patch ONLY the broken DB loader. All V5.6.12 analysis remains unchanged.
v5612.load_rows = fixed_load_rows

if __name__ == "__main__":
    v5612.main()
