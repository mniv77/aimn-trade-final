# /app/security.py
import os, base64
from cryptography.fernet import Fernet
from .db import db_session
from .models import ApiCredential

def ensure_encryption_key():
    # REQUIRED: set ENCRYPTION_KEY in PA env; generate once: Fernet.generate_key().decode()
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY env var is required.")
    return key

def _f() -> Fernet:
    return Fernet(os.environ["ENCRYPTION_KEY"].encode())

def encrypt(text: str) -> str:
    return _f().encrypt(text.encode()).decode()

def decrypt(token: str) -> str:
    return _f().decrypt(token.encode()).decode()

def upsert_alpaca_keys(key_id: str, secret: str, paper: bool = True):
    cred = db_session.query(ApiCredential).filter_by(venue="alpaca", paper=paper).one_or_none()
    if cred is None:
        cred = ApiCredential(venue="alpaca", paper=paper, key_id_enc=encrypt(key_id), secret_enc=encrypt(secret))
        db_session.add(cred)
    else:
        cred.key_id_enc = encrypt(key_id)
        cred.secret_enc = encrypt(secret)
    db_session.commit()

def get_alpaca_keys(paper: bool = True) -> tuple[str, str]:
    cred = db_session.query(ApiCredential).filter_by(venue="alpaca", paper=paper).one_or_none()
    if not cred:
        raise RuntimeError("Alpaca API keys not found in database.")
    return decrypt(cred.key_id_enc), decrypt(cred.secret_enc)