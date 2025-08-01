# alpaca_connector_fixed.py
"""
Fixed version that handles after-hours data properly
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import alpaca_trade_api as tradeapi
from typing import Optional, Dict
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class AlpacaConnector:
    """
    Connect to Alpaca API - same data source as TradingView
    """
    
    def __init__(self, paper_trading: bool = True):
        """
        Initialize Alpaca connection
        
        Args:
            paper_trading: Use paper account (True) or live account (False)
        """
        # Get credentials from environment or config
        self.api_key = os.getenv('APCA_API_KEY_ID', 'your_api_key_here')
        self.secret_key = os.getenv('APCA_API_SECRET_KEY', 'your_secret_key_here')
        # Use paper or live URL
        if paper_trading:
            self.base_url = 'https://paper-api.alpaca.markets'
            print("🧪 Using Alpaca PAPER trading account")
        else:
            self.base_url = 'https://api.alpaca.markets'
            print("💰 Using Alpaca LIVE trading account")
            
        # Create connection
        try:
            self.api = tradeapi.REST(
                self.api_key,
                self.secret_key,
                self.base_url,
                api_version='v2'
            )
            
            # Test connection
            account = self.api.get_account()
            print(f"✅ Connected to Alpaca!")
            print(f"   Account Status: {account.status}")
            print(f"   Buying Power: ${float(account.buying_power):,.2f}")
            
        except Exception as e:
            print(f"❌ Failed to connect to Alpaca: {e}")
            print("   Please check your API keys in .env file")
            raise
            
    def get_bars(self, symbol: str, timeframe: str = '1Min', limit: int = 200) -> pd.DataFrame:
        """
        Get historical bars - SAME as TradingView chart
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            timeframe: '1Min', '5Min', '15Min', '1Hour', '1Day'
            limit: Number of bars to retrieve
            
        Returns:
            DataFrame with columns: open, high, low, close, volume
        """
        print(f"\n📊 Fetching {symbol} data from Alpaca...")
        print(f"   Timeframe: {timeframe}")
        print(f"   Bars requested: {limit}")
        
        try:
            # Convert timeframe to Alpaca format
            timeframe_map = {
                '1Min': tradeapi.TimeFrame.Minute,
                '5Min': tradeapi.TimeFrame(5, tradeapi.TimeFrameUnit.Minute),
                '15Min': tradeapi.TimeFrame(15, tradeapi.TimeFrameUnit.Minute),
                '1Hour': tradeapi.TimeFrame.Hour,
                '1Day': tradeapi.TimeFrame.Day
            }
            
            alpaca_timeframe = timeframe_map.get(timeframe, tradeapi.TimeFrame.Minute)
            
            # Get bars without specifying start time - let Alpaca handle it
            bars = self.api.get_bars(
                symbol,
                alpaca_timeframe,
                limit=limit,
                adjustment='raw'  # Same as TradingView
            ).df
            
            # Check if we got any data
            if len(bars) == 0:
                print(f"⚠️  No data returned for {timeframe}. Market might be closed.")
                print("   Trying daily timeframe instead...")
                
                # Try daily bars as fallback
                bars = self.api.get_bars(
                    symbol,
                    tradeapi.TimeFrame.Day,
                    limit=limit,
                    adjustment='raw'
                ).df
                
                if len(bars) == 0:
                    raise Exception("No data available for this symbol")
            
            # Ensure column names match our system
            bars = bars.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })
            
            print(f"✅ Retrieved {len(bars)} bars")
            if len(bars) > 0:
                print(f"   Latest close: ${bars['close'].iloc[-1]:.2f}")
                print(f"   Time: {bars.index[-1]}")
            
            return bars
            
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            raise
            
    def get_latest_price(self, symbol: str) -> float:
        """
        Get current price for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Current price
        """
        try:
            trade = self.api.get_latest_trade(symbol)
            return float(trade.price)
        except Exception as e:
            print(f"❌ Error getting price for {symbol}: {e}")
            raise
            
    def get_account_info(self) -> Dict:
        """
        Get account information
        
        Returns:
            Dictionary with account details
        """
        account = self.api.get_account()
        
        return {
            'buying_power': float(account.buying_power),
            'portfolio_value': float(account.portfolio_value),
            'cash': float(account.cash),
            'pattern_day_trader': account.pattern_day_trader,
            'trading_blocked': account.trading_blocked,
            'account_blocked': account.account_blocked
        }
        
    def place_order(self, symbol: str, side: str, qty: float, 
                   order_type: str = 'market', limit_price: Optional[float] = None) -> Dict:
        """
        Place an order through Alpaca
        
        Args:
            symbol: Stock symbol
            side: 'buy' or 'sell'
            qty: Number of shares
            order_type: 'market' or 'limit'
            limit_price: Price for limit orders
            
        Returns:
            Order details
        """
        try:
            if order_type == 'market':
                order = self.api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type='market',
                    time_in_force='gtc' if '/' in symbol else 'day'
                )
            else:
                order = self.api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type='limit',
                    time_in_force='gtc' if '/' in symbol else 'day',
                    limit_price=limit_price
                )
                
            print(f"✅ Order placed: {side.upper()} {qty} {symbol}")
            print(f"   Order ID: {order.id}")
            
            return {
                'id': order.id,
                'symbol': order.symbol,
                'qty': order.qty,
                'side': order.side,
                'type': order.type,
                'status': order.status
            }
            
        except Exception as e:
            print(f"❌ Order failed: {e}")
            raise
            
    def get_positions(self) -> pd.DataFrame:
        """
        Get current positions
        
        Returns:
            DataFrame with position details
        """
        positions = self.api.list_positions()
        
        if not positions:
            return pd.DataFrame()
            
        data = []
        for pos in positions:
            data.append({
                'symbol': pos.symbol,
                'qty': float(pos.qty),
                'side': pos.side,
                'market_value': float(pos.market_value),
                'cost_basis': float(pos.cost_basis),
                'unrealized_pl': float(pos.unrealized_pl),
                'unrealized_plpc': float(pos.unrealized_plpc)
            })
            
        return pd.DataFrame(data)
        
    def is_tradable(self, symbol: str) -> bool:
        """
        Check if a symbol is tradable
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if tradable
        """
        try:
            asset = self.api.get_asset(symbol)
            return asset.tradable and asset.status == 'active'
        except:
            return False


# Specialized connector for our trading system
class AlpacaTradingConnector(AlpacaConnector):
    """
    Extended connector with our trading system features
    """
    
    def __init__(self, paper_trading: bool = True):
        super().__init__(paper_trading)
        
    def get_data_for_validation(self, symbol: str, bars: int = 200) -> pd.DataFrame:
        """
        Get data formatted for Pine Script validation
        
        Args:
            symbol: Stock symbol
            bars: Number of bars
            
        Returns:
            DataFrame ready for indicator calculation
        """
        # Try 1-minute bars first, fall back to daily if needed
        try:
            df = self.get_bars(symbol, '1Min', bars)
        except:
            print("   Falling back to daily data...")
            df = self.get_bars(symbol, '1Day', bars)
        
        # Add any additional data needed
        df['symbol'] = symbol
        
        # Display summary
        print(f"\n📊 Data Summary for {symbol}:")
        print(f"   Bars: {len(df)}")
        if len(df) > 0:
            print(f"   Date Range: {df.index[0]} to {df.index[-1]}")
            print(f"   Current Close: ${df['close'].iloc[-1]:.2f}")
        
        return df
        
    def get_latest_bars(self, symbol: str, count: int = 200) -> pd.DataFrame:
        """
        Get latest bars for live trading (matches scanner interface)
        
        Args:
            symbol: Stock symbol
            count: Number of bars
            
        Returns:
            DataFrame with OHLCV data
        """
        # During market hours, use 1Min; after hours, use daily
        try:
            return self.get_bars(symbol, '1Min', count)
        except:
            return self.get_bars(symbol, '1Day', count)
        
    def get_current_price(self, symbol: str) -> float:
        """
        Get current price (matches position manager interface)
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Current price
        """
        return self.get_latest_price(symbol)


# Test connection
def test_alpaca_connection():
    """
    Test Alpaca connection and data retrieval
    """
    print("\n" + "="*60)
    print("🚀 TESTING ALPACA CONNECTION")
    print("="*60)
    
    # Create connector
    connector = AlpacaTradingConnector(paper_trading=True)
    
    # Test data retrieval
    symbol = 'AAPL'
    df = connector.get_data_for_validation(symbol)
    
    # Show sample data
    if len(df) > 0:
        print(f"\nSample data (last 5 bars):")
        print(df.tail())
    
    # Test current price
    try:
        current_price = connector.get_current_price(symbol)
        print(f"\nCurrent {symbol} price: ${current_price:.2f}")
    except:
        print(f"\nCouldn't get real-time price (market might be closed)")
    
    # Show account info
    account = connector.get_account_info()
    print(f"\nAccount Info:")
    print(f"   Buying Power: ${account['buying_power']:,.2f}")
    print(f"   Portfolio Value: ${account['portfolio_value']:,.2f}")
    
    # Check market status
    clock = connector.api.get_clock()
    print(f"\nMarket Status:")
    print(f"   Is Open: {clock.is_open}")
    print(f"   Next Open: {clock.next_open}")
    print(f"   Next Close: {clock.next_close}")
    
    print("\n✅ Alpaca connection successful!")
    

# Create .env template
def create_env_template():
    """
    Create template for API keys
    """
    template = """# Alpaca API Configuration
# Get your keys from: https://alpaca.markets/

# Paper Trading Keys
ALPACA_API_KEY=your_paper_api_key_here
ALPACA_SECRET_KEY=your_paper_secret_key_here

# Live Trading Keys (when ready)
# ALPACA_LIVE_API_KEY=your_live_api_key_here
# ALPACA_LIVE_SECRET_KEY=your_live_secret_key_here
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(template)
        print("📄 Created .env file template")
        print("   Please add your Alpaca API keys to .env file")
    

if __name__ == "__main__":
    # Create .env template if needed
    create_env_template()
    
    # Test connection
    test_alpaca_connection()