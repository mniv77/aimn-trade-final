# =========================================
# path: security/secret_box.py
# =========================================
from __future__ import annotations
import os
from typing import Sequence
from cryptography.fernet import Fernet, MultiFernet, InvalidToken

class SecretBox:
    """why: DB secrets at rest encryption; master key in env."""
    def __init__(self, keys: Sequence[bytes]):
        # first key used for encrypt; all keys allowed for decrypt
        ferns = [Fernet(k) for k in keys]
        self._multi = MultiFernet(ferns)
        self._enc = ferns[0]

    def encrypt(self, s: str) -> str:
        return self._enc.encrypt(s.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        try:
            return self._multi.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken as e:
            raise ValueError("secret decrypt failed") from e

def load_secret_box() -> SecretBox:
    """why: one env var with base64 Fernet key; rotation via comma list."""
    raw = os.getenv("APP_MASTER_KEYS") or os.getenv("SECRET_ENCRYPTION_KEY")
    if not raw:
        # one-shot dev key (unsafe for prod); replace in prod
        raw = Fernet.generate_key().decode("utf-8")
        os.environ["SECRET_ENCRYPTION_KEY"] = raw
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return SecretBox([k.encode("utf-8") for k in keys])

BOX = load_secret_box()
