
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
        self.symbol_params = symbol_params
        self.default_params = {
            'rsi_window': 100,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'volume_threshold': 1.0,
            'atr_period': 14,
            'atr_ma_period': 28,
            'atr_multiplier': 1.3,
            'obv_period': 20
        }

    def get_symbol_params(self, symbol: str) -> Dict:
        params = self.default_params.copy()
        # Try exact match first
        if symbol in self.symbol_params:
            params.update(self.symbol_params[symbol])
        # Try without slash for crypto (BTC/USD -> BTCUSD)
        symbol_no_slash = symbol.replace('/', '')
        if symbol_no_slash in self.symbol_params:
            params.update(self.symbol_params[symbol_no_slash])
        return params

    def check_buy_conditions(self, df: pd.DataFrame, params: Dict) -> Tuple[bool, float]:
        if len(df) < 100:
            return False, 0.0

        latest = df.iloc[-1]

        rsi_oversold = latest['rsi_real'] <= params['rsi_oversold']
        macd_bullish = latest['macd_bullish_cross']
        volume_ok = latest['bullish_volume']
        atr_ok = latest['volatility_expanding']

        signal = rsi_oversold and macd_bullish and volume_ok and atr_ok

        score = 0.0
        if signal:
            rsi_score = (params['rsi_oversold'] - latest['rsi_real']) / params['rsi_oversold'] * 25
            macd_score = min(abs(latest['macd_histogram']) * 10, 25)
            volume_ratio = latest['volume'] / df['volume'].rolling(20).mean().iloc[-1]
            volume_score = min((volume_ratio - 1) * 10, 25)
            atr_ratio = latest['atr'] / latest['atr_ma']
            atr_score = min((atr_ratio - params['atr_multiplier']) * 10, 25)

            score = rsi_score + macd_score + volume_score + atr_score
            score = max(0, min(100, score))

        return signal, score

    def check_sell_conditions(self, df: pd.DataFrame, params: Dict) -> Tuple[bool, float]:
        if len(df) < 100:
            return False, 0.0

        latest = df.iloc[-1]

        rsi_overbought = latest['rsi_real'] >= params['rsi_overbought']
        macd_bearish = latest['macd_bearish_cross']
        volume_ok = latest['bearish_volume']
        atr_ok = latest['volatility_expanding']

        signal = rsi_overbought and macd_bearish and volume_ok and atr_ok

        score = 0.0
        if signal:
            rsi_score = (latest['rsi_real'] - params['rsi_overbought']) / (100 - params['rsi_overbought']) * 25
            macd_score = min(abs(latest['macd_histogram']) * 10, 25)
            volume_ratio = latest['volume'] / df['volume'].rolling(20).mean().iloc[-1]
            volume_score = min((volume_ratio - 1) * 10, 25)
            atr_ratio = latest['atr'] / latest['atr_ma']
            atr_score = min((atr_ratio - params['atr_multiplier']) * 10, 25)

            score = rsi_score + macd_score + volume_score + atr_score
            score = max(0, min(100, score))

        return signal, score

    def scan_all_symbols(self, market_data: Dict[str, pd.DataFrame]) -> Optional[Dict]:
        opportunities = []

        for symbol, df in market_data.items():
            try:
                params = self.get_symbol_params(symbol)
                df_with_indicators = AIMnIndicators.calculate_all_indicators(df, params)

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

                sell_signal, sell_score = self.check_sell_conditions(df_with_indicators, params)
                if sell_signal:
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

        if opportunities:
            best_opportunity = max(opportunities, key=lambda x: x['score'])
            logger.info(f"Best opportunity: {best_opportunity['symbol']} {best_opportunity['direction']} (score: {best_opportunity['score']:.1f})")
            return best_opportunity

        return None

    def get_signal_summary(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """Get a summary of signals for all symbols (for dashboard/monitoring)."""
        summary = {}
        for symbol, df in market_data.items():
            if df is None or len(df) < 50:
                summary[symbol] = {'status': 'insufficient_data'}
                continue
            try:
                params = self.get_symbol_params(symbol)
                df_ind = AIMnIndicators.calculate_all_indicators(df, params)
                latest = df_ind.iloc[-1]
                buy_signal, buy_score = self.check_buy_conditions(df_ind, params)
                sell_signal, sell_score = self.check_sell_conditions(df_ind, params)
                summary[symbol] = {
                    'status': 'ready',
                    'price': latest['close'],
                    'rsi': latest.get('rsi_real', 50),
                    'buy_ready': buy_signal,
                    'sell_ready': sell_signal,
                    'buy_score': round(buy_score, 1),
                    'sell_score': round(sell_score, 1),
                }
            except Exception as e:
                summary[symbol] = {'status': 'error', 'error': str(e)}
        return summary
