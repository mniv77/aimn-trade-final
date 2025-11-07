"""
Flexible stubs so worker imports & calls won't crash.
Replace with real trading logic later.
"""
from typing import Optional, Any
from dataclasses import dataclass

@dataclass
class ExitDecision:
    exit_now: bool = False
    reason: str | None = None

def enter_position(symbol: str, qty: float, price: float, runtime_state: Any=None, params: Any=None, **kwargs) -> Optional[int]:
    print(f"[PM] enter_position symbol={symbol} qty={qty} price={price}", flush=True)
    return None  # e.g., return new Position ID

def evaluate_exit(symbol: str, price: float, runtime_state: Any=None, params: Any=None, **kwargs) -> ExitDecision:
    # Worker calls: evaluate_exit(symbol, last_price, r, params)
    print(f"[PM] evaluate_exit symbol={symbol} price={price}", flush=True)
    return ExitDecision(exit_now=False)

def close_position(symbol: str=None, position: Any=None, price: float=None, **kwargs) -> None:
    pid = getattr(position, "id", None)
    print(f"[PM] close_position symbol={symbol} id={pid} price={price}", flush=True)
    return None
