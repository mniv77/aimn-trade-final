# filename: app/orchestrator.py
"""
AIMn Trading System — Orchestrator (background control loop)

Purpose
-------
This module runs the background loop that the Streamlit dashboard controls.
It exposes simple functions the UI can call to:
  • start() / pause() the scanner-executor loop
  • apply_params() for live per-symbol tuning
  • stop_now() for emergency liquidation
  • close_position() for graceful exit
  • status() to report current state back to the UI

Notes
-----
• This is a minimal, safe scaffold that works today. It logs activity and
  simulates scanning. You can wire in your real scanner/position_manager later
  without changing the UI.
• No third-party deps. Uses Python threading and a global singleton Worker.
• Log file path defaults to env AIMN_LOG_FILE or 'aimn_crypto_trading.log'.
"""

from __future__ import annotations

import os
import json
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# ----------------------------------------------------------------------------
# Config & Logging
# ----------------------------------------------------------------------------

LOG_PATH = os.getenv("AIMN_LOG_FILE", "aimn_crypto_trading.log")


def _log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # As a last resort, print
        print(line, end="")


# ----------------------------------------------------------------------------
# Global State
# ----------------------------------------------------------------------------

@dataclass
class OrchestratorState:
    broker: str = "Alpaca"            # or "Gemini"
    paper: bool = True
    live_confirmed: bool = False
    is_running: bool = False
    is_paused: bool = True
    last_tick_ts: float = 0.0
    symbols_enabled: list[str] = field(default_factory=list)
    params_per_symbol: Dict[str, Dict[str, Any]] = field(default_factory=dict)


_state = OrchestratorState()
_worker: Optional["Worker"] = None
_state_lock = threading.Lock()


# ----------------------------------------------------------------------------
# Worker Thread
# ----------------------------------------------------------------------------

class Worker(threading.Thread):
    def __init__(self, state: OrchestratorState, lock: threading.Lock, interval_sec: float = 2.0):
        super().__init__(daemon=True)
        self.state = state
        self.lock = lock
        self.interval_sec = interval_sec
        self.stop_event = threading.Event()

    def run(self) -> None:
        _log("Orchestrator worker started.")
        while not self.stop_event.is_set():
            with self.lock:
                if not self.state.is_running or self.state.is_paused:
                    # idle but alive — sleep briefly
                    pass
                else:
                    # === MAIN LOOP ===
                    self._tick()
            time.sleep(self.interval_sec)
        _log("Orchestrator worker stopped.")

    def _tick(self) -> None:
        # This is where you'll call your real scanner & executor
        # For now we simulate and log
        self.state.last_tick_ts = time.time()
        enabled = self.state.symbols_enabled or []
        broker = self.state.broker
        mode = "PAPER" if self.state.paper else "LIVE"
        _log(f"Tick: broker={broker} mode={mode} enabled={enabled}")

        # Example: pseudo-scan using params
        try:
            for sym in enabled:
                params = self.state.params_per_symbol.get(sym, {})
                # Add minimal visibility
                if params:
                    _log(f"  scan {sym}: rsiW={params.get('rsi_window')} macd=({params.get('macd_fast')},{params.get('macd_slow')},{params.get('macd_signal')})")
        except Exception as e:
            _log(f"Scan error: {e}")

    def stop(self) -> None:
        self.stop_event.set()


# ----------------------------------------------------------------------------
# Public API used by the Dashboard
# ----------------------------------------------------------------------------

def start(broker: str = "Alpaca", paper: bool = True, live_confirmed: bool = False) -> bool:
    """Start (or resume) the orchestrator loop."""
    global _worker
    with _state_lock:
        _state.broker = broker
        _state.paper = paper
        _state.live_confirmed = live_confirmed
        _state.is_running = True
        _state.is_paused = False
        if _worker is None or not _worker.is_alive():
            _worker = Worker(_state, _state_lock)
            _worker.start()
            _log(f"start(): worker launched broker={broker} paper={paper}")
        else:
            _log("start(): resuming existing worker")
    return True


def pause() -> bool:
    with _state_lock:
        _state.is_paused = True
        _log("pause(): loop paused")
    return True


def resume() -> bool:
    with _state_lock:
        _state.is_paused = False
        _state.is_running = True
        _log("resume(): loop resumed")
    return True


def apply_params(params_per_symbol: Dict[str, Dict[str, Any]], enabled_symbols: list[str]) -> bool:
    with _state_lock:
        _state.params_per_symbol = params_per_symbol or {}
        _state.symbols_enabled = enabled_symbols or []
        # Log a short diff
        _log(f"apply_params(): enabled={_state.symbols_enabled}")
    return True


def stop_now() -> bool:
    """Emergency termination & liquidation stub.
    In the real system: close all positions immediately.
    """
    _log("STOP NOW requested — (stub) close all positions immediately")
    # TODO: broker.close_all_positions()
    return True


def close_position() -> bool:
    """Graceful close of current position stub.
    In the real system: use your exit logic.
    """
    _log("close_position() requested — (stub) close active position via exit logic")
    # TODO: position_manager.close_active()
    return True


def status() -> Dict[str, Any]:
    with _state_lock:
        return {
            "broker": _state.broker,
            "paper": _state.paper,
            "live_confirmed": _state.live_confirmed,
            "is_running": _state.is_running,
            "is_paused": _state.is_paused,
            "enabled_symbols": list(_state.symbols_enabled),
            "last_tick_ts": _state.last_tick_ts,
        }


def shutdown() -> None:
    global _worker
    with _state_lock:
        if _worker is not None:
            _worker.stop()
            _worker = None
        _state.is_running = False
        _state.is_paused = True
        _log("shutdown(): orchestrator stopped")


# Convenience for manual testing
if __name__ == "__main__":
    start("Alpaca", paper=True)
    apply_params({"BTC/USD": {"rsi_window": 100, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9}}, ["BTC/USD"]) 
    time.sleep(5)
    pause()
    time.sleep(2)
    resume()
    time.sleep(5)
    stop_now()
    close_position()
    shutdown()
