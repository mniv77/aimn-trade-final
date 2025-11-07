# =========================================
# path: blueprints/credentials_api.py
# =========================================
from __future__ import annotations
from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from config.db import get_db, SessionLocal, Base, engine
from models import BrokerCredential, TickSize

credentials_api = Blueprint("credentials_api", __name__)

def _ok(d, code=200): return jsonify({"ok": True, **d}), code
def _err(m, code=400): return jsonify({"ok": False, "error": m}), code

def _user_id() -> int:
    # why: pluggable. Replace with real auth later.
    return 1

@credentials_api.route("/api/credentials", methods=["GET"])
def list_credentials():
    with SessionLocal() as db:
        uid = _user_id()
        rows = db.query(BrokerCredential).filter(BrokerCredential.user_id==uid).all()
        data = []
        for r in rows:
            data.append({
                "id": r.id, "broker": r.broker, "label": r.label,
                "is_active": r.is_active, "updated_at": r.updated_at.isoformat()
            })
        return _ok({"items": data})

@credentials_api.route("/api/credentials", methods=["POST"])
def upsert_credentials():
    j = request.get_json(silent=True) or {}
    broker = (j.get("broker") or "alpaca").lower()
    label = j.get("label") or "default"
    key_id = j.get("key_id") or ""
    secret_key = j.get("secret_key") or ""
    base_url = j.get("base_url") or ""
    if broker != "alpaca":
        return _err("only alpaca supported for now")
    if not key_id or not secret_key:
        return _err("key_id and secret_key required")

    uid = _user_id()
    with SessionLocal() as db:
        row = db.query(BrokerCredential).filter(
            BrokerCredential.user_id==uid,
            BrokerCredential.broker=="alpaca",
            BrokerCredential.label==label
        ).first()
        if not row:
            row = BrokerCredential(user_id=uid, broker="alpaca", label=label, is_active=True)
            db.add(row)
        row.set_secrets(key_id, secret_key, base_url or None)
        row.is_active = True
        db.commit()
        return _ok({"id": row.id, "label": row.label})

@credentials_api.route("/api/credentials/<int:cid>", methods=["DELETE"])
def delete_credentials(cid: int):
    with SessionLocal() as db:
        uid = _user_id()
        row = db.query(BrokerCredential).filter(
            BrokerCredential.id==cid, BrokerCredential.user_id==uid
        ).first()
        if not row: return _err("not found", 404)
        db.delete(row); db.commit()
        return _ok({"deleted": cid})

# ------- tick sizes (server-managed override) -------
@credentials_api.route("/api/meta/tick_size", methods=["GET","POST","DELETE"])
def tick_size_handler():
    uid = _user_id()
    if request.method == "GET":
        ex = (request.args.get("exchange") or "").upper()
        sym = (request.args.get("symbol") or "").upper()
        with SessionLocal() as db:
            row = db.query(TickSize).filter(TickSize.user_id==uid, TickSize.exchange==ex, TickSize.symbol==sym).first()
            if not row: return _ok({"tick_size": None})
            return _ok({"tick_size": row.tick_size, "updated_at": row.updated_at.isoformat()})
    elif request.method == "POST":
        j = request.get_json(silent=True) or {}
        ex = (j.get("exchange") or "").upper()
        sym = (j.get("symbol") or "").upper()
        ts = float(j.get("tick_size") or 0)
        if not ex or not sym or ts <= 0: return _err("exchange, symbol, tick_size required")
        with SessionLocal() as db:
            row = db.query(TickSize).filter(TickSize.user_id==uid, TickSize.exchange==ex, TickSize.symbol==sym).first()
            if not row:
                row = TickSize(user_id=uid, exchange=ex, symbol=sym, tick_size=ts)
                db.add(row)
            else:
                row.tick_size = ts
            db.commit()
            return _ok({"exchange": ex, "symbol": sym, "tick_size": ts})
    else:
        ex = (request.args.get("exchange") or "").upper()
        sym = (request.args.get("symbol") or "").upper()
        with SessionLocal() as db:
            row = db.query(TickSize).filter(TickSize.user_id==uid, TickSize.exchange==ex, TickSize.symbol==sym).first()
            if not row: return _ok({"deleted": False})
            db.delete(row); db.commit()
            return _ok({"deleted": True})
