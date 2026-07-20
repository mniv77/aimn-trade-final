#!/usr/bin/env python3
"""
=========================================================
AATA Session Builder
=========================================================

Session: 0001

Purpose:
    Save the first official AATA research session
    into the Academy database.

Author:
    Meir Niv / ChatGPT

=========================================================
"""

from builder_config import *
import mysql.connector

print("=" * 60)
print(f"{ACADEMY_NAME} Session Builder")
print("Session #0001")
print("=" * 60)

print()
print("Configuration Loaded Successfully")
print(f"Academy : {ACADEMY_NAME}")
print(f"Database: {DB_NAME}")
print(f"Builder : {CREATED_BY}")
print()

try:
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    print("✅ Connected to MySQL successfully.")

    conn.close()

except Exception as e:
    print("❌ Database connection failed.")
    print(e)