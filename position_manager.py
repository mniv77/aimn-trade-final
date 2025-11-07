# position_manager.py
'''
AIMn Trading System - Position Manager
Handles entry, dual trailing exits, and position tracking
'''

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ExitCode(Enum):
    '''Exit codes for tracking how positions were closed'''
    STOP_LOSS = "S"
    EARLY_TRAIL = "E"
    PEAK_TRAIL = "P"
    RSI_EXIT = "R"


class Position:
    '''Represents an active trading position'''
    
    def __init__(self, symbol: str, direction: str, entry_price: float, 
                 shares: int, entry_time: datetime, params: Dict):
        self.symbol = symbol
        self.direction = direction  # 'BUY' or 'SELL'
        self.entry_price = entry_price
        self.shares = shares
        self.entry_time = entry_time
        self.params = params
        
        # Tracking variables
        self.highest_price = entry_price if direction == 'BUY' else None
        self.lowest_price = entry_price if direction == 'SELL' else None
        self.current_price = entry_price
        self.unrealized_pnl = 0.0
        self.unrealized_pnl_pct = 0.0
        
        # Exit levels
        self.stop_loss_price = self._calculate_stop_loss()
        self.early_trail_active = False
        self.early_trail_price = None
        self.peak_trail_active = False
        self.peak_trail_price = None
    
    def _calculate_stop_loss(self) -> float:
        '''Calculate initial stop loss price'''
        stop_loss_pct = self.params.get('stop_loss_percent', 2.0)
        
        if self.direction == 'BUY':
            return self.entry_price * (1 - stop_loss_pct / 100)
        else:  # SELL
            return self.entry_price * (1 + stop_loss_pct / 100)
    
    def update_price(self, current_price: float) -> Optional[Tuple[ExitCode, float]]:
        '''
        Update position with current price and check exit conditions
        Returns (ExitCode, exit_price) if exit triggered, None otherwise
        '''
        self.current_price = current_price
        
        # Update P&L
        if self.direction == 'BUY':
            self.unrealized_pnl = (current_price - self.entry_price) * self.shares
            self.unrealized_pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            
            # Update highest price
            if self.highest_price is None or current_price > self.highest_price:
                self.highest_price = current_price
        else:  # SELL
            self.unrealized_pnl = (self.entry_price - current_price) * self.shares
            self.unrealized_pnl_pct = ((self.entry_price - current_price) / self.entry_price) * 100
            
            # Update lowest price
            if self.lowest_price is None or current_price < self.lowest_price:
                self.lowest_price = current_price
        
        # Check exit conditions in order of priority
        
        # 1. Stop Loss
        if self._check_stop_loss():
            return ExitCode.STOP_LOSS, current_price
        
        # 2. Peak Trailing (tight)
        if self._check_peak_trailing():
            return ExitCode.PEAK_TRAIL, current_price
        
        # 3. Early Trailing (loose)
        if self._check_early_trailing():
            return ExitCode.EARLY_TRAIL, current_price
        
        return None
    
    def _check_stop_loss(self) -> bool:
        '''Check if stop loss is hit'''
        if self.direction == 'BUY':
            return self.current_price <= self.stop_loss_price
        else:  # SELL
            return self.current_price >= self.stop_loss_price
    
    def _check_early_trailing(self) -> bool:
        '''Check early trailing stop (loose)'''
        early_start = self.params.get('early_trail_start', 1.0)
        early_minus = self.params.get('early_trail_minus', 15.0)
        
        # Activate early trailing if profit threshold reached
        if self.unrealized_pnl_pct >= early_start and not self.early_trail_active:
            self.early_trail_active = True
            logger.info(f"Early trailing activated for {self.symbol} at {self.unrealized_pnl_pct:.2f}% profit")
        
        # Update and check trailing stop
        if self.early_trail_active:
            if self.direction == 'BUY':
                # Trail from highest price
                self.early_trail_price = self.highest_price * (1 - early_minus / 100)
                return self.current_price <= self.early_trail_price
            else:  # SELL
                # Trail from lowest price
                self.early_trail_price = self.lowest_price * (1 + early_minus / 100)
                return self.current_price >= self.early_trail_price
        
        return False
    
    def _check_peak_trailing(self) -> bool:
        '''Check peak trailing stop (tight)'''
        peak_start = self.params.get('peak_trail_start', 5.0)
        peak_minus = self.params.get('peak_trail_minus', 0.5)
        
        # Activate peak trailing if profit threshold reached
        if self.unrealized_pnl_pct >= peak_start and not self.peak_trail_active:
            self.peak_trail_active = True
            logger.info(f"Peak trailing activated for {self.symbol} at {self.unrealized_pnl_pct:.2f}% profit")
        
        # Update and check trailing stop
        if self.peak_trail_active:
            if self.direction == 'BUY':
                # Trail from highest price
                self.peak_trail_price = self.highest_price * (1 - peak_minus / 100)
                return self.current_price <= self.peak_trail_price
            else:  # SELL
                # Trail from lowest price
                self.peak_trail_price = self.lowest_price * (1 + peak_minus / 100)
                return self.current_price >= self.peak_trail_price
        
        return False
    
    def check_rsi_exit(self, current_rsi: float, params: Dict) -> bool:
        '''
        Check RSI exit condition (optional)
        Exit when RSI reverses with minimum profit
        '''
        if not params.get('use_rsi_exit', True):
            return False
        
        min_profit = params.get('rsi_exit_min_profit', 0.5)
        
        if self.unrealized_pnl_pct < min_profit:
            return False
        
        if self.direction == 'BUY':
            # Exit long if RSI becomes overbought
            return current_rsi >= params.get('rsi_overbought', 70)
        else:  # SELL
            # Exit short if RSI becomes oversold
            return current_rsi <= params.get('rsi_oversold', 30)


class AIMnPositionManager:
    '''Manages all positions and executions'''
    
    def __init__(self, max_positions: int = 1):
        self.positions: Dict[str, Position] = {}
        self.max_positions = max_positions
        self.trade_history = []
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
    
    def has_position(self, symbol: str = None) -> bool:
        '''Check if we have any position or specific symbol position'''
        if symbol:
            return symbol in self.positions
        return len(self.positions) > 0
    
    def can_enter_position(self) -> bool:
        '''Check if we can enter a new position'''
        return len(self.positions) < self.max_positions
    
    def enter_position(self, opportunity: Dict, shares: int, params: Dict) -> Position:
        '''Enter a new position based on scanner opportunity'''
        position = Position(
            symbol=opportunity['symbol'],
            direction=opportunity['direction'],
            entry_price=opportunity['entry_price'],
            shares=shares,
            entry_time=datetime.now(),
            params=params
        )
        
        self.positions[opportunity['symbol']] = position
        
        logger.info(f"ENTERED {opportunity['direction']} position: {opportunity['symbol']} "
                   f"@ ${opportunity['entry_price']:.2f} x {shares} shares")
        
        return position
    
    def update_position(self, symbol: str, current_price: float, 
                       current_rsi: float = None) -> Optional[Dict]:
        '''
        Update position and check for exits
        Returns exit info if position closed, None otherwise
        '''
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Check price-based exits
        exit_result = position.update_price(current_price)
        
        # Check RSI exit if provided
        if exit_result is None and current_rsi is not None:
            if position.check_rsi_exit(current_rsi, position.params):
                exit_result = (ExitCode.RSI_EXIT, current_price)
        
        # Handle exit if triggered
        if exit_result:
            exit_code, exit_price = exit_result
            
            # Calculate final P&L
            if position.direction == 'BUY':
                pnl = (exit_price - position.entry_price) * position.shares
            else:  # SELL
                pnl = (position.entry_price - exit_price) * position.shares
            
            pnl_pct = (pnl / (position.entry_price * position.shares)) * 100
            
            # Update statistics
            self.total_trades += 1
            self.total_pnl += pnl
            if pnl > 0:
                self.winning_trades += 1
            
            # Record trade
            trade_record = {
                'symbol': position.symbol,
                'direction': position.direction,
                'entry_time': position.entry_time,
                'exit_time': datetime.now(),
                'entry_price': position.entry_price,
                'exit_price': exit_price,
                'shares': position.shares,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'exit_code': exit_code.value,
                'highest_price': position.highest_price,
                'lowest_price': position.lowest_price
            }
            self.trade_history.append(trade_record)
            
            # Remove position
            del self.positions[symbol]
            
            logger.info(f"EXITED {position.direction} position: {symbol} "
                       f"@ ${exit_price:.2f} | P&L: ${pnl:.2f} ({pnl_pct:.2f}%) "
                       f"| Exit: {exit_code.value}")
            
            return trade_record
        
        return None
    
    def get_statistics(self) -> Dict:
        '''Get trading statistics'''
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.total_trades - self.winning_trades,
            'win_rate': win_rate,
            'total_pnl': self.total_pnl,
            'avg_pnl': self.total_pnl / self.total_trades if self.total_trades > 0 else 0,
            'active_positions': len(self.positions)
        }
