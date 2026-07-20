# scanner.py
"""
AIMn Trading System - Multi-Symbol Scanner
Scans all symbols and finds the best trading opportunity
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
from indicators import AIMnIndicators

logger = logging.getLogger(__name__)


class AIMnScanner:
    """Scanner to find the best trading opportunity across multiple symbols"""

    def __init__(self, symbol_params: Dict[str, Dict]):
        self.symbol_params = symbol_params
        self.default_params = {
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'volume_threshold': 1.2,
            'atr_period': 14,
            'atr_ma_period': 28,
            'atr_multiplier': 1.3,
            'obv_period': 20,
        }

    def get_symbol_params(self, symbol: str) -> Dict:
        params = self.default_params.copy()
        if symbol in self.symbol_params:
            params.update(self.symbol_params[symbol])
        # Try without slash (BTC/USD -> BTCUSD)
        symbol_no_slash = symbol.replace('/', '')
        if symbol_no_slash in self.symbol_params:
            params.update(self.symbol_params[symbol_no_slash])
        return params

    def calculate_opportunity_score(self, df: pd.DataFrame, params: Dict, direction: str) -> float:
        """Score 0-100: higher = better opportunity"""
        if len(df) < 2:
            return 0.0
        latest = df.iloc[-1]
        score = 0.0

        # RSI component (0-25 points)
        rsi = latest.get('rsi_real', 50)
        if direction == 'BUY':
            if rsi <= params['rsi_oversold']:
                score += (params['rsi_oversold'] - rsi) / params['rsi_oversold'] * 25
        else:
            if rsi >= params['rsi_overbought']:
                score += (rsi - params['rsi_overbought']) / (100 - params['rsi_overbought']) * 25

        # MACD histogram component (0-25 points)
        hist = latest.get('macd_histogram', 0)
        score += min(abs(hist) * 10, 25)

        # Volume component (0-25 points)
        vol_mean = df['volume'].rolling(20).mean().iloc[-1]
        volume_ratio = latest['volume'] / vol_mean if vol_mean else 1
        score += min((volume_ratio - 1) * 10, 25)

        # ATR component (0-25 points)
        atr_ma = latest.get('atr_ma', None)
        atr = latest.get('atr', None)
        if atr and atr_ma and atr_ma > 0:
            atr_ratio = atr / atr_ma
            score += min((atr_ratio - params['atr_multiplier']) * 10, 25)

        return max(0.0, min(100.0, score))

    def scan_symbol(self, symbol: str, df: pd.DataFrame) -> Optional[Dict]:
        """Scan a single symbol; returns opportunity dict or None"""
        if df is None or len(df) < 50:
            logger.debug(f"Insufficient data for {symbol}")
            return None

        params = self.get_symbol_params(symbol)
        df_ind = AIMnIndicators.calculate_all_indicators(df, params)
        conditions = AIMnIndicators.check_entry_conditions(df_ind, params)
        latest = df_ind.iloc[-1]

        for direction, cond_key in [('BUY', 'buy'), ('SELL', 'sell')]:
            if conditions.get(cond_key):
                score = self.calculate_opportunity_score(df_ind, params, direction)
                return {
                    'symbol': symbol,
                    'direction': direction,
                    'entry_price': latest['close'],
                    'score': score,
                    'indicators': {
                        'rsi_real': latest.get('rsi_real'),
                        'macd': latest.get('macd'),
                        'signal': latest.get('signal'),
                        'volume_ratio': latest['volume'] / df_ind['volume'].rolling(20).mean().iloc[-1],
                        'atr_ratio': (latest.get('atr', 0) / latest.get('atr_ma', 1)) if latest.get('atr_ma') else None,
                    },
                    'conditions': conditions
                }
        return None

    def scan_all_symbols(self, market_data: Dict[str, pd.DataFrame]) -> Optional[Dict]:
        """Scan all symbols; return highest-scoring opportunity or None"""
        opportunities = []
        for symbol, df in market_data.items():
            try:
                opp = self.scan_symbol(symbol, df)
                if opp:
                    opportunities.append(opp)
                    logger.debug(f"Opportunity: {symbol} {opp['direction']} score={opp['score']:.1f}")
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")

        if opportunities:
            best = max(opportunities, key=lambda x: x['score'])
            logger.info(f"Best: {best['symbol']} {best['direction']} score={best['score']:.1f}")
            return best
        return None

    def get_signal_summary(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, Dict]:
        """Summary of all symbols for dashboard/monitoring"""
        summary = {}
        for symbol, df in market_data.items():
            if df is None or len(df) < 50:
                summary[symbol] = {'status': 'insufficient_data'}
                continue
            try:
                params = self.get_symbol_params(symbol)
                df_ind = AIMnIndicators.calculate_all_indicators(df, params)
                latest = df_ind.iloc[-1]
                conditions = AIMnIndicators.check_entry_conditions(df_ind, params)
                vol_mean = df_ind['volume'].rolling(20).mean().iloc[-1]

                missing_buy, missing_sell = [], []
                if not conditions.get('rsi_buy'):   missing_buy.append('RSI')
                if not conditions.get('macd_buy'):  missing_buy.append('MACD')
                if not conditions.get('volume_buy'): missing_buy.append('Volume')
                if not conditions.get('rsi_sell'):  missing_sell.append('RSI')
                if not conditions.get('macd_sell'): missing_sell.append('MACD')
                if not conditions.get('volume_sell'): missing_sell.append('Volume')

                summary[symbol] = {
                    'status': 'ready',
                    'price': latest['close'],
                    'rsi': latest.get('rsi_real'),
                    'volume_ratio': latest['volume'] / vol_mean if vol_mean else None,
                    'buy_ready': conditions.get('buy', False),
                    'sell_ready': conditions.get('sell', False),
                    'missing_buy': missing_buy,
                    'missing_sell': missing_sell,
                }
            except Exception as e:
                summary[symbol] = {'status': 'error', 'error': str(e)}
        return summary