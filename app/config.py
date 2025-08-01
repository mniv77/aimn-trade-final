# aimn_crypto_config.py
"""
Configuration for AIMn Crypto Trading System
CORRECTED: Alpaca requires slashes in crypto symbols!
"""

# Trading Mode
PAPER_TRADING = True  # Set to False for live trading

# Crypto Symbols (Alpaca format - WITH slashes!)
SYMBOLS = [
    'BTC/USD',    # Bitcoin (verified available)
    'ETH/USD',    # Ethereum (verified available)
    'LTC/USD',    # Litecoin (verified available)
    'BCH/USD',    # Bitcoin Cash (verified available)
    'LINK/USD',   # Chainlink (verified available)
    'UNI/USD',    # Uniswap (verified available)
    'AAVE/USD'    # Aave (verified available)
]

# Trading Parameters
CAPITAL_PER_TRADE = 0.30  # 30% of capital per trade
SCAN_INTERVAL = 30  # Seconds between scans
TIMEFRAME = '1Min'  # Bar timeframe for crypto

# Risk Management Defaults
DEFAULT_STOP_LOSS = 2.0  # 2% stop loss
DEFAULT_EARLY_TRAIL_START = 1.0  # Start early trail at 1% profit
DEFAULT_EARLY_TRAIL_MINUS = 15.0  # Trail 15% below peak
DEFAULT_PEAK_TRAIL_START = 5.0  # Start peak trail at 5% profit
DEFAULT_PEAK_TRAIL_MINUS = 0.5  # Trail 0.5% below peak

SYMBOL_CONFIGS = {
    'BTC/USD': {
        'rsi_oversold': 45,    # CHANGE THIS TO 35
        'rsi_overbought': 55,  # CHANGE THIS TO 65
        # ... rest of config
    },
    'ETH/USD': {
        'rsi_oversold': 45,    # CHANGE THIS TO 35
        'rsi_overbought': 55,  # CHANGE THIS TO 65
        # ... rest of config
    },
    # Do this for ALL symbols
}


# Symbol-Specific Parameters
SYMBOL_PARAMS = {
    'BTC/USD': {
        'rsi_period': 14,
        'rsi_oversold': 45,
        'rsi_overbought': 55,
        'macd_fast': 5,
        'macd_slow': 13,
        'macd_signal': 5,
        'volume_ma_period': 20,
        'volume_threshold': 0.01,
        'atr_period': 14,
        'atr_threshold': 0.01,
        'stop_loss': 2.0,
        'early_trail_start': 1.0,
        'early_trail_minus': 15.0,
        'peak_trail_start': 5.0,
        'peak_trail_minus': 0.5,
        'use_rsi_exit': True,
        'rsi_exit_threshold': 1.0
    },
    'ETH/USD': {
        'rsi_period': 14,
        'rsi_oversold': 45,
        'rsi_overbought': 55,
        'macd_fast': 5,
        'macd_slow': 13,
        'macd_signal': 5,
        'volume_ma_period': 20,
        'volume_threshold': 0.01,
        'atr_period': 14,
        'atr_threshold': 0.01,
        'stop_loss': 2.5,
        'early_trail_start': 1.0,
        'early_trail_minus': 20.0,
        'peak_trail_start': 5.0,
        'peak_trail_minus': 0.7,
        'use_rsi_exit': True,
        'rsi_exit_threshold': 1.0
    },
    # Default parameters for other symbols
    'DEFAULT': {
        'rsi_period': 14,
        'rsi_oversold': 45,
        'rsi_overbought': 55,
        'macd_fast': 5,
        'macd_slow': 13,
        'macd_signal': 5,
        'volume_ma_period': 20,
        'volume_threshold': 0.01,
        'atr_period': 14,
        'atr_threshold': 0.01,
        'stop_loss': DEFAULT_STOP_LOSS,
        'early_trail_start': DEFAULT_EARLY_TRAIL_START,
        'early_trail_minus': DEFAULT_EARLY_TRAIL_MINUS,
        'peak_trail_start': DEFAULT_PEAK_TRAIL_START,
        'peak_trail_minus': DEFAULT_PEAK_TRAIL_MINUS,
        'use_rsi_exit': True,
        'rsi_exit_threshold': 1.0
    }
}

# Apply default parameters to symbols without specific config
for symbol in SYMBOLS:
    if symbol not in SYMBOL_PARAMS:
        SYMBOL_PARAMS[symbol] = SYMBOL_PARAMS['DEFAULT'].copy()

# Logging Configuration
LOG_LEVEL = 'INFO'
LOG_FILE = 'aimn_crypto_trading.log'

# Performance Tracking
TRACK_PERFORMANCE = True
PERFORMANCE_FILE = 'aimn_crypto_performance.csv'

# Volume Confirmation Settings
VOLUME_CONFIRMATION = True  # Enable volume confirmation
VOLUME_SETTINGS = {
    'min_volume_ratio': 0.5,  # Minimum volume vs average
    'spike_threshold': 2.0,   # Standard deviations for spike detection
    'obv_period': 20,         # OBV moving average period
}

# Entry Scoring Weights
SCORING_WEIGHTS = {
    'rsi': 0.3,      # 30% weight for RSI signal
    'macd': 0.3,     # 30% weight for MACD signal
    'volume': 0.4,   # 40% weight for volume confirmation
}

# Additional Settings
MAX_POSITIONS = 1  # Maximum concurrent positions
MIN_BARS_REQUIRED = 50  # Minimum bars needed for indicator calculation

# Broker Settings
ALPACA_RETRY_ATTEMPTS = 3
ALPACA_RETRY_DELAY = 5  # seconds

print(f"Configuration loaded: {len(SYMBOLS)} crypto symbols (WITH slashes!)")