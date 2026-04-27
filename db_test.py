from dotenv import load_dotenv
load_dotenv()  # this loads variables from .env into os.environ
Example full script:

from dotenv import load_dotenv
load_dotenv()

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

MYSQL_USER = os.environ.get("PA_MYSQL_USER")
MYSQL_DB   = os.environ.get("PA_MYSQL_DB")
MYSQL_PW   = os.environ.get("PA_MYSQL_PW")
MYSQL_HOST = os.environ.get("PA_MYSQL_HOST")

DB_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PW}@{MYSQL_HOST}/{MYSQL_DB}?charset=utf8mb4"

engine = create_engine(DB_URI, pool_pre_ping=True, pool_recycle=3600)
Session = sessionmaker(bind=engine)
session = Session()

try:
    result = session.execute("SELECT 1")
    print("Database connection: SUCCESS")
except Exception as e:
    print(f"Database connection: FAILED - {e}")
finally:
    session.close()