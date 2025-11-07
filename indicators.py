<<<<<<< HEAD
# indicators.py
'''
AIMn Trading System - Technical Indicators
All indicators match the Pine Script logic exactly
'''

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional

# Note: You'll need to install TA-Lib separately
# For Windows: pip install TA-Lib-0.4.24-cp312-cp312-win_amd64.whl
# Download from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    print("Warning: TA-Lib not installed. Using fallback calculations.")
    TALIB_AVAILABLE = False


class AIMnIndicators:
    '''Calculate all indicators for the AIMn Trading System'''
    
    @staticmethod
    def calculate_rsi_real(df: pd.DataFrame, window: int = 100) -> pd.Series:
        '''
        Calculate RSI Real (Price-Based RSI)
        Formula: (Close - Lowest Low) / (Highest High - Lowest Low) * 100
        
        This is NOT momentum-based like traditional RSI, but position-based
        '''
        highest_high = df['high'].rolling(window=window).max()
        lowest_low = df['low'].rolling(window=window).min()
        
        # Avoid division by zero
        price_range = highest_high - lowest_low
        price_range = price_range.replace(0, 1)
        
        rsi_real = ((df['close'] - lowest_low) / price_range) * 100
        
        return rsi_real
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        '''
        Calculate MACD with crossover detection
        Returns dict with 'macd', 'signal', 'histogram', and 'crossover'
        '''
        if TALIB_AVAILABLE:
            macd, macd_signal, macd_hist = talib.MACD(df['close'], 
                                                       fastperiod=fast, 
                                                       slowperiod=slow, 
                                                       signalperiod=signal)
        else:
            # Fallback calculation
            exp1 = df['close'].ewm(span=fast, adjust=False).mean()
            exp2 = df['close'].ewm(span=slow, adjust=False).mean()
            macd = exp1 - exp2
            macd_signal = macd.ewm(span=signal, adjust=False).mean()
            macd_hist = macd - macd_signal
        
        # Detect crossovers
        macd_prev = macd.shift(1)
        signal_prev = macd_signal.shift(1)
        
        bullish_cross = (macd_prev <= signal_prev) & (macd > macd_signal)
        bearish_cross = (macd_prev >= signal_prev) & (macd < macd_signal)
        
        return {
            'macd': macd,
            'signal': macd_signal,
            'histogram': macd_hist,
            'bullish_cross': bullish_cross,
            'bearish_cross': bearish_cross
        }

    @staticmethod
    def check_entry_conditions(data, symbol, rsi_config, macd_config, volume_config, atr_config):
        # Dummy logic - replace this with real indicator logic later
        return False

    
    @staticmethod
    def check_entry_conditions(data, symbol, rsi_config, macd_config, volume_config, atr_config):
        # Temporary logic to prevent errors – you can improve later
        return False


    
    @staticmethod
    def calculate_volume_signals(df: pd.DataFrame, obv_period: int = 20) -> Dict[str, pd.Series]:
        '''
        Calculate volume confirmations with OBV
        Returns signals for high volume on moves with OBV trend
        '''
        # On Balance Volume
        if TALIB_AVAILABLE:
            obv = talib.OBV(df['close'], df['volume'])
        else:
            # Fallback OBV calculation
            obv = (df['volume'] * (~df['close'].diff().le(0) * 2 - 1)).cumsum()
        
        obv_sma = obv.rolling(window=obv_period).mean()
        
        # Volume analysis
        volume_sma = df['volume'].rolling(window=20).mean()
        high_volume = df['volume'] > volume_sma
        
        # Price movement
        price_up = df['close'] > df['close'].shift(1)
        price_down = df['close'] < df['close'].shift(1)
        
        # OBV trend
        obv_trending_up = obv > obv_sma
        obv_trending_down = obv < obv_sma
        
        # Combined signals
        bullish_volume = high_volume & price_up & obv_trending_up
        bearish_volume = high_volume & price_down & obv_trending_down
        
        return {
            'obv': obv,
            'obv_sma': obv_sma,
            'high_volume': high_volume,
            'bullish_volume': bullish_volume,
            'bearish_volume': bearish_volume
        }
    
    @staticmethod
    def calculate_atr_filter(df: pd.DataFrame, atr_period: int = 14, 
                           atr_ma_period: int = 28, multiplier: float = 1.3) -> Dict[str, pd.Series]:
        '''
        Calculate ATR volatility filter
        Only trade when ATR > MA(ATR) * multiplier
        '''
        if TALIB_AVAILABLE:
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=atr_period)
        else:
            # Fallback ATR calculation
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(window=atr_period).mean()
        
        atr_ma = atr.rolling(window=atr_ma_period).mean()
        
        # Volatility expanding = good for trading
        volatility_expanding = atr > (atr_ma * multiplier)
        
        return {
            'atr': atr,
            'atr_ma': atr_ma,
            'volatility_expanding': volatility_expanding,
            'atr_ratio': atr / atr_ma
        }
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        '''
        Calculate all indicators and add to dataframe
        '''
        df = df.copy()
        
        # RSI Real
        df['rsi_real'] = AIMnIndicators.calculate_rsi_real(df, params.get('rsi_window', 100))
        
        # MACD
        macd_data = AIMnIndicators.calculate_macd(df, 
                                                  params.get('macd_fast', 12),
                                                  params.get('macd_slow', 26),
                                                  params.get('macd_signal', 9))
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['signal']
        df['macd_histogram'] = macd_data['histogram']
        df['macd_bullish_cross'] = macd_data['bullish_cross']
        df['macd_bearish_cross'] = macd_data['bearish_cross']
        
        # Volume
        volume_data = AIMnIndicators.calculate_volume_signals(df, params.get('obv_period', 20))
        df['obv'] = volume_data['obv']
        df['obv_sma'] = volume_data['obv_sma']
        df['bullish_volume'] = volume_data['bullish_volume']
        df['bearish_volume'] = volume_data['bearish_volume']
        
        # ATR Filter
        atr_data = AIMnIndicators.calculate_atr_filter(df,
                                                       params.get('atr_period', 14),
                                                       params.get('atr_ma_period', 28),
                                                       params.get('atr_multiplier', 1.3))
        df['atr'] = atr_data['atr']
        df['atr_ma'] = atr_data['atr_ma']
        df['volatility_expanding'] = atr_data['volatility_expanding']
        
        return df

=======
# indicators.py
'''
AIMn Trading System - Technical Indicators
All indicators match the Pine Script logic exactly
'''

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional

# Note: You'll need to install TA-Lib separately
# For Windows: pip install TA-Lib-0.4.24-cp312-cp312-win_amd64.whl
# Download from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    print("Warning: TA-Lib not installed. Using fallback calculations.")
    TALIB_AVAILABLE = False


class AIMnIndicators:
    '''Calculate all indicators for the AIMn Trading System'''
    
    @staticmethod
    def calculate_rsi_real(df: pd.DataFrame, window: int = 100) -> pd.Series:
        '''
        Calculate RSI Real (Price-Based RSI)
        Formula: (Close - Lowest Low) / (Highest High - Lowest Low) * 100
        
        This is NOT momentum-based like traditional RSI, but position-based
        '''
        highest_high = df['high'].rolling(window=window).max()
        lowest_low = df['low'].rolling(window=window).min()
        
        # Avoid division by zero
        price_range = highest_high - lowest_low
        price_range = price_range.replace(0, 1)
        
        rsi_real = ((df['close'] - lowest_low) / price_range) * 100
        
        return rsi_real
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        '''
        Calculate MACD with crossover detection
        Returns dict with 'macd', 'signal', 'histogram', and 'crossover'
        '''
        if TALIB_AVAILABLE:
            macd, macd_signal, macd_hist = talib.MACD(df['close'], 
                                                       fastperiod=fast, 
                                                       slowperiod=slow, 
                                                       signalperiod=signal)
        else:
            # Fallback calculation
            exp1 = df['close'].ewm(span=fast, adjust=False).mean()
            exp2 = df['close'].ewm(span=slow, adjust=False).mean()
            macd = exp1 - exp2
            macd_signal = macd.ewm(span=signal, adjust=False).mean()
            macd_hist = macd - macd_signal
        
        # Detect crossovers
        macd_prev = macd.shift(1)
        signal_prev = macd_signal.shift(1)
        
        bullish_cross = (macd_prev <= signal_prev) & (macd > macd_signal)
        bearish_cross = (macd_prev >= signal_prev) & (macd < macd_signal)
        
        return {
            'macd': macd,
            'signal': macd_signal,
            'histogram': macd_hist,
            'bullish_cross': bullish_cross,
            'bearish_cross': bearish_cross
        }
    @staticmethod
    def check_entry_conditions(data, symbol, rsi_config, macd_config, volume_config, atr_config):
        # Dummy logic - replace this with real indicator logic later
        return False
    
    @staticmethod
    def calculate_volume_signals(df: pd.DataFrame, obv_period: int = 20) -> Dict[str, pd.Series]:
        '''
        Calculate volume confirmations with OBV
        Returns signals for high volume on moves with OBV trend
        '''
        # On Balance Volume
        if TALIB_AVAILABLE:
            obv = talib.OBV(df['close'], df['volume'])
        else:
            # Fallback OBV calculation
            obv = (df['volume'] * (~df['close'].diff().le(0) * 2 - 1)).cumsum()
        
        obv_sma = obv.rolling(window=obv_period).mean()
        
        # Volume analysis
        volume_sma = df['volume'].rolling(window=20).mean()
        high_volume = df['volume'] > volume_sma
        
        # Price movement
        price_up = df['close'] > df['close'].shift(1)
        price_down = df['close'] < df['close'].shift(1)
        
        # OBV trend
        obv_trending_up = obv > obv_sma
        obv_trending_down = obv < obv_sma
        
        # Combined signals
        bullish_volume = high_volume & price_up & obv_trending_up
        bearish_volume = high_volume & price_down & obv_trending_down
        
        return {
            'obv': obv,
            'obv_sma': obv_sma,
            'high_volume': high_volume,
            'bullish_volume': bullish_volume,
            'bearish_volume': bearish_volume
        }
    
    @staticmethod
    def calculate_atr_filter(df: pd.DataFrame, atr_period: int = 14, 
                           atr_ma_period: int = 28, multiplier: float = 1.3) -> Dict[str, pd.Series]:
        '''
        Calculate ATR volatility filter
        Only trade when ATR > MA(ATR) * multiplier
        '''
        if TALIB_AVAILABLE:
            atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=atr_period)
        else:
            # Fallback ATR calculation
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(window=atr_period).mean()
        
        atr_ma = atr.rolling(window=atr_ma_period).mean()
        
        # Volatility expanding = good for trading
        volatility_expanding = atr > (atr_ma * multiplier)
        
        return {
            'atr': atr,
            'atr_ma': atr_ma,
            'volatility_expanding': volatility_expanding,
            'atr_ratio': atr / atr_ma
        }
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
        '''
        Calculate all indicators and add to dataframe
        '''
        df = df.copy()
        
        # RSI Real
        df['rsi_real'] = AIMnIndicators.calculate_rsi_real(df, params.get('rsi_window', 100))
        
        # MACD
        macd_data = AIMnIndicators.calculate_macd(df, 
                                                  params.get('macd_fast', 12),
                                                  params.get('macd_slow', 26),
                                                  params.get('macd_signal', 9))
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['signal']
        df['macd_histogram'] = macd_data['histogram']
        df['macd_bullish_cross'] = macd_data['bullish_cross']
        df['macd_bearish_cross'] = macd_data['bearish_cross']
        
        # Volume
        volume_data = AIMnIndicators.calculate_volume_signals(df, params.get('obv_period', 20))
        df['obv'] = volume_data['obv']
        df['obv_sma'] = volume_data['obv_sma']
        df['bullish_volume'] = volume_data['bullish_volume']
        df['bearish_volume'] = volume_data['bearish_volume']
        
        # ATR Filter
        atr_data = AIMnIndicators.calculate_atr_filter(df,
                                                       params.get('atr_period', 14),
                                                       params.get('atr_ma_period', 28),
                                                       params.get('atr_multiplier', 1.3))
        df['atr'] = atr_data['atr']
        df['atr_ma'] = atr_data['atr_ma']
        df['volatility_expanding'] = atr_data['volatility_expanding']
        
        return df


def analyze_market(data, strategy):
    return strategy(data)
>>>>>>> 0c0df91 (Initial push)
