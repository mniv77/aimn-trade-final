# /aimn-trade-final/trading_connector.py
import json
import os
from datetime import datetime

class TradingDataConnector:
    def __init__(self):
        # Use current directory for data files
        self.data_path = os.path.dirname(os.path.abspath(__file__))
        
    def get_scanner_data(self):
        """Read current scanner status from your bot"""
        try:
            with open(os.path.join(self.data_path, 'scanner_status.json'), 'r') as f:
                return json.load(f)
        except:
            # Return empty list if file doesn't exist yet
            return []
    
    def get_active_trades(self):
        """Get current open positions"""
        try:
            with open(os.path.join(self.data_path, 'active_trades.json'), 'r') as f:
                return json.load(f)
        except:
            return []
    
    def get_account_stats(self):
        """Get account statistics"""
        try:
            with open(os.path.join(self.data_path, 'account_stats.json'), 'r') as f:
                return json.load(f)
        except:
            return {
                "buying_power": 373093.52,
                "total_pnl": 0,
                "win_rate": 0,
                "active_trades": 0
            }