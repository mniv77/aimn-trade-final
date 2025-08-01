# main_v2.py
"""
AIMn Trading System - Enhanced Main Script
Uses configuration file for easy parameter adjustment
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List
import json
import pandas as pd
from market_data import load_all_market_data

# Import configuration
from config import ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL, SYMBOLS, TIMEFRAME, SYMBOL_PARAMS , LOG_LEVEL, LOG_FILE , PAPER_TRADING

# Import components
from alpaca_connector import AlpacaTradingConnector
from scanner import AIMnScanner
from position_manager import AIMnPositionManager, ExitCode
from indicators import AIMnIndicators

# Default trading system constants
CAPITAL_PER_TRADE = 0.3         # Use 30% of available capital per trade
SCAN_INTERVAL = 30              # Scan every 30 seconds



market_data = load_all_market_data()
scanner = AIMnScanner(SYMBOL_PARAMS)
best_trade = scanner.scan_all_symbols(market_data)
 

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AIMnTradingEngine:
    """
    Main trading engine that coordinates all components
    """
    
    def __init__(self, connector: AlpacaTradingConnector, 
                 symbols: List[str], 
                 symbol_params: Dict[str, Dict],
                 capital_per_trade: float = 0.2,
                 scan_interval: int = 60):
        """
        Initialize the AIMn Trading Engine
        """
        self.connector = connector
        self.symbols = symbols
        self.symbol_params = symbol_params
        self.capital_per_trade = capital_per_trade
        self.scan_interval = scan_interval
        
        # Initialize components
        self.scanner = AIMnScanner(symbol_params)
        self.position_manager = AIMnPositionManager(max_positions=1)  # One position at a time
        
        # Control flags
        self.running = False
        
        # Performance tracking
        self.start_time = datetime.now()
        self.initial_portfolio_value = None
        
        logger.info("AIMn Trading Engine initialized")
        logger.info(f"Trading symbols: {symbols}")
        logger.info(f"Scan interval: {scan_interval} seconds")
    
    def get_market_data(self) -> Dict[str, pd.DataFrame]:
        """Fetch latest market data for all symbols"""
        market_data = {}
        
        for symbol in self.symbols:
            try:
                print(f"📊 Fetching {symbol} data from Alpaca...")
                print(f"   Timeframe: {TIMEFRAME}")
                print(f"   Bars requested: 200")
                
                # For crypto symbols (containing /)
                if '/' in symbol:
                    # Calculate time range
                    end_time = datetime.now()
                    start_time = end_time - timedelta(hours=4)
                    
                    # Use get_crypto_bars for crypto
                    bars_response = self.connector.api.get_crypto_bars(
                        symbol,
                        timeframe=TIMEFRAME,
                        start=start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        end=end_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        limit=200
                    )
                    
                    # Get the dataframe
                    bars = bars_response.df
                    
                    if not bars.empty:
                        # Reset index
                        bars = bars.reset_index()
                        
                        # Handle multi-level columns if present
                        if isinstance(bars.columns, pd.MultiIndex):
                            # Flatten multi-level columns
                            bars.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in bars.columns]
                            
                            # Find columns that match our pattern
                            timestamp_col = [col for col in bars.columns if 'timestamp' in col.lower()][0]
                            open_col = [col for col in bars.columns if 'open' in col.lower() and symbol in col][0]
                            high_col = [col for col in bars.columns if 'high' in col.lower() and symbol in col][0]
                            low_col = [col for col in bars.columns if 'low' in col.lower() and symbol in col][0]
                            close_col = [col for col in bars.columns if 'close' in col.lower() and symbol in col][0]
                            volume_col = [col for col in bars.columns if 'volume' in col.lower() and symbol in col][0]
                            
                            # Create clean dataframe
                            df = pd.DataFrame({
                                'timestamp': bars[timestamp_col],
                                'open': bars[open_col],
                                'high': bars[high_col],
                                'low': bars[low_col],
                                'close': bars[close_col],
                                'volume': bars[volume_col]
                            })
                        else:
                            # Simple columns
                            df = bars[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                        
                        print(f"   ✅ Got {len(df)} bars, latest price: ${df['close'].iloc[-1]:.2f}")
                    else:
                        print(f"   ⚠️ No data returned")
                        df = pd.DataFrame()
                else:
                    # Regular stock data
                    df = self.connector.get_bars(symbol, TIMEFRAME, 200)
                    if len(df) > 0:
                        print(f"   ✅ Got {len(df)} bars")
                
                if len(df) > 0:
                    market_data[symbol] = df
                    logger.debug(f"Fetched data for {symbol}: {len(df)} bars")
                else:
                    logger.warning(f"No data returned for {symbol}")
                    
            except Exception as e:
                print(f"❌ Error fetching data: {e}")
                logger.error(f"Failed to fetch data for {symbol}: {e}")
        
        return market_data
    
    def calculate_position_size(self, price: float) -> float:
        """Calculate number of shares to trade based on available capital"""
        try:
            account = self.connector.get_account_info()
            # Use CASH instead of buying power for more accurate calculation
            available_capital = float(account.get('cash', account['buying_power']))
            
            # Use specified fraction of capital
            position_value = available_capital * self.capital_per_trade
            # Add safety margin to avoid insufficient funds
            position_value = position_value * 0.95  # Use 95% to account for fees
            
            # For crypto, we can have fractional shares
            if any('/' in s for s in self.symbols):  # It's crypto
                shares = position_value / price
                # Round to appropriate decimal places
                if price > 1000:
                    shares = round(shares, 4)  # For BTC
                elif price > 100:
                    shares = round(shares, 3)  # For ETH
                else:
                    shares = round(shares, 2)  # For smaller cryptos
                return max(0.001, shares)  # Minimum crypto amount
            else:
                # For stocks, must be whole shares
                shares = int(position_value / price)
                return max(1, shares)
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0
    
    def process_active_positions(self, market_data: Dict[str, pd.DataFrame]):
        """Update and check exits for all active positions"""
        for symbol, position in list(self.position_manager.positions.items()):
            try:
                # Get current data
                if symbol not in market_data:
                    continue
                
                df = market_data[symbol]
                current_price = df['close'].iloc[-1]
                
                # Calculate current RSI for RSI exit
                params = self.scanner.get_symbol_params(symbol)
                df_with_indicators = AIMnIndicators.calculate_all_indicators(df, params)
                current_rsi = df_with_indicators['rsi_real'].iloc[-1]
                
                # Update position and check for exit
                exit_info = self.position_manager.update_position(
                    symbol, current_price, current_rsi
                )
                
                if exit_info:
                    # Execute the exit trade
                    self.execute_exit_trade(exit_info)
                    
                    # Log the trade
                    self.log_trade(exit_info)
                    
                    # Show current statistics
                    stats = self.position_manager.get_statistics()
                    logger.info(f"📊 Stats: Trades={stats['total_trades']}, "
                               f"Win Rate={stats['win_rate']:.1f}%, "
                               f"Total P&L=${stats['total_pnl']:.2f}")
                    
            except Exception as e:
                logger.error(f"Error processing position {symbol}: {e}")
    
    def execute_exit_trade(self, exit_info: Dict):
        """Execute exit trade with broker"""
        try:
            # Determine exit side (opposite of entry)
            exit_side = 'sell' if exit_info['direction'] == 'BUY' else 'buy'
            
            # Place exit order
            order = self.connector.place_order(
                symbol=exit_info['symbol'],
                side=exit_side,
                qty=exit_info['shares']
            )
            
            logger.info(f"🚪 EXIT ORDER PLACED: {exit_side} {exit_info['shares']} shares of "
                       f"{exit_info['symbol']} @ market")
                       
        except Exception as e:
            logger.error(f"Failed to execute exit order: {e}")
    
    def execute_trade(self, opportunity: Dict):
        """Execute a trade based on scanner opportunity"""
        try:
            # Calculate position size
            shares = self.calculate_position_size(opportunity['entry_price'])
            
            if shares == 0:
                logger.warning("Insufficient capital for trade")
                return
            
            # Get symbol parameters
            params = self.scanner.get_symbol_params(opportunity['symbol'])
            
            # Place order with broker
            order = self.connector.place_order(
                symbol=opportunity['symbol'],
                side='buy' if opportunity['direction'] == 'BUY' else 'sell',
                qty=shares
            )
            
            # Record position
            position = self.position_manager.enter_position(
                opportunity, shares, params
            )
            
            # Log entry
            unit_type = "units" if '/' in opportunity['symbol'] else "shares"
            logger.info(f"🎯 TRADE EXECUTED: {opportunity['direction']} {shares} {unit_type} of "
                       f"{opportunity['symbol']} @ ${opportunity['entry_price']:.2f}")
            logger.info(f"📈 Indicators: RSI={opportunity['indicators']['rsi_real']:.1f}, "
                       f"Volume Ratio={opportunity['indicators']['volume_ratio']:.2f}, "
                       f"ATR Ratio={opportunity['indicators']['atr_ratio']:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to execute trade: {e}")
    
    def run_trading_cycle(self):
        """Run one complete trading cycle"""
        try:
            logger.info("="*50)
            logger.info(f"Trading cycle started at {datetime.now()}")
            
            # Check if we're trading crypto (24/7 market)
            is_crypto = any('/' in s for s in self.symbols)
            
            if not is_crypto:
                # Check market status for stocks
                clock = self.connector.api.get_clock()
                if not clock.is_open:
                    logger.info(f"⏰ Market is CLOSED. Next open: {clock.next_open}")
                    return
            else:
                logger.info("🌐 Trading crypto - market is always open!")
            
            # 1. Get latest market data
            market_data = self.get_market_data()
            
            if not market_data:
                logger.warning("No market data available")
                return
            
            # 2. Process existing positions
            self.process_active_positions(market_data)
            
            # 3. If no position, scan for opportunities
            if not self.position_manager.has_position():
                logger.info("🔍 No active position, scanning for opportunities...")
                
                opportunity = self.scanner.scan_all_symbols(market_data)
                
                if opportunity:
                    logger.info(f"💡 Opportunity found: {opportunity['symbol']} "
                               f"{opportunity['direction']} (score: {opportunity['score']:.1f})")
                    
                    self.execute_trade(opportunity)
                else:
                    logger.info("   No trading opportunities found")
            else:
                # Log current position status
                for symbol, position in self.position_manager.positions.items():
                    logger.info(f"📊 Active position: {symbol} {position.direction} | "
                               f"P&L: ${position.unrealized_pnl:.2f} "
                               f"({position.unrealized_pnl_pct:.2f}%)")
                    
                    if position.early_trail_active:
                        logger.info(f"   🔵 Early trail active: ${position.early_trail_price:.2f}")
                    if position.peak_trail_active:
                        logger.info(f"   🟢 Peak trail active: ${position.peak_trail_price:.2f}")
            
            # Show account status
            self.show_account_status()
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
    
    def show_account_status(self):
        """Display current account status"""
        try:
            account = self.connector.get_account_info()
            
            # Track performance
            if self.initial_portfolio_value is None:
                self.initial_portfolio_value = account['portfolio_value']
            
            current_value = account['portfolio_value']
            total_return = ((current_value - self.initial_portfolio_value) / 
                           self.initial_portfolio_value * 100) if self.initial_portfolio_value > 0 else 0
            
            logger.info(f"\n💰 Account Status:")
            logger.info(f"   Portfolio Value: ${current_value:,.2f}")
            logger.info(f"   Buying Power: ${account['buying_power']:,.2f}")
            logger.info(f"   Session Return: {total_return:+.2f}%")
            
        except Exception as e:
            logger.error(f"Error getting account status: {e}")
    
    def log_trade(self, trade_info: Dict):
        """Log completed trade to file"""
        with open('aimn_trades.json', 'a') as f:
            f.write(json.dumps(trade_info, default=str) + '\n')
        
        # Also log to performance file if enabled
        if TRACK_PERFORMANCE:
            self.log_performance(trade_info)
    
    def log_performance(self, trade_info: Dict):
        """Log trade performance for analysis"""
        try:
            performance_data = {
                'timestamp': datetime.now().isoformat(),
                'symbol': trade_info['symbol'],
                'direction': trade_info['direction'],
                'entry_price': trade_info['entry_price'],
                'exit_price': trade_info['exit_price'],
                'shares': trade_info['shares'],
                'pnl': trade_info['pnl'],
                'pnl_pct': trade_info['pnl_pct'],
                'exit_code': trade_info['exit_code'],
                'hold_time': (trade_info['exit_time'] - trade_info['entry_time']).total_seconds() / 60
            }
            
            # Append to CSV
            df = pd.DataFrame([performance_data])
            df.to_csv(PERFORMANCE_FILE, mode='a', header=not pd.io.common.file_exists(PERFORMANCE_FILE), index=False)
            
        except Exception as e:
            logger.error(f"Error logging performance: {e}")
    
    def start(self):
        """Start the trading engine"""
        logger.info("🚀 Starting AIMn Trading Engine...")
        self.running = True
        
        # Show initial account status
        try:
            account = self.connector.get_account_info()
            logger.info(f"📊 Initial Account Status:")
            logger.info(f"   Buying Power: ${account['buying_power']:,.2f}")
            logger.info(f"   Portfolio Value: ${account['portfolio_value']:,.2f}")
            
            # Check current positions
            positions = self.connector.get_positions()
            if not positions.empty:
                logger.info(f"\n📈 Current Positions:")
                for _, pos in positions.iterrows():
                    logger.info(f"   {pos['symbol']}: {pos['qty']} shares @ ${pos['market_value']:,.2f}")
                    
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
        
        # Main trading loop
        while self.running:
            try:
                self.run_trading_cycle()
                
                # Wait before next cycle
                logger.info(f"\n⏳ Waiting {self.scan_interval} seconds until next scan...")
                time.sleep(self.scan_interval)
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(30)  # Wait 30 seconds on error
    
    def stop(self):
        """Stop the trading engine"""
        logger.info("Stopping AIMn Trading Engine...")
        self.running = False
        
        # Show final statistics
        stats = self.position_manager.get_statistics()
        runtime = (datetime.now() - self.start_time).total_seconds() / 3600
        
        logger.info("="*50)
        logger.info("📊 FINAL STATISTICS:")
        logger.info(f"⏱️  Runtime: {runtime:.1f} hours")
        logger.info(f"📈 Total Trades: {stats['total_trades']}")
        logger.info(f"✅ Winning Trades: {stats['winning_trades']}")
        logger.info(f"❌ Losing Trades: {stats['losing_trades']}")
        logger.info(f"📊 Win Rate: {stats['win_rate']:.1f}%")
        logger.info(f"💰 Total P&L: ${stats['total_pnl']:.2f}")
        logger.info(f"💵 Average P&L: ${stats['avg_pnl']:.2f}")
        logger.info("="*50)


def main():
    """Main entry point"""
    # Detect if we're trading crypto
    is_crypto = any('/' in s for s in SYMBOLS)
    
    print("\n" + "="*60)
    if is_crypto:
        print("🌐 AIMn CRYPTO TRADING SYSTEM V2.0")
    else:
        print("🚀 AIMn TRADING SYSTEM V2.0")
    print("="*60)
    print("Philosophy: Let the market pick your trades.")
    print("            Let logic pick your exits.")
    print("="*60 + "\n")
    
    # Initialize Alpaca connector
    print("1️⃣ Connecting to Alpaca...")
    connector = AlpacaTradingConnector(paper_trading=PAPER_TRADING)
    
    # Initialize trading engine
    print("\n2️⃣ Initializing AIMn Trading Engine...")
    engine = AIMnTradingEngine(
        connector=connector,
        symbols=SYMBOLS,
        symbol_params=SYMBOL_PARAMS,
        capital_per_trade=CAPITAL_PER_TRADE,
        scan_interval=SCAN_INTERVAL
    )
    
    # Start trading
    print("\n3️⃣ Starting automated trading...")
    print("   Press Ctrl+C to stop\n")
    
    try:
        engine.start()
    except KeyboardInterrupt:
        print("\n\n⛔ Shutdown signal received")
        engine.stop()


if __name__ == "__main__":
    main()