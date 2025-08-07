# CLAUDE_CONTEXT.md - AI Assistant Context File

## Project Overview
**Repository**: https://github.com/mniv77/aimn-trade-final
**Description**: AI-powered automated crypto trading bot using RSI, MACD, volume filters, and trailing stop logic. Built in Python and integrated with Alpaca API.

**Last Updated**: [DATE - Update this each time]

## Project Architecture
### Core Components
- **Trading Platform**: Alpaca API for crypto trading
- **Programming Language**: Python
- **Technical Indicators**: 
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
  - Volume filters
- **Risk Management**: Trailing stop logic
- **AI Components**: [To be detailed]

### Key Files and Modules
```
[List your main files here, e.g.:]
- main.py - Main trading bot entry point
- strategies/rsi_macd_strategy.py - Trading strategy implementation
- risk_management/trailing_stop.py - Trailing stop implementation
- config/alpaca_config.py - API configuration
- [Add more as needed]
```

## Current Development Status
### Working Features
- [List what's currently working]

### In Progress
- [List what you're currently working on]

### Known Issues
- [List any bugs or problems]

### TODO/Future Enhancements
- [List planned features]

## Technical Details
### API Keys and Configuration
- Alpaca API (Paper/Live trading)
- Required environment variables:
  ```
  ALPACA_API_KEY=
  ALPACA_SECRET_KEY=
  ALPACA_BASE_URL=
  ```

### Trading Parameters
- **Timeframe**: [e.g., 1min, 5min, 1hour]
- **Trading Pairs**: [e.g., BTC/USD, ETH/USD]
- **Position Sizing**: [e.g., fixed amount, percentage of portfolio]
- **Risk Parameters**:
  - Max position size: 
  - Stop loss percentage:
  - Trailing stop percentage:

### Strategy Logic
#### Entry Conditions
- RSI: [e.g., Buy when RSI < 30]
- MACD: [e.g., Buy when MACD crosses above signal line]
- Volume: [e.g., Volume must be above 20-period average]

#### Exit Conditions
- Take profit: [e.g., 2% gain]
- Stop loss: [e.g., 1% loss]
- Trailing stop: [e.g., 0.5% trailing]

## Conversation History
### Session 1 - [DATE]
**Topics Discussed**:
- Initial project review
- Identified project as crypto trading bot using Alpaca API
- Uses RSI, MACD, volume filters, and trailing stops

**Next Steps Identified**:
- [Add specific next steps from our conversation]

### Session 2 - [DATE]
[Add future sessions here]

## Code Snippets for Reference
### Example: Main Trading Loop
```python
# Add key code snippets here that would be helpful for context
```

### Example: Strategy Implementation
```python
# Add strategy code snippets
```

## Questions for Next Session
1. [Add questions you want to address next time]
2. 

## Notes for AI Assistant
- This project focuses on automated crypto trading
- Risk management is a priority
- Currently using Alpaca API but may consider other exchanges
- [Add any other important context]

---
*Remember to update this file after each development session!*