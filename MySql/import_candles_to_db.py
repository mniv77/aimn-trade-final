import os
import pandas as pd
from sqlalchemy import create_engine

# If you use a .env file for credentials, load it (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MYSQL_USER = os.environ.get("PA_MYSQL_USER")
MYSQL_DB   = os.environ.get("PA_MYSQL_DB")
MYSQL_PW   = os.environ.get("PA_MYSQL_PW")
MYSQL_HOST = os.environ.get("PA_MYSQL_HOST")

DB_URI = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PW}@{MYSQL_HOST}/{MYSQL_DB}?charset=utf8mb4"
engine = create_engine(DB_URI, pool_pre_ping=True, pool_recycle=3600)

# Read the cleaned CSV
csv_path = os.path.join(os.path.dirname(__file__), "btc_ohlcv_for_db.csv")
df = pd.read_csv(csv_path)

# Import to MySQL (append mode)
df.to_sql("candles", engine, if_exists="append", index=False)
print("Imported CSV data into MySQL candles table.")