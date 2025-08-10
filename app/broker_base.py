<<<<<<< HEAD
# filename: app/broker_base.py
"""
AIMn Trading System — Broker Base Interface

Purpose
-------
This defines the common interface that all broker adapters (Alpaca, Gemini, etc.)
must implement. It allows the dashboard/orchestrator to call broker functions
without caring which broker is active.

Every method here should be implemented in each specific broker adapter:
    - broker_alpaca.py
    - broker_gemini.py
    - (future) broker_binance.py, etc.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BrokerBase(ABC):
    """Abstract base class for all broker adapters."""

    def __init__(self, api_key: str, api_secret: str, **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        self.extra_params = kwargs

    # ------------------------------------------------------------------
    # Connection / account
    # ------------------------------------------------------------------
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the broker API."""
        pass

    @abstractmethod
    def get_account(self) -> Dict[str, Any]:
        """Return account info: portfolio value, buying power, etc."""
        pass

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------
    @abstractmethod
    def list_symbols(self) -> List[str]:
        """Return list of tradable symbols for this broker."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Return a list of current open positions."""
        pass

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------
    @abstractmethod
    def place_order(self, symbol: str, qty: float, side: str, order_type: str = "market") -> Any:
        """
        Place an order.
        side: "buy" or "sell"
        order_type: "market", "limit", etc.
        """
        pass

    @abstractmethod
    def close_position(self, symbol: str) -> Any:
        """Close a position for the given symbol."""
        pass

    @abstractmethod
    def close_all_positions(self) -> Any:
        """Close all open positions."""
        pass

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def is_connected(self) -> bool:
        """Return True if broker connection is established."""
        return hasattr(self, "_connected") and self._connected is True

=======
# filename: app/broker_base.py
"""
AIMn Trading System — Broker Base Interface

Purpose
-------
This defines the common interface that all broker adapters (Alpaca, Gemini, etc.)
must implement. It allows the dashboard/orchestrator to call broker functions
without caring which broker is active.

Every method here should be implemented in each specific broker adapter:
    - broker_alpaca.py
    - broker_gemini.py
    - (future) broker_binance.py, etc.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BrokerBase(ABC):
    """Abstract base class for all broker adapters."""

    def __init__(self, api_key: str, api_secret: str, **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        self.extra_params = kwargs

    # ------------------------------------------------------------------
    # Connection / account
    # ------------------------------------------------------------------
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the broker API."""
        pass

    @abstractmethod
    def get_account(self) -> Dict[str, Any]:
        """Return account info: portfolio value, buying power, etc."""
        pass

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------
    @abstractmethod
    def list_symbols(self) -> List[str]:
        """Return list of tradable symbols for this broker."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Return a list of current open positions."""
        pass

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------
    @abstractmethod
    def place_order(self, symbol: str, qty: float, side: str, order_type: str = "market") -> Any:
        """
        Place an order.
        side: "buy" or "sell"
        order_type: "market", "limit", etc.
        """
        pass

    @abstractmethod
    def close_position(self, symbol: str) -> Any:
        """Close a position for the given symbol."""
        pass

    @abstractmethod
    def close_all_positions(self) -> Any:
        """Close all open positions."""
        pass

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def is_connected(self) -> bool:
        """Return True if broker connection is established."""
        return hasattr(self, "_connected") and self._connected is True

>>>>>>> 0c0df91 (Initial push)
