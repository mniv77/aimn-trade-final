from sqlalchemy import text, inspect
from app.db import engine

def main():
    insp = inspect(engine)
    if not insp.has_table("ui_events"):
        with engine.begin() as cx:
            cx.execute(text("""
                CREATE TABLE ui_events (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    kind VARCHAR(32) NOT NULL,
                    ref_id INT NULL,
                    ts DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("Created table: ui_events")
    else:
        print("ui_events already exists.")

if __name__ == "__main__":
    main()
