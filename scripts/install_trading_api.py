# scripts/install_trading_api.py
# WHY: one-shot installer; safe, idempotent; supports both single-file app and app-factory patterns.

from __future__ import annotations
import re
from pathlib import Path

ROOT = Path.cwd()
APP = ROOT / "app.py"
BROKERS = ROOT / "brokers"
ALPACA = BROKERS / "alpaca_client.py"
BROKERS_INIT = BROKERS / "__init__.py"

BLUEPRINT_BLOCK = """
# >>> trading_api START
from flask import Blueprint, request, jsonify
from brokers.alpaca_client import AlpacaBroker, BaseBroker

trading_api = Blueprint("trading_api", __name__)
BROKER: BaseBroker = AlpacaBroker.from_env_or_dummy()

def _ok(data, code=200):  # why: unify success payloads
    return jsonify({"ok": True, **data}), code
def _err(msg, code=400):  # why: unify error payloads
    return jsonify({"ok": False, "error": msg}), code

@trading_api.route("/api/trade/open", methods=["POST"])
def api_trade_open():
    j = request.get_json(silent=True) or {}
    symbol = j.get("symbol")
    side = (j.get("side") or "BUY").upper()
    qty = float(j.get("qty") or 1)
    if not symbol or side not in {"BUY","SELL"}:
        return _err("symbol and side required")
    res = BROKER.open_market(symbol=symbol, side=side, qty=qty)
    if getattr(res, "ok", False):
        return _ok({"order_id": getattr(res, "order_id", ""),
                    "symbol": symbol, "side": side, "qty": qty,
                    "broker_mode": BROKER.__class__.__name__})
    return _err(getattr(res, "error", "order failed"), 502)

@trading_api.route("/api/trade/close", methods=["POST"])
def api_trade_close():
    j = request.get_json(silent=True) or {}
    symbol = j.get("symbol")
    side = (j.get("side") or "BUY").upper()
    qty = float(j.get("qty") or 1)
    if not symbol or side not in {"BUY","SELL"}:
        return _err("symbol and side required")
    res = BROKER.close_market(symbol=symbol, side=side, qty=qty)
    if getattr(res, "ok", False):
        return _ok({"order_id": getattr(res, "order_id", ""),
                    "symbol": symbol, "side": getattr(res, "side", side), "qty": qty,
                    "broker_mode": BROKER.__class__.__name__})
    return _err(getattr(res, "error", "close failed"), 502)

@trading_api.route("/api/trade/panic", methods=["POST"])
def api_trade_panic():
    # why: panic = immediate reverse market order
    return api_trade_close()
# >>> trading_api END
""".lstrip()

ALPACA_CLIENT = """
# brokers/alpaca_client.py
from __future__ import annotations
import os, uuid
from dataclasses import dataclass
from typing import Optional, Dict, Any

try:
    import alpaca_trade_api as tradeapi
except Exception:
    tradeapi = None  # optional fallback

from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

@dataclass
class OrderResult:
    ok: bool
    order_id: str
    side: str
    symbol: str
    qty: float
    raw: Dict[str, Any] | None = None
    error: str | None = None

class BaseBroker:
    def open_market(self, symbol: str, side: str, qty: float) -> OrderResult: ...
    def close_market(self, symbol: str, side: str, qty: float) -> OrderResult: ...

class DryRunBroker(BaseBroker):
    # why: safe on servers without creds
    def open_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        return OrderResult(ok=True, order_id=f"dry-{uuid.uuid4().hex[:10]}", side=side, symbol=symbol, qty=qty, raw={"mode":"dryrun"})
    def close_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        return OrderResult(ok=True, order_id=f"dry-close-{uuid.uuid4().hex[:10]}", side=side, symbol=symbol, qty=qty, raw={"mode":"dryrun"})

class AlpacaBroker(BaseBroker):
    def __init__(self, api):
        self.api = api

    @classmethod
    def from_env_or_dummy(cls):
        key = os.getenv("APCA_API_KEY_ID")
        sec = os.getenv("APCA_API_SECRET_KEY")
        base = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")
        if tradeapi and key and sec:
            api = tradeapi.REST(key_id=key, secret_key=sec, base_url=base, api_version="v2")
            try:
                api.get_account()
                return cls(api)
            except Exception:
                pass
        return DryRunBroker()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(0.6), retry=retry_if_exception_type(Exception))
    def _submit(self, **kw):
        return self.api.submit_order(**kw)

    def open_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        try:
            o = self._submit(symbol=symbol, qty=str(qty), side=side.lower(), type="market", time_in_force="day")
            rid = getattr(o, "id", "") or getattr(getattr(o, "_raw", {}), "get", lambda *_: "")("id")
            return OrderResult(ok=True, order_id=rid, side=side, symbol=symbol, qty=qty, raw=getattr(o, "_raw", None))
        except Exception as e:
            return OrderResult(ok=False, order_id="", side=side, symbol=symbol, qty=qty, error=str(e))

    def close_market(self, symbol: str, side: str, qty: float) -> OrderResult:
        close_side = "sell" if side.upper()=="BUY" else "buy"
        try:
            o = self._submit(symbol=symbol, qty=str(qty), side=close_side, type="market", time_in_force="day")
            rid = getattr(o, "id", "") or getattr(getattr(o, "_raw", {}), "get", lambda *_: "")("id")
            return OrderResult(ok=True, order_id=rid, side=close_side, symbol=symbol, qty=qty, raw=getattr(o, "_raw", None))
        except Exception as e:
            return OrderResult(ok=False, order_id="", side=close_side, symbol=symbol, qty=qty, error=str(e))
""".lstrip()

def ensure_brokers():
    BROKERS.mkdir(exist_ok=True)
    if not BROKERS_INIT.exists():
        BROKERS_INIT.write_text("", encoding="utf-8")
        print("• created brokers/__init__.py")
    ALPACA.write_text(ALPACA_CLIENT, encoding="utf-8")
    print("• wrote brokers/alpaca_client.py")

def read_app() -> str:
    if not APP.exists():
        raise SystemExit("ERROR: app.py not found in current directory.")
    return APP.read_text(encoding="utf-8")

def write_app(text: str):
    APP.write_text(text, encoding="utf-8")
    print("• updated app.py")

def has_blueprint_block(src: str) -> bool:
    return "# >>> trading_api START" in src

def insert_blueprint_block(src: str) -> str:
    # Find last import block; insert after it. Why: keep routes near imports.
    lines = src.splitlines()
    last_import_idx = -1
    for i, ln in enumerate(lines[:300]):  # scan top
        if re.match(r"^\s*(from\s+\S+\s+import\s+|import\s+\S+)", ln):
            last_import_idx = i
    idx = last_import_idx + 1 if last_import_idx >= 0 else 0
    lines.insert(idx+1, "")
    lines.insert(idx+2, BLUEPRINT_BLOCK.rstrip())
    return "\n".join(lines) + ("\n" if not src.endswith("\n") else "")

def has_registration(src: str) -> bool:
    return re.search(r"\bapp\.register_blueprint\(\s*trading_api\s*\)", src) is not None

def register_after_app_assignment(src: str) -> tuple[str,bool]:
    # Place right after first "app = Flask(" if present.
    m = re.search(r"^(?P<indent>\s*)app\s*=\s*Flask\([^)]*\)\s*$", src, re.MULTILINE)
    if not m:
        return src, False
    insert_at = m.end()
    before = src[:insert_at]
    after = src[insert_at:]
    reg = f"\n{m.group('indent')}app.register_blueprint(trading_api)\n"
    if "app.register_blueprint(trading_api)" in src:
        return src, True
    return before + reg + after, True

def register_inside_factory(src: str) -> tuple[str,bool]:
    # Insert before "return app" inside create_app().
    pat = r"def\s+create_app\s*\(\s*\)\s*:\s*(?P<body>(?:.|\n)*?)\n(?=def\s|\Z)"
    m = re.search(pat, src)
    if not m:
        return src, False
    body = m.group("body")
    if "app.register_blueprint(trading_api)" in body:
        return src, True
    # Find return app
    rb = re.search(r"^\s*return\s+app\s*$", body, re.MULTILINE)
    if not rb:
        return src, False
    indent = re.search(r"^(\s*)return\s+app\s*$", body, re.MULTILINE).group(1)
    new_body = body[:rb.start()] + f"{indent}app.register_blueprint(trading_api)\n" + body[rb.start():]
    new_src = src.replace(body, new_body, 1)
    return new_src, True

def main():
    ensure_brokers()
    src = read_app()
    changed = False

    if not has_blueprint_block(src):
        src = insert_blueprint_block(src)
        print("• injected trading_api blueprint block")
        changed = True
    else:
        print("• trading_api blueprint block already present")

    if not has_registration(src):
        s2, ok = register_after_app_assignment(src)
        if ok:
            src = s2
            print("• registered blueprint after app = Flask(...)")
            changed = True
        else:
            s3, ok2 = register_inside_factory(src)
            if ok2:
                src = s3
                print("• registered blueprint inside create_app()")
                changed = True
            else:
                print("! WARNING: could not find app = Flask(...) or create_app(); please add:\n    app.register_blueprint(trading_api)")
    else:
        print("• blueprint registration already present")

    if changed:
        write_app(src)
    else:
        print("• no changes needed")

    print("\nDone.\nNext:")
    print("  - Set Alpaca paper creds (optional):")
    print("      export APCA_API_KEY_ID=...; export APCA_API_SECRET_KEY=...")
    print("  - Reload your web app on PythonAnywhere.")
    print("  - Verify: POST /api/trade/open returns ok=true (DryRunBroker if no creds).")

if __name__ == "__main__":
    main()
