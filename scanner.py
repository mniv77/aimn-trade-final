
# scanner.py
"""
Multi-symbol scanner for AIMn Trading System
Scans all symbols and finds the best trading opportunity
"""

import pandas as pd
import logging
from typing import Dict, List, Optional
from indicators import AIMnIndicators

logger = logging.getLogger(__name__)


class AIMnScanner:
    """Scanner to find trading opportunities across multiple symbols"""
    
    def __init__(self, symbol_params: Dict[str, Dict]):
        """
        Initialize scanner with symbol-specific parameters
        
        Args:
            symbol_params: Dictionary of parameters for each symbol
        """
        self.symbol_params = symbol_params
        self.default_params = symbol_params.get('DEFAULT', {})
    
    def get_symbol_params(self, symbol: str) -> Dict:
        """Get parameters for a specific symbol"""
        # Try exact match first
        if symbol in self.symbol_params:
            return self.symbol_params[symbol]
        
        # Try without slash for crypto (BTC/USD -> BTCUSD)
        symbol_no_slash = symbol.replace('/', '')
        if symbol_no_slash in self.symbol_params:
            return self.symbol_params[symbol_no_slash]
        
        # Return default parameters
        return self.default_params.copy()
    
    def calculate_opportunity_score(self, df: pd.DataFrame, params: Dict, direction: str) -> float:
        """
        Calculate a score for the trading opportunity
        Higher score = better opportunity
        """
        if len(df) < 2:
            return 0
        
        latest = df.iloc[-1]
        score = 0
        
        # RSI component (0-40 points)
        rsi = latest['rsi_real']
        if direction == 'BUY':
            rsi_oversold = params.get('rsi_oversold', 30)
            if rsi <= rsi_oversold:
                # The lower the RSI, the higher the score
                rsi_score = (rsi_oversold - rsi) / rsi_oversold * 40
                score += rsi_score
        else:  # SELL
            rsi_overbought = params.get('rsi_overbought', 70)
            if rsi >= rsi_overbought:
                # The higher the RSI, the higher the score
                rsi_score = (rsi - rsi_overbought) / (100 - rsi_overbought) * 40
                score += rsi_score
        
        # MACD component (0-30 points)
        if direction == 'BUY' and latest.get('macd_cross_up', False):
            score += 30
        elif direction == 'SELL' and latest.get('macd_cross_down', False):
            score += 30
        
        # Volume component (0-20 points)
        volume_ratio = latest['volume_ratio']
        volume_threshold = params.get('volume_threshold', 1.2)
        if volume_ratio >= volume_threshold:
            volume_score = min((volume_ratio - 1) * 10, 20)
            score += volume_score
        
        # ATR component (0-10 points)
        atr_ratio = latest['atr_ratio']
        atr_threshold = params.get('atr_threshold', 1.3)
        if atr_ratio >= atr_threshold:
            atr_score = min((atr_ratio - 1) * 10, 10)
            score += atr_score
        
        return score
    
    def scan_symbol(self, symbol: str, df: pd.DataFrame) -> Optional[Dict]:
        """
        Scan a single symbol for trading opportunities
        
        Returns:
            Dictionary with opportunity details or None
        """
        if df is None or len(df) < 50:  # Need minimum bars for indicators
            logger.debug(f"Insufficient data for {symbol}")
            return None
        
        # Get symbol-specific parameters
        params = self.get_symbol_params(symbol)
        
        # Calculate all indicators
        df_with_indicators = AIMnIndicators.calculate_all_indicators(df, params)
        
        # Check entry conditions
        conditions = AIMnIndicators.check_entry_conditions(df_with_indicators, params)
        
        # Get latest values
        latest = df_with_indicators.iloc[-1]
        
        # Create opportunity if conditions are met
        if conditions['buy']:
            score = self.calculate_opportunity_score(df_with_indicators, params, 'BUY')
            return {
                'symbol': symbol,
                'direction': 'BUY',
                'entry_price': latest['close'],
                'score': score,
                'indicators': {
                    'rsi_real': latest['rsi_real'],
                    'macd': latest['macd'],
                    'signal': latest['signal'],
                    'volume_ratio': latest['volume_ratio'],
                    'atr_ratio': latest['atr_ratio'],
                    'obv_trend': latest['obv_trend']
                },
                'conditions': conditions
            }
        
        elif conditions['sell']:
            score = self.calculate_opportunity_score(df_with_indicators, params, 'SELL')
            return {
                'symbol': symbol,
                'direction': 'SELL',
                'entry_price': latest['close'],
                'score': score,
                'indicators': {
                    'rsi_real': latest['rsi_real'],
                    'macd': latest['macd'],
                    'signal': latest['signal'],
                    'volume_ratio': latest['volume_ratio'],
                    'atr_ratio': latest['atr_ratio'],
                    'obv_trend': latest['obv_trend']
                },
                'conditions': conditions
            }
        
        return None
    
    def scan_all_symbols(self, market_data: Dict[str, pd.DataFrame]) -> Optional[Dict]:
        """
        Scan all symbols and return the best opportunity
        
        Args:
            market_data: Dictionary of DataFrames for each symbol
            
        Returns:
            Best opportunity or None
        """
        opportunities = []
        
        for symbol, df in market_data.items():
            try:
                opportunity = self.scan_symbol(symbol, df)
                if opportunity:
                    opportunities.append(opportunity)
                    logger.debug(f"Opportunity found: {symbol} {opportunity['direction']} "
                               f"(score: {opportunity['score']:.1f})")
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
        
        # Return the highest scoring opportunity
        if opportunities:
            best_opportunity = max(opportunities, key=lambda x: x['score'])
            logger.info(f"Best opportunity: {best_opportunity['symbol']} "
                       f"{best_opportunity['direction']} "
                       f"(score: {best_opportunity['score']:.1f})")
            return best_opportunity
        
        return None
    
    def get_signal_summary(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """
        Get a summary of signals for all symbols (for dashboard/monitoring)
        """
        summary = {}
        
        for symbol, df in market_data.items():
            if df is None or len(df) < 50:
                summary[symbol] = {'status': 'insufficient_data'}
                continue
            
            try:
                params = self.get_symbol_params(symbol)
                df_with_indicators = AIMnIndicators.calculate_all_indicators(df, params)
                latest = df_with_indicators.iloc[-1]
                conditions = AIMnIndicators.check_entry_conditions(df_with_indicators, params)
                
                summary[symbol] = {
                    'status': 'ready',
                    'price': latest['close'],
                    'rsi': latest['rsi_real'],
                    'volume_ratio': latest['volume_ratio'],
                    'atr_ratio': latest['atr_ratio'],
                    'buy_ready': conditions['buy'],
                    'sell_ready': conditions['sell'],
                    'missing_buy': [],
                    'missing_sell': []
                }
                
                # Check what's missing for buy signal
                if not conditions['buy']:
                    if not conditions['rsi_buy']:
                        summary[symbol]['missing_buy'].append('RSI')
                    if not conditions['macd_buy']:
                        summary[symbol]['missing_buy'].append('MACD')
                    if not conditions['volume_buy']:
                        summary[symbol]['missing_buy'].append('Volume')
                    if not conditions['high_volatility']:
                        summary[symbol]['missing_buy'].append('ATR')
                
                # Check what's missing for sell signal
                if not conditions['sell']:
                    if not conditions['rsi_sell']:
                        summary[symbol]['missing_sell'].append('RSI')
                    if not conditions['macd_sell']:
                        summary[symbol]['missing_sell'].append('MACD')
                    if not conditions['volume_sell']:
                        summary[symbol]['missing_sell'].append('Volume')
                    if not conditions['high_volatility']:
                        summary[symbol]['missing_sell'].append('ATR')
                        
            except Exception as e:
                summary[symbol] = {'status': 'error', 'error': str(e)}
        
        return summary


# Test the scanner
if __name__ == "__main__":
    # Test with sample data
    import numpy as np
    
    # Create sample parameters
    test_params = {
        'DEFAULT': {
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'volume_threshold': 1.2,
            'atr_threshold': 1.3
        }
    }
    
    # Create sample market data
    dates = pd.date_range('2023-01-01', periods=100, freq='1min')
    
    market_data = {}
    for symbol in ['BTC/USD', 'ETH/USD']:
        np.random.seed(hash(symbol) % 100)
        df = pd.DataFrame({
            'timestamp': dates,
            'open': 100 + np.random.randn(100).cumsum(),
            'high': 102 + np.random.randn(100).cumsum(),
            'low': 98 + np.random.randn(100).cumsum(),
            'close': 100 + np.random.randn(100).cumsum(),
            'volume': 1000 + np.random.randint(-100, 100, 100)
        })
        market_data[symbol] = df
    
    # Test scanner
    scanner = AIMnScanner(test_params)
    
    # Scan all symbols
    best_opportunity = scanner.scan_all_symbols(market_data)
    
    if best_opportunity:
        print(f"Best opportunity: {best_opportunity['symbol']} {best_opportunity['direction']}")
        print(f"Score: {best_opportunity['score']:.1f}")
        print(f"Entry price: ${best_opportunity['entry_price']:.2f}")
    else:
        print("No opportunities found")
    
    # Get summary
    summary = scanner.get_signal_summary(market_data)
    print("\nSignal Summary:")
    for symbol, info in summary.items():
        print(f"{symbol}: {info}")