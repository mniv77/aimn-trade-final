# dashboard.py

"""
AIMn Trading System — Streamlit Control Dashboard (root/dashboard.py)

This dashboard is the single control panel for live trading and tuning.
It supports:
  • Broker selection (Alpaca | Gemini)
  • Secure credential entry (stored via backend helper — wired in later)
  • Paper/Live mode with confirmation for Live
  • Start/Pause scanning, STOP NOW, and Close Position
  • Symbol sync from broker + selection
  • Per-symbol parameter tuning table with Save & Apply (hot reload)
  • Account/positions status panes
  • Live log viewer (tail)

This is a self-contained UI scaffold that **runs today** without the backend.
All broker/db/orchestrator calls are **stubbed** and can be wired up in subsequent files
(app/orchestrator.py, app/broker_*.py, app/state.py, etc.).

Usage:
  streamlit run dashboard.py

Next files to add after this:
  app/__init__.py
  app/broker_base.py, app/broker_alpaca.py, app/broker_gemini.py
  app/state.py (SQLite + encryption helpers)
  app/orchestrator.py (scanner/execution loop)
  app/params.py (schema + defaults)
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any

import streamlit as st

# =============================
# Session State Helpers
# =============================
DEFAULT_SYMBOLS = [
    "BTC/USD",
    "ETH/USD",
    "LTC/USD",
    "BCH/USD",
    "LINK/USD",
    "UNI/USD",
    "AAVE/USD",
]

DEFAULT_PARAMS = {
    "mode": "Both",              # Buy, Sell, Both
    "timeframe": "1h",
    # RSIReal
    "rsi_window": 100,
    "rsi_oversold": 25.0,
    "rsi_overbought": 75.0,
    # MACD
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    # Volume filter
    "vol_lookback": 20,
    "vol_min_mult": 1.2,
    # ATR filter
    "atr_lookback": 14,
    "atr_min": 0.0,
    # Dual Trailing — Early & Peak (V strategy style)
    "early_start_pct": 1.0,
    "early_minus_pct": 0.5,
    "peak_start_pct": 3.0,
    "peak_minus_pct": 1.0,
    # Stops / Targets
    "stop_loss_pct": 4.0,
    "max_profit_pct": 20.0,
    # Sizing
    "capital_pct": 30.0,
    # Cooldown
    "cooldown_bars": 0,
}


def _ensure_state():
    st.session_state.setdefault("broker", "Alpaca")  # or "Gemini"
    st.session_state.setdefault("paper", True)
    st.session_state.setdefault("live_confirmed", False)
    st.session_state.setdefault("connected", False)
    st.session_state.setdefault("symbols", DEFAULT_SYMBOLS.copy())
    st.session_state.setdefault("enabled_symbols", DEFAULT_SYMBOLS[:3])
    st.session_state.setdefault("params_per_symbol", {s: DEFAULT_PARAMS.copy() for s in DEFAULT_SYMBOLS})
    st.session_state.setdefault("is_scanning", False)
    st.session_state.setdefault("log_path", os.getenv("AIMN_LOG_FILE", "aimn_crypto_trading.log"))


# =============================
# Backend Stub Layer
# Replace with real implementations in app/* modules next.
# =============================
class Backend:
    @staticmethod
    def save_credentials(broker: str, key_id: str, secret: str, **extra):
        # TODO: store encrypted in DB via app/state.py
        return True

    @staticmethod
    def list_symbols(broker: str) -> List[str]:
        # TODO: call broker adapter
        # Provide a safe default for now
        if broker == "Gemini":
            return [
                "BTC/USD", "ETH/USD", "LTC/USD", "BCH/USD",
                "SOL/USD", "ADA/USD", "DOGE/USD", "AVAX/USD"
            ]
        return DEFAULT_SYMBOLS.copy()

    @staticmethod
    def get_account(broker: str) -> Dict[str, Any]:
        # TODO: call broker adapter
        return {
            "broker": broker,
            "mode": "Paper" if st.session_state.get("paper", True) else "Live",
            "portfolio_value": 100000.00,
            "buying_power": 100000.00,
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }

    @staticmethod
    def get_positions(broker: str) -> List[Dict[str, Any]]:
        # TODO: real positions
        return []

    @staticmethod
    def apply_params(broker: str, params_per_symbol: Dict[str, Dict[str, Any]]):
        # TODO: persist to DB and hot-apply to orchestrator
        return True

    @staticmethod
    def start_scanner(broker: str):
        # TODO: launch orchestrator loop
        return True

    @staticmethod
    def pause_scanner():
        # TODO: pause orchestrator
        return True

    @staticmethod
    def stop_now():
        # TODO: emergency close all
        return True

    @staticmethod
    def close_position():
        # TODO: graceful close active position using exit logic
        return True


# =============================
# UI Components
# =============================

def ui_topbar():
    col1, col2, col3, col4 = st.columns([1.2, 1, 1, 1])
    with col1:
        st.selectbox(
            "Broker",
            ["Alpaca", "Gemini"],
            index=0 if st.session_state.broker == "Alpaca" else 1,
            key="broker",
            help="Choose the active broker."
        )
    with col2:
        st.toggle("Paper Mode", value=st.session_state.paper, key="paper")
    with col3:
        if not st.session_state.paper:
            st.text_input("Type LIVE to confirm", key="_live_confirm")
            st.session_state.live_confirmed = st.session_state.get("_live_confirm", "").strip().upper() == "LIVE"
            if st.session_state.live_confirmed:
                st.success("LIVE mode confirmed.")
            else:
                st.warning("LIVE mode requires typing LIVE.")
        else:
            st.session_state.live_confirmed = False
            st.info("Running in PAPER mode.")
    with col4:
        if st.button("Connect Broker / Save Keys", use_container_width=True):
            with st.modal("Connect to broker"):
                st.write(f"**{st.session_state.broker}** credentials")
                key_id = st.text_input("API Key", type="password")
                secret = st.text_input("API Secret", type="password")
                extra_json = st.text_area("Extra (JSON)", value="{}", help="Optional: passphrase, base_url, etc.")
                submitted = st.button("Save")
                if submitted:
                    try:
                        extra = json.loads(extra_json or "{}")
                    except Exception:
                        st.error("Extra must be valid JSON.")
                        st.stop()
                    ok = Backend.save_credentials(st.session_state.broker, key_id, secret, **extra)
                    if ok:
                        st.session_state.connected = True
                        st.success("Credentials saved (encrypted store to be wired).")
                    else:
                        st.error("Failed to save credentials.")


def ui_controls():
    st.subheader("Controls")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        if not st.session_state.is_scanning:
            if st.button("▶️ Start Scanning", use_container_width=True):
                ok = Backend.start_scanner(st.session_state.broker)
                if ok:
                    st.session_state.is_scanning = True
                    st.success("Scanner started.")
        else:
            st.button("▶️ Start Scanning", use_container_width=True, disabled=True)
    with c2:
        if st.session_state.is_scanning:
            if st.button("⏸ Pause Scanning", use_container_width=True):
                ok = Backend.pause_scanner()
                if ok:
                    st.session_state.is_scanning = False
                    st.info("Scanner paused.")
        else:
            st.button("⏸ Pause Scanning", use_container_width=True, disabled=True)
    with c3:
        if st.button("🛑 STOP NOW", use_container_width=True, type="secondary"):
            ok = Backend.stop_now()
            if ok:
                st.error("STOP NOW triggered — all positions should be closed.")
    with c4:
        if st.button("📉 Close Position", use_container_width=True):
            ok = Backend.close_position()
            if ok:
                st.warning("Close Position requested.")
    with c5:
        st.write("")
        st.write("")
        st.caption("Use STOP NOW for emergency exit.")


def ui_symbols_and_tuning():
    st.subheader("Symbols & Tuning")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🔄 Sync Symbols from Broker"):
            symbols = Backend.list_symbols(st.session_state.broker)
            st.session_state.symbols = symbols
            # initialize new symbols in params map
            for s in symbols:
                if s not in st.session_state.params_per_symbol:
                    st.session_state.params_per_symbol[s] = DEFAULT_PARAMS.copy()
            st.success(f"Synced {len(symbols)} symbols from {st.session_state.broker}.")
        enabled = st.multiselect(
            "Enable symbols",
            options=st.session_state.symbols,
            default=[s for s in st.session_state.enabled_symbols if s in st.session_state.symbols],
            key="enabled_symbols",
        )
    with c2:
        st.write("**Per-symbol parameters** (edit and Save)")
        sel = st.selectbox("Edit parameters for symbol", options=st.session_state.enabled_symbols)
        params = st.session_state.params_per_symbol.get(sel, DEFAULT_PARAMS.copy()).copy()
        with st.form(key=f"params_{sel}"):
            colA, colB, colC = st.columns(3)
            with colA:
                params["mode"] = st.selectbox("Mode", ["Buy", "Sell", "Both"], index=["Buy","Sell","Both"].index(params["mode"]))
                params["timeframe"] = st.text_input("Timeframe", value=params["timeframe"])
                params["capital_pct"] = st.number_input("Capital %", value=float(params["capital_pct"]), min_value=1.0, max_value=100.0, step=1.0)
                params["cooldown_bars"] = st.number_input("Cooldown Bars", value=int(params["cooldown_bars"]), min_value=0, step=1)
            with colB:
                st.markdown("**RSIReal**")
                params["rsi_window"] = st.number_input("Window", value=int(params["rsi_window"]), min_value=10, step=1)
                params["rsi_oversold"] = st.number_input("Oversold", value=float(params["rsi_oversold"]), min_value=0.0, max_value=100.0, step=0.1)
                params["rsi_overbought"] = st.number_input("Overbought", value=float(params["rsi_overbought"]), min_value=0.0, max_value=100.0, step=0.1)
                st.markdown("**MACD**")
                params["macd_fast"] = st.number_input("Fast", value=int(params["macd_fast"]), min_value=1, step=1)
                params["macd_slow"] = st.number_input("Slow", value=int(params["macd_slow"]), min_value=2, step=1)
                params["macd_signal"] = st.number_input("Signal", value=int(params["macd_signal"]), min_value=1, step=1)
            with colC:
                st.markdown("**Volume Filter**")
                params["vol_lookback"] = st.number_input("Lookback", value=int(params["vol_lookback"]), min_value=1, step=1)
                params["vol_min_mult"] = st.number_input("Min Mult", value=float(params["vol_min_mult"]), min_value=0.0, step=0.1)
                st.markdown("**ATR Filter**")
                params["atr_lookback"] = st.number_input("ATR Lookback", value=int(params["atr_lookback"]), min_value=1, step=1)
                params["atr_min"] = st.number_input("ATR Min", value=float(params["atr_min"]), min_value=0.0, step=0.01)
            st.markdown("**Dual Trailing (V Strategy)**")
            colD, colE = st.columns(2)
            with colD:
                params["early_start_pct"] = st.number_input("Early Start %", value=float(params["early_start_pct"]), min_value=0.0, step=0.1)
                params["early_minus_pct"] = st.number_input("Early Minus %", value=float(params["early_minus_pct"]), min_value=0.0, step=0.1)
            with colE:
                params["peak_start_pct"] = st.number_input("Peak Start %", value=float(params["peak_start_pct"]), min_value=0.0, step=0.1)
                params["peak_minus_pct"] = st.number_input("Peak Minus %", value=float(params["peak_minus_pct"]), min_value=0.0, step=0.1)
            st.markdown("**Stops / Targets**")
            colF, colG = st.columns(2)
            with colF:
                params["stop_loss_pct"] = st.number_input("Stop-Loss %", value=float(params["stop_loss_pct"]), min_value=0.0, step=0.1)
            with colG:
                params["max_profit_pct"] = st.number_input("Max Profit %", value=float(params["max_profit_pct"]), min_value=0.0, step=0.1)

            saved = st.form_submit_button("Save Params")
            if saved:
                st.session_state.params_per_symbol[sel] = params
                ok = Backend.apply_params(st.session_state.broker, st.session_state.params_per_symbol)
                if ok:
                    st.success(f"Parameters saved for {sel} and applied (backend hook pending).")


def ui_status_and_logs():
    st.subheader("Status & Logs")
    c1, c2 = st.columns([1, 1])
    with c1:
        acct = Backend.get_account(st.session_state.broker)
        st.markdown(
            f"""
            **Broker:** {acct.get('broker')}  
            **Mode:** {acct.get('mode')}  
            **Portfolio Value:** ${acct.get('portfolio_value'):,.2f}  
            **Buying Power:** ${acct.get('buying_power'):,.2f}  
            **Updated:** {acct.get('timestamp')}  
            """
        )
        pos = Backend.get_positions(st.session_state.broker)
        if pos:
            st.table(pos)
        else:
            st.info("No open positions.")
    with c2:
        st.write("**Live Log (tail)**")
        log_path = st.session_state.get("log_path")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-500:]
                st.code("".join(lines) or "(log empty)", language="text")
            except Exception as e:
                st.warning(f"Unable to read log: {e}")
        else:
            st.caption(f"Log file not found at {log_path}. Configure AIMN_LOG_FILE env var.")


# =============================
# Main
# =============================

def main():
    st.set_page_config(page_title="AIMn Trading Dashboard", page_icon="🚀", layout="wide")
    st.title("🚀 AIMn Trading System — Live Control & Tuning")
    _ensure_state()

    ui_topbar()
    st.divider()
    ui_controls()
    st.divider()
    ui_symbols_and_tuning()
    st.divider()
    ui_status_and_logs()

    st.caption(
        "This is the UI scaffold. Backend wiring (brokers, DB encryption, orchestrator) "
        "will be added in subsequent files without breaking this interface."
    )


if __name__ == "__main__":
    main()
