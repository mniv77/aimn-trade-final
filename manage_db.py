from __future__ import annotations
from config.db import Base, engine
import models  # ensures models are imported
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("DB ready.")
