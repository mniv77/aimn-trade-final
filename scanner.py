# scanner.py
'''
AIMn Trading System - Multi-Symbol Scanner
Continuously scans for the best opportunity across all symbols
'''

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
from indicators import AIMnIndicators

logger = logging.getLogger(__name__)


class AIMnScanner:
    '''
    Scanner that finds the best trading opportunity across multiple symbols
    '''
    
    def __init__(self, symbol_params: Dict[str, Dict]):
        '''
        Initialize scanner with symbol-specific parameters
        
        symbol_params format:
        {
            'AAPL': {
                'rsi_window': 100,
                'rsi_overbought': 70,
                'rsi_oversold': 30,
                'volume_threshold': 0.9,
                'atr_multiplier': 1.2,
                ...
            },
            'BTC/USD': {...}
        }
        '''
        self.symbol_params = symbol_params
        self.default_params = {
            'rsi_window': 100,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'volume_threshold': 1.0,
            'atr_multiplier': 1.3,
            'obv_period': 20
        }
    
    def get_symbol_params(self, symbol: str) -> Dict:
        '''Get parameters for a specific symbol, using defaults if not specified'''
        params = self.default_params.copy()
        if symbol in self.symbol_params:
            params.update(self.symbol_params[symbol])
        return params
    
    def check_buy_conditions(self, df: pd.DataFrame, params: Dict) -> Tuple[bool, float]:
        '''
        Check if BUY conditions are met
        Returns (signal_present, score)
        '''
        if len(df) < 100:  # Need enough data
            return False, 0.0
        
        latest = df.iloc[-1]
        
        # Check only RSI and MACD (volume/ATR disabled)
        rsi_oversold = latest['rsi_real'] <= params['rsi_oversold']
        macd_bullish = latest['macd_bullish_cross']
        volume_confirmed = True  # DISABLED - always pass
        volatility_good = True   # DISABLED - always pass
        
        # Only RSI and MACD required now
        signal = rsi_oversold and macd_bullish
        
        # Calculate score (0-100) based on strength of signals
        score = 0.0
        if signal:
            # RSI contribution (stronger oversold = higher score)
            rsi_score = (params['rsi_oversold'] - latest['rsi_real']) / params['rsi_oversold'] * 25
            
            # MACD contribution (histogram strength)
            macd_score = min(abs(latest['macd_histogram']) * 10, 25)
            
            # Volume contribution (how much above average)
            volume_ratio = latest['volume'] / df['volume'].rolling(20).mean().iloc[-1]
            volume_score = min((volume_ratio - 1) * 10, 25)
            
            # ATR contribution (how much expansion)
            atr_ratio = latest['atr'] / latest['atr_ma']
            atr_score = min((atr_ratio - params['atr_multiplier']) * 10, 25)
            
            score = rsi_score + macd_score + volume_score + atr_score
            score = max(0, min(100, score))  # Clamp to 0-100
        
        return signal, score
    
    def check_sell_conditions(self, df: pd.DataFrame, params: Dict) -> Tuple[bool, float]:
        '''
        Check if SELL conditions are met
        Returns (signal_present, score)
        '''
        if len(df) < 100:
            return False, 0.0
        
        latest = df.iloc[-1]
        
        # Check only RSI and MACD (volume/ATR disabled)
        rsi_overbought = latest['rsi_real'] >= params['rsi_overbought']
        macd_bearish = latest['macd_bearish_cross']
        volume_confirmed = True  # DISABLED - always pass
        volatility_good = True   # DISABLED - always pass
        
        # Only RSI and MACD required now
        signal = rsi_overbought and macd_bearish
        
        # Calculate score
        score = 0.0
        if signal:
            # RSI contribution
            rsi_score = (latest['rsi_real'] - params['rsi_overbought']) / (100 - params['rsi_overbought']) * 25
            
            # MACD contribution
            macd_score = min(abs(latest['macd_histogram']) * 10, 25)
            
            # Volume contribution
            volume_ratio = latest['volume'] / df['volume'].rolling(20).mean().iloc[-1]
            volume_score = min((volume_ratio - 1) * 10, 25)
            
            # ATR contribution
            atr_ratio = latest['atr'] / latest['atr_ma']
            atr_score = min((atr_ratio - params['atr_multiplier']) * 10, 25)
            
            score = rsi_score + macd_score + volume_score + atr_score
            score = max(0, min(100, score))
        
        return signal, score
    
    def scan_all_symbols(self, market_data: Dict[str, pd.DataFrame]) -> Optional[Dict]:
        '''
        Scan all symbols and return the best opportunity
        
        market_data: Dict of symbol -> DataFrame with OHLCV data
        
        Returns:
        {
            'symbol': 'AAPL',
            'direction': 'BUY' or 'SELL',
            'score': 85.5,
            'entry_price': 150.25,
            'indicators': {...}
        }
        '''
        opportunities = []
        
        for symbol, df in market_data.items():
            try:
                # Get symbol-specific parameters
                params = self.get_symbol_params(symbol)
                
                # Calculate indicators
                df_with_indicators = AIMnIndicators.calculate_all_indicators(df, params)
                
                # Check buy conditions
                buy_signal, buy_score = self.check_buy_conditions(df_with_indicators, params)
                if buy_signal:
                    opportunities.append({
                        'symbol': symbol,
                        'direction': 'BUY',
                        'score': buy_score,
                        'entry_price': df_with_indicators['close'].iloc[-1],
                        'indicators': {
                            'rsi_real': df_with_indicators['rsi_real'].iloc[-1],
                            'macd': df_with_indicators['macd'].iloc[-1],
                            'volume_ratio': df_with_indicators['volume'].iloc[-1] / df_with_indicators['volume'].rolling(20).mean().iloc[-1],
                            'atr_ratio': df_with_indicators['atr'].iloc[-1] / df_with_indicators['atr_ma'].iloc[-1]
                        }
                    })
                
                # Check sell conditions - TEMPORARILY DISABLED
                # Only check sells if we actually own this crypto
                sell_signal = False  # DISABLED until we own crypto
                sell_score = 0
                if False and sell_signal:  # This block won't run
                    opportunities.append({
                        'symbol': symbol,
                        'direction': 'SELL',
                        'score': sell_score,
                        'entry_price': df_with_indicators['close'].iloc[-1],
                        'indicators': {
                            'rsi_real': df_with_indicators['rsi_real'].iloc[-1],
                            'macd': df_with_indicators['macd'].iloc[-1],
                            'volume_ratio': df_with_indicators['volume'].iloc[-1] / df_with_indicators['volume'].rolling(20).mean().iloc[-1],
                            'atr_ratio': df_with_indicators['atr'].iloc[-1] / df_with_indicators['atr_ma'].iloc[-1]
                        }
                    })
                    
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                continue
        
        # Return highest scoring opportunity
        if opportunities:
            best_opportunity = max(opportunities, key=lambda x: x['score'])
            logger.info(f"Best opportunity: {best_opportunity['symbol']} {best_opportunity['direction']} (score: {best_opportunity['score']:.1f})")
            return best_opportunity
        
        return None
