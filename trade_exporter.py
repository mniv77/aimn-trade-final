<<<<<<< HEAD
# trade_exporter.py
"""
Exports trade history to CSV
"""
import pandas as pd
import os

def export_trades_to_csv(trade_history, filename="trades_export.csv"):
    if not trade_history:
        print("No trades to export.")
        return

    df = pd.DataFrame(trade_history)
    os.makedirs("exports", exist_ok=True)
    df.to_csv(f"exports/{filename}", index=False)
    print(f"✅ Trades exported to exports/{filename}")

# In AIMnPositionManager.update_position():
            # Snapshot plot if df available
            if df is not None:
                from trade_snapshot import save_trade_snapshot
                filename = f"{symbol}_{exit_code.value}_{position.entry_time.strftime('%Y%m%d_%H%M%S')}"
                save_trade_snapshot(
                    df, symbol, position.entry_time, datetime.now(),
                    position.entry_price, exit_price,
                    filename,
                    stop_loss=position.stop_loss_price,
                    rsi=current_rsi,
                    exit_reason=exit_code.value
=======
# trade_exporter.py
"""
Exports trade history to CSV
"""
import pandas as pd
import os

def export_trades_to_csv(trade_history, filename="trades_export.csv"):
    if not trade_history:
        print("No trades to export.")
        return

    df = pd.DataFrame(trade_history)
    os.makedirs("exports", exist_ok=True)
    df.to_csv(f"exports/{filename}", index=False)
    print(f"✅ Trades exported to exports/{filename}")

# In AIMnPositionManager.update_position():
            # Snapshot plot if df available
            if df is not None:
                from trade_snapshot import save_trade_snapshot
                filename = f"{symbol}_{exit_code.value}_{position.entry_time.strftime('%Y%m%d_%H%M%S')}"
                save_trade_snapshot(
                    df, symbol, position.entry_time, datetime.now(),
                    position.entry_price, exit_price,
                    filename,
                    stop_loss=position.stop_loss_price,
                    rsi=current_rsi,
                    exit_reason=exit_code.value
>>>>>>> 0c0df91 (Initial push)
                )