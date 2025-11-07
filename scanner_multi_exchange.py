# scanner_multi_exchange.py - Multi-exchange scanner with position blocking
import time
import threading
from datetime import datetime, timedelta
from app_sub.db import db_session
from app_sub.models import StrategyParam
from shared_models import SignalAlert, ExchangeState
from app_sub.scanner import score_row, should_enter
from app_sub.broker_manager import get_broker

class ExchangeScanner:
    def __init__(self, exchange_name):
        self.exchange_name = exchange_name
        self.running = False
        self.thread = None
        
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._scan_loop, daemon=True)
            self.thread.start()
            
    def stop(self):
        self.running = False
        
    def _scan_loop(self):
        while self.running:
            try:
                # Check if this exchange should be scanning
                exchange_state = db_session.query(ExchangeState).filter_by(exchange=self.exchange_name).first()
                
                if not exchange_state:
                    # Initialize exchange state
                    exchange_state = ExchangeState(exchange=self.exchange_name, is_scanning=True)
                    db_session.add(exchange_state)
                    db_session.commit()
                    
                # Update heartbeat
                exchange_state.last_heartbeat = datetime.now()
                db_session.commit()
                
                # Skip scanning if position is active or emergency stop
                if not exchange_state.is_scanning or exchange_state.emergency_stop:
                    time.sleep(5)
                    continue
                    
                # Perform actual scanning
                self._perform_scan()
                
            except Exception as e:
                print(f"Scanner error on {self.exchange_name}: {e}")
                
            time.sleep(3)  # Scan every 3 seconds
            
    def _perform_scan(self):
        # Get symbols for this exchange
        broker = get_broker(self.exchange_name)
        symbols = broker.list_symbols()[:10]  # Limit for testing
        
        for symbol in symbols:
            # Get strategy params
            params = db_session.query(StrategyParam).filter_by(symbol=symbol).first()
            if not params:
                continue
                
            # Get market data and calculate score
            # This would need real price data - placeholder for now
            score = 0.75  # Simulate score
            
            if should_enter(score, params.entry_threshold):
                # Create signal alert
                alert = SignalAlert(
                    symbol=symbol,
                    direction="BUY",  # Simplified - would determine from indicators
                    exchange=self.exchange_name,
                    user_id="default_user",
                    signal_strength=score,
                    entry_price=100.0  # Would get from market data
                )
                db_session.add(alert)
                
                # Block this exchange from scanning
                exchange_state = db_session.query(ExchangeState).filter_by(exchange=self.exchange_name).first()
                exchange_state.is_scanning = False
                exchange_state.active_position_symbol = symbol
                
                db_session.commit()
                print(f"Signal created for {symbol} on {self.exchange_name} - Scanner paused")
                break

# Initialize scanners for both exchanges
alpaca_scanner = ExchangeScanner("Alpaca")
gemini_scanner = ExchangeScanner("Gemini")

def start_all_scanners():
    alpaca_scanner.start()
    gemini_scanner.start()
    
def stop_all_scanners():
    alpaca_scanner.stop() 
    gemini_scanner.stop()