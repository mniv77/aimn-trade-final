# ==============================
# File: tests/_env.py
# ==============================
from __future__ import annotations
import os, socket

def _contains(s: str, needle: str) -> bool:
    try:
        return needle in (s or "")
    except Exception:
        return False

HOST = os.environ.get("HOSTNAME", "") + socket.getfqdn() + os.getcwd()
IS_PYTHONANYWHERE: bool = _contains(HOST.lower(), "pythonanywhere")