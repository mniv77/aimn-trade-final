# indicators.py
'''
AIMn Trading System - Technical Indicators
All indicators match the Pine Script logic exactly
'''
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    print("Warning: TA-Lib not installed. Using fallback calculations.")
    TALIB_AVAILABLE = False

class AIMnIndicators:

    @staticmethod
    def calculate_rsi_real(df: pd.DataFrame, window: int = 100) -> pd.Series:
        highest_high = df['high'].rolling(window=window).max()
        lowest_low   = df['low'].rolling(window=window).min()
        price_range  = (highest_high - lowest_low).replace(0, 1)
        return ((df['close'] - lowest_low) / price_range * 100).clip(0, 100)

    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        if TALIB_AVAILABLE:
            macd, macd_signal, macd_hist = talib.MACD(df['close'], fastperiod=fast, slowperiod=slow, signalperiod=signal)
        else:
            exp1 = df['close'].ewm(span=fast, adjust=False).mean()
            exp2 = df['close'].ewm(span=slow, adjust=False).mean()
            macd = exp1 - exp2
            macd_signal = macd.ewm(span=signal, adjust=False).mean()
            macd_hist   = macd - macd_signal
        macd_prev    = macd.shift(1)
        signal_prev  = macd_signal.shift(1)
        return {
            'macd'         : macd,
            'signal'       : macd_signal,
            'histogram'    : macd_hist,
            'bullish_cross': (macd_prev <= signal_prev) & (macd > macd_signal),
            'bearish_cross': (macd_prev >= signal_prev) & (macd < macd_signal),
        }

    @staticmethod
    def check_entry_conditions(data, symbol, rsi_config, macd_config, volume_config, atr_config):
        return False

    @staticmethod
    def calculate_volume_signals(df: pd.DataFrame, obv_period: int = 20) -> Dict[str, pd.Series]:
        if TALIB_AVAILABLE:
            obv = talib.OBV(df['close'], df['volume'])
        else:
            obv = (df['volume'] * (~df['close'].diff().le(0) * 2 - 1)).cumsum()
        obv_sma      = obv.rolling(window=obv_period).mean()
        volume_sma   = df['volume'].rolling(window=20).mean()
        high_volume  = df['volume'] > volume_sma
        price_up     = df['close'] > df['close'].shift(1)
        price_down   = df['close'] < df['close'].shift(1)
        return {
            'obv'           : obv,
            'obv_sma'       : obv_sma,
            'high_volume'   : high_volume,
            'bullish_volume': high_volume & price_up   & (obv > obv_sma),
            'bearish_volume': high_volume & price_down & (obv < obv_sma),
        }

    @staticmethod
    def calculate_atr_filter(df: pd.DataFrame, atr_period: int = 14, atr_ma_period: int = 28, multiplier: float = 1.3) -> Dict[str, pd.Series]:
        if TALIB_AVAILABLE:
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=atr_period)
        else:
            hl  = df['high'] - df['low']
            hc  = np.abs(df['high'] - df['close'].shift())
            lc  = np.abs(df['low']  - df['close'].shift())
            atr = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(window=atr_period).mean()
        atr_ma = atr.rolling(window=atr_ma_period).mean()
        return {
            'atr'                : atr,
            'atr_ma'             : atr_ma,
            'volatility_expanding': atr > (atr_ma * multiplier),
            'atr_ratio'          : atr / atr_ma,
        }

    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        df   = df.copy()
        df['rsi_real'] = AIMnIndicators.calculate_rsi_real(df, params.get('rsi_window', 100))
        macd = AIMnIndicators.calculate_macd(df, params.get('macd_fast', 12), params.get('macd_slow', 26), params.get('macd_signal', 9))
        df['macd']            = macd['macd']
        df['macd_signal']     = macd['signal']
        df['macd_histogram']  = macd['histogram']
        df['macd_bullish_cross'] = macd['bullish_cross']
        df['macd_bearish_cross'] = macd['bearish_cross']
        vol = AIMnIndicators.calculate_volume_signals(df, params.get('obv_period', 20))
        df['obv']             = vol['obv']
        df['obv_sma']         = vol['obv_sma']
        df['bullish_volume']  = vol['bullish_volume']
        df['bearish_volume']  = vol['bearish_volume']
        atr = AIMnIndicators.calculate_atr_filter(df, params.get('atr_period', 14), params.get('atr_ma_period', 28), params.get('atr_multiplier', 1.3))
        df['atr']                  = atr['atr']
        df['atr_ma']               = atr['atr_ma']
        df['volatility_expanding'] = atr['volatility_expanding']
        return df

def analyze_market(data, strategy):
    return strategy(data)