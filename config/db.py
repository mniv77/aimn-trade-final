# config/db.py
from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# Prefer real DB via env; fallback to local SQLite file
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("SQLALCHEMY_DATABASE_URI")
    or f"sqlite:///{os.path.join(os.getcwd(), 'aimn.db')}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
)
Base = declarative_base()

def get_db():
    """Yield a session; always closes. Used by blueprints/services."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
