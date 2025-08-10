# /app/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base

MYSQL_USER = os.environ.get("PA_MYSQL_USER")       # e.g. yourusername
MYSQL_DB   = os.environ.get("PA_MYSQL_DB")         # e.g. yourusername$default
MYSQL_PW   = os.environ.get("PA_MYSQL_PW")
MYSQL_HOST = os.environ.get("PA_MYSQL_HOST")       # e.g. yourusername.mysql.pythonanywhere-services.com
DB_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PW}@{MYSQL_HOST}/{MYSQL_DB}?charset=utf8mb4"

engine = create_engine(DB_URI, pool_pre_ping=True, pool_recycle=3600, echo=False)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
def init_db(app=None):
    from .models import User, StrategyParam, ApiCredential, RuntimeState, Trade, Position, LogEvent
    Base.metadata.create_all(bind=engine)