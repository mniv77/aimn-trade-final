from __future__ import annotations
from sqlalchemy import inspect, text
from app.db import engine
from app.models import StrategyParam

DDL = {
    "mode": "VARCHAR(8) NOT NULL DEFAULT 'BUY'",
    "rsi_period": "INT NOT NULL DEFAULT 14",
    "rsi_buy_whole": "INT NOT NULL DEFAULT 30",
    "rsi_buy_decimal": "INT NOT NULL DEFAULT 0",
    "rsi_sell_whole": "INT NOT NULL DEFAULT 70",
    "rsi_sell_decimal": "INT NOT NULL DEFAULT 0",
    "macd_fast": "INT NOT NULL DEFAULT 12",
    "macd_slow": "INT NOT NULL DEFAULT 26",
    "macd_signal": "INT NOT NULL DEFAULT 9",
    "vol_window": "INT NOT NULL DEFAULT 20",
    "weight_rsi": "DOUBLE NOT NULL DEFAULT 0.5",
    "weight_macd": "DOUBLE NOT NULL DEFAULT 0.3",
    "weight_vol": "DOUBLE NOT NULL DEFAULT 0.2",
    "entry_threshold": "DOUBLE NOT NULL DEFAULT 1.0",
    "trailing_pct_primary_whole": "INT NOT NULL DEFAULT 1",
    "trailing_pct_primary_decimal": "INT NOT NULL DEFAULT 0",
    "trailing_pct_secondary_whole": "INT NOT NULL DEFAULT 2",
    "trailing_pct_secondary_decimal": "INT NOT NULL DEFAULT 0",
    "trailing_start_whole": "INT NOT NULL DEFAULT 1",
    "trailing_start_decimal": "INT NOT NULL DEFAULT 0",
    "stop_loss_whole": "INT NOT NULL DEFAULT 1",
    "stop_loss_decimal": "INT NOT NULL DEFAULT 0",
    "rsi_exit_whole": "INT NOT NULL DEFAULT 50",
    "rsi_exit_decimal": "INT NOT NULL DEFAULT 0",
    "position_size_usd": "INT NOT NULL DEFAULT 50",
    "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
}

def main() -> None:
    insp = inspect(engine)
    tbl = StrategyParam.__tablename__
    if not insp.has_table(tbl):
        with engine.begin() as cx:
            cx.execute(text(f"""
                CREATE TABLE `{tbl}` (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    symbol VARCHAR(32) NOT NULL,
                    timeframe VARCHAR(16) NOT NULL
                )
            """))
    insp = inspect(engine)
    have = {c["name"] for c in insp.get_columns(tbl)}
    need = [k for k in DDL if k not in have]
    if not need:
        print("No column changes needed.")
        return
    with engine.begin() as cx:
        for col in need:
            cx.execute(text(f"ALTER TABLE `{tbl}` ADD COLUMN `{col}` {DDL[col]}"))
            print("Added column:", col)
    print("Migration complete.")

if __name__ == "__main__":
    main()
