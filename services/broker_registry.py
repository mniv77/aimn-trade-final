# =========================================
# path: services/broker_registry.py
# =========================================
from __future__ import annotations
from sqlalchemy.orm import Session
from brokers.alpaca_client import BaseBroker, DryRunBroker, AlpacaBroker
from models import BrokerCredential

def per_user_broker(db: Session, user_id: int, prefer_label: str | None = None) -> BaseBroker:
    """why: one broker per user; choose active label or default."""
    q = db.query(BrokerCredential).filter(
        BrokerCredential.user_id==user_id,
        BrokerCredential.is_active==True,
        BrokerCredential.broker=="alpaca",
    )
    if prefer_label:
        q = q.filter(BrokerCredential.label==prefer_label)
    cred = q.order_by(BrokerCredential.updated_at.desc()).first()
    if not cred:
        return DryRunBroker()
    try:
        key, sec, base = cred.get_secrets()
        return AlpacaBroker(key_id=key, secret_key=sec, base_url=base)
    except Exception:
        return DryRunBroker()
