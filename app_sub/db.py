# app_sub/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base

MYSQL_USER = os.environ.get("PA_MYSQL_USER")
MYSQL_DB   = os.environ.get("PA_MYSQL_DB")
MYSQL_PW   = os.environ.get("PA_MYSQL_PW")
MYSQL_HOST = os.environ.get("PA_MYSQL_HOST")

if not all([MYSQL_USER, MYSQL_DB, MYSQL_PW, MYSQL_HOST]):
    raise RuntimeError("Missing PA_MYSQL_* env vars")

# --- one-time table creation helper ---
def init_db(app=None):
    # Import models that define tables; they use their own Base
    # and we bind them to this module's engine for create_all.
    try:
        from shared_models import Base
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        # Optional: log/print if you have a logger
        raise



db_url = URL.create(
    "mysql+pymysql",
    username=MYSQL_USER,
    password=MYSQL_PW,  # handles special chars
    host=MYSQL_HOST,
    database=MYSQL_DB,
    query={"charset": "utf8mb4"},
)

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
db_session = scoped_session(SessionLocal)
Base = declarative_base()
