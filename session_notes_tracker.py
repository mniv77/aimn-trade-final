<<<<<<< HEAD
# session_notes_tracker.py

"""
📌 AIMn Trading Session Log
Maintained automatically to track session progress.
This log summarizes our Streamlit backtest dashboard upgrades.
"""

import datetime
import pymysql
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

session_notes = [
    "✅ Connected to MySQL on PythonAnywhere (PEW) and reading backtest data from `backtests` table",
    "✅ Added drawdown calculation, visualization, and filtering",
    "✅ Implemented rolling Sharpe ratio, CAGR, and MAR ratio",
    "✅ Built drawdown summary table with DD start/end/duration",
    "✅ Added export to CSV for filtered results and drawdown stats",
    "✅ Dual-axis plots for cumulative profit and drawdown",
    "✅ Stability tag based on MAR ratio (Stable vs Volatile)",
    "✅ Added filters for stability and drawdown threshold",
    "✅ Sortable drawdown table by Strategy, MAR, DD duration, etc.",
    "✅ Included number of trades per strategy",
    "✅ Added heatmap of risk-adjusted performance (CAGR, MAR, DD)",
    "🛠️ Next planned: normalize heatmap 0-1 and profit per trade"
]


def save_log_to_db(session_id: str = "default_user"):
    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"),
            port=int(os.getenv("MYSQL_PORT", 3306))
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(50),
                    note TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )""")
            for note in session_notes:
                cursor.execute("INSERT INTO session_log (session_id, note) VALUES (%s, %s)", (session_id, note))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"❌ Failed to save log to DB: {e}")
        return False


def write_log_to_file():
    filename = f"session_log_{datetime.date.today()}.txt"
    with open(filename, "w") as f:
        for i, note in enumerate(session_notes, 1):
            f.write(f"{i:02d}. {note}\n")
    return filename


def fetch_log_from_db():
    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"),
            port=int(os.getenv("MYSQL_PORT", 3306))
        )
        df = pd.read_sql("SELECT * FROM session_log ORDER BY timestamp DESC", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"❌ Could not fetch past logs: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    st.title("📘 AIMn Trading System Log Exporter")

    session_id = st.text_input("Enter Session ID or User Name:", value="user01")

    if st.button("💾 Export Session Log to Database"):
        if save_log_to_db(session_id):
            st.success("✅ Session log exported to database successfully.")

    if st.button("📝 Export Session Log to TXT File"):
        filename = write_log_to_file()
        st.success(f"📝 Session log saved as: {filename}")

    st.markdown("---")
    st.subheader("🧾 Current Session Notes")
    for i, note in enumerate(session_notes, 1):
        st.write(f"{i:02d}. {note}")

    st.markdown("---")
    st.subheader("📂 View Past Logs")
    log_df = fetch_log_from_db()
    if not log_df.empty:
        user_filter = st.selectbox("Filter by Session ID", options=["All"] + sorted(log_df["session_id"].unique()))
        if user_filter != "All":
            log_df = log_df[log_df["session_id"] == user_filter]

        date_range = st.date_input("Filter by Date Range", [log_df["timestamp"].min().date(), log_df["timestamp"].max().date()])
        if isinstance(date_range, list) and len(date_range) == 2:
            start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
            log_df = log_df[(log_df["timestamp"] >= start_date) & (log_df["timestamp"] <= end_date)]

        search_term = st.text_input("Search Notes for Keyword:").strip()
        if search_term:
            log_df = log_df[log_df["note"].str.contains(search_term, case=False, na=False)]

        st.dataframe(log_df)
        st.markdown(f"**Total Sessions Logged:** {log_df['session_id'].nunique()} | **Total Notes:** {len(log_df)}")
=======
# session_notes_tracker.py

"""
📌 AIMn Trading Session Log
Maintained automatically to track session progress.
This log summarizes our Streamlit backtest dashboard upgrades.
"""

import datetime
import pymysql
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

session_notes = [
    "✅ Connected to MySQL on PythonAnywhere (PEW) and reading backtest data from `backtests` table",
    "✅ Added drawdown calculation, visualization, and filtering",
    "✅ Implemented rolling Sharpe ratio, CAGR, and MAR ratio",
    "✅ Built drawdown summary table with DD start/end/duration",
    "✅ Added export to CSV for filtered results and drawdown stats",
    "✅ Dual-axis plots for cumulative profit and drawdown",
    "✅ Stability tag based on MAR ratio (Stable vs Volatile)",
    "✅ Added filters for stability and drawdown threshold",
    "✅ Sortable drawdown table by Strategy, MAR, DD duration, etc.",
    "✅ Included number of trades per strategy",
    "✅ Added heatmap of risk-adjusted performance (CAGR, MAR, DD)",
    "🛠️ Next planned: normalize heatmap 0-1 and profit per trade"
]


def save_log_to_db(session_id: str = "default_user"):
    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"),
            port=int(os.getenv("MYSQL_PORT", 3306))
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(50),
                    note TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )""")
            for note in session_notes:
                cursor.execute("INSERT INTO session_log (session_id, note) VALUES (%s, %s)", (session_id, note))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"❌ Failed to save log to DB: {e}")
        return False


def write_log_to_file():
    filename = f"session_log_{datetime.date.today()}.txt"
    with open(filename, "w") as f:
        for i, note in enumerate(session_notes, 1):
            f.write(f"{i:02d}. {note}\n")
    return filename


def fetch_log_from_db():
    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE"),
            port=int(os.getenv("MYSQL_PORT", 3306))
        )
        df = pd.read_sql("SELECT * FROM session_log ORDER BY timestamp DESC", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"❌ Could not fetch past logs: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    st.title("📘 AIMn Trading System Log Exporter")

    session_id = st.text_input("Enter Session ID or User Name:", value="user01")

    if st.button("💾 Export Session Log to Database"):
        if save_log_to_db(session_id):
            st.success("✅ Session log exported to database successfully.")

    if st.button("📝 Export Session Log to TXT File"):
        filename = write_log_to_file()
        st.success(f"📝 Session log saved as: {filename}")

    st.markdown("---")
    st.subheader("🧾 Current Session Notes")
    for i, note in enumerate(session_notes, 1):
        st.write(f"{i:02d}. {note}")

    st.markdown("---")
    st.subheader("📂 View Past Logs")
    log_df = fetch_log_from_db()
    if not log_df.empty:
        user_filter = st.selectbox("Filter by Session ID", options=["All"] + sorted(log_df["session_id"].unique()))
        if user_filter != "All":
            log_df = log_df[log_df["session_id"] == user_filter]

        date_range = st.date_input("Filter by Date Range", [log_df["timestamp"].min().date(), log_df["timestamp"].max().date()])
        if isinstance(date_range, list) and len(date_range) == 2:
            start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
            log_df = log_df[(log_df["timestamp"] >= start_date) & (log_df["timestamp"] <= end_date)]

        search_term = st.text_input("Search Notes for Keyword:").strip()
        if search_term:
            log_df = log_df[log_df["note"].str.contains(search_term, case=False, na=False)]

        st.dataframe(log_df)
        st.markdown(f"**Total Sessions Logged:** {log_df['session_id'].nunique()} | **Total Notes:** {len(log_df)}")
>>>>>>> 0c0df91 (Initial push)
