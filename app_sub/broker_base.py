from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BrokerBase(ABC):
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        self.extra_params = kwargs

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def get_account(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def list_symbols(self) -> List[str]:
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def place_order(self, symbol: str, qty: float, side: str, order_type: str = "market") -> Any:
        pass

    @abstractmethod
    def close_position(self, symbol: str) -> Any:
        pass

    @abstractmethod
    def close_all_positions(self) -> Any:
        pass

    def is_connected(self) -> bool:
        return hasattr(self, "_connected") and self._connected is True