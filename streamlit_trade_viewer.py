<<<<<<< HEAD
# streamlit_trade_viewer.py

# (imports and setup remain unchanged)
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import math
from datetime import timedelta

with tabs[3]:
    st.subheader("🧪 Backtest Results (From Database)")

    log_scale = st.checkbox("🔁 Log Scale for Charts")
    drawdown_filter = st.checkbox("📉 Only show strategies with drawdown below threshold")
    drawdown_threshold = st.number_input("Drawdown Threshold", value=-100.0)
    mar_stability_cutoff = st.number_input("MAR Ratio Stable/Volatile Threshold", value=0.5)
    stability_filter = st.selectbox("Filter By Stability", ["All", "Stable", "Volatile"])
    sort_column = st.selectbox("Sort Drawdown Table By", ["Strategy", "Max Drawdown", "DD Duration (days)", "CAGR", "MAR Ratio", "Trades"])
    ascending_sort = st.checkbox("⬆️ Sort Ascending", value=False)

    def calculate_drawdown(pnl_series):
        cumulative = pnl_series.cumsum()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak)
        return drawdown

    def rolling_sharpe(profit_series, window=20):
        return profit_series.rolling(window).mean() / profit_series.rolling(window).std()

    def max_drawdown(pnl_series):
        drawdown = calculate_drawdown(pnl_series)
        return drawdown.min()

    def compute_cagr(profits, timestamps):
        if len(timestamps) < 2:
            return 0
        duration = (timestamps[-1] - timestamps[0]).days / 365.25
        final_value = profits.sum()
        return (1 + final_value) ** (1 / duration) - 1 if duration > 0 else 0

    try:
        conn = get_mysql_connection()
        query = "SELECT * FROM backtests ORDER BY timestamp DESC"
        df_bt = pd.read_sql(query, conn)
        conn.close()

        df_bt["timestamp"] = pd.to_datetime(df_bt["timestamp"])

        st.write("Total Records:", len(df_bt))

        with st.expander("🔍 Filter Backtests"):
            symbols = ["All"] + sorted(df_bt["symbol"].dropna().unique().tolist())
            strategies = ["All"] + sorted(df_bt["strategy"].dropna().unique().tolist())

            selected_symbol = st.selectbox("Symbol", symbols)
            selected_strategy = st.selectbox("Strategy", strategies)
            date_range = st.date_input("Date Range", value=(df_bt["timestamp"].min().date(), df_bt["timestamp"].max().date()))
            profit_range = st.slider("Profit Range", float(df_bt["profit"].min()), float(df_bt["profit"].max()), (float(df_bt["profit"].min()), float(df_bt["profit"].max())))

            if selected_symbol != "All":
                df_bt = df_bt[df_bt["symbol"] == selected_symbol]
            if selected_strategy != "All":
                df_bt = df_bt[df_bt["strategy"] == selected_strategy]

            start_date, end_date = date_range
            df_bt = df_bt[(df_bt["timestamp"] >= pd.to_datetime(start_date)) & (df_bt["timestamp"] <= pd.to_datetime(end_date))]
            df_bt = df_bt[(df_bt["profit"] >= profit_range[0]) & (df_bt["profit"] <= profit_range[1])]

        st.dataframe(df_bt, use_container_width=True)

        if not df_bt.empty:
            st.line_chart(df_bt.set_index("timestamp")["profit"].cumsum())

        st.download_button("📤 Export Filtered to CSV", data=df_bt.to_csv(index=False).encode(), file_name="filtered_backtests.csv")

        with st.expander("📊 Drawdown Summary Table"):
            drawdown_summary = []
            for strategy in df_bt["strategy"].unique():
                strat_df = df_bt[df_bt["strategy"] == strategy].sort_values("timestamp")
                profits = strat_df["profit"]
                timestamps = strat_df["timestamp"]
                dd_series = calculate_drawdown(profits)
                dd = dd_series.min()
                dd_start = timestamps[dd_series.idxmax()] if not dd_series.empty else None
                dd_end = timestamps[dd_series.idxmin()] if not dd_series.empty else None
                dd_duration = (dd_end - dd_start).days if dd_start and dd_end else None
                cagr = compute_cagr(profits, timestamps)
                mar_ratio = cagr / abs(dd) if dd != 0 else None
                stability = "Stable" if mar_ratio is not None and mar_ratio >= mar_stability_cutoff else "Volatile"
                trades = len(strat_df)
                drawdown_summary.append((strategy, dd, dd_start, dd_end, dd_duration, cagr, mar_ratio, stability, trades))
            drawdown_df = pd.DataFrame(drawdown_summary, columns=["Strategy", "Max Drawdown", "DD Start", "DD End", "DD Duration (days)", "CAGR", "MAR Ratio", "Stability", "Trades"])
            if drawdown_filter:
                drawdown_df = drawdown_df[drawdown_df["Max Drawdown"] >= drawdown_threshold]
            if stability_filter != "All":
                drawdown_df = drawdown_df[drawdown_df["Stability"] == stability_filter]
            drawdown_df = drawdown_df.sort_values(by=sort_column, ascending=ascending_sort)
            st.dataframe(drawdown_df)

            st.download_button("📥 Export Drawdown Stats to CSV", data=drawdown_df.to_csv(index=False).encode(), file_name="drawdown_summary.csv")

            alert_df = drawdown_df[drawdown_df["Max Drawdown"] < drawdown_threshold]
            if not alert_df.empty:
                st.error("⚠️ Alert: Some strategies exceed the drawdown threshold!")
                st.dataframe(alert_df)

        with st.expander("📊 Cumulative Profit and Drawdown"):
            filtered_strategies = drawdown_df["Strategy"].unique()
            for strategy in filtered_strategies:
                st.markdown(f"#### {strategy}")
                strat_df = df_bt[df_bt["strategy"] == strategy].sort_values("timestamp")
                profit = strat_df.set_index("timestamp")["profit"].cumsum()
                drawdown = calculate_drawdown(strat_df["profit"])
                fig, ax1 = plt.subplots()
                ax1.set_title(f"{strategy}: Profit vs Drawdown")
                ax1.plot(profit, label="Cumulative Profit", color="blue")
                ax2 = ax1.twinx()
                ax2.plot(drawdown.values, label="Drawdown", color="red")
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                ax1.legend(loc="upper left")
                ax2.legend(loc="upper right")
                fig.autofmt_xdate()
                st.pyplot(fig)

        with st.expander("📈 Strategy Risk Heatmap"):
            if not drawdown_df.empty:
                heatmap_data = drawdown_df.set_index("Strategy")[["CAGR", "MAR Ratio", "Max Drawdown"]]
                st.write("### Risk-adjusted Performance Heatmap")
                fig, ax = plt.subplots(figsize=(8, len(heatmap_data)*0.5))
                sns.heatmap(heatmap_data, annot=True, cmap="RdYlGn", linewidths=0.5, fmt=".2f", ax=ax)
                st.pyplot(fig)

    except Exception as e:
        st.error(f"Failed to load backtest data from DB: {e}")
=======
# streamlit_trade_viewer.py

# (imports and setup remain unchanged)
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import math
from datetime import timedelta

with tabs[3]:
    st.subheader("🧪 Backtest Results (From Database)")

    log_scale = st.checkbox("🔁 Log Scale for Charts")
    drawdown_filter = st.checkbox("📉 Only show strategies with drawdown below threshold")
    drawdown_threshold = st.number_input("Drawdown Threshold", value=-100.0)
    mar_stability_cutoff = st.number_input("MAR Ratio Stable/Volatile Threshold", value=0.5)
    stability_filter = st.selectbox("Filter By Stability", ["All", "Stable", "Volatile"])
    sort_column = st.selectbox("Sort Drawdown Table By", ["Strategy", "Max Drawdown", "DD Duration (days)", "CAGR", "MAR Ratio", "Trades"])
    ascending_sort = st.checkbox("⬆️ Sort Ascending", value=False)

    def calculate_drawdown(pnl_series):
        cumulative = pnl_series.cumsum()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak)
        return drawdown

    def rolling_sharpe(profit_series, window=20):
        return profit_series.rolling(window).mean() / profit_series.rolling(window).std()

    def max_drawdown(pnl_series):
        drawdown = calculate_drawdown(pnl_series)
        return drawdown.min()

    def compute_cagr(profits, timestamps):
        if len(timestamps) < 2:
            return 0
        duration = (timestamps[-1] - timestamps[0]).days / 365.25
        final_value = profits.sum()
        return (1 + final_value) ** (1 / duration) - 1 if duration > 0 else 0

    try:
        conn = get_mysql_connection()
        query = "SELECT * FROM backtests ORDER BY timestamp DESC"
        df_bt = pd.read_sql(query, conn)
        conn.close()

        df_bt["timestamp"] = pd.to_datetime(df_bt["timestamp"])

        st.write("Total Records:", len(df_bt))

        with st.expander("🔍 Filter Backtests"):
            symbols = ["All"] + sorted(df_bt["symbol"].dropna().unique().tolist())
            strategies = ["All"] + sorted(df_bt["strategy"].dropna().unique().tolist())

            selected_symbol = st.selectbox("Symbol", symbols)
            selected_strategy = st.selectbox("Strategy", strategies)
            date_range = st.date_input("Date Range", value=(df_bt["timestamp"].min().date(), df_bt["timestamp"].max().date()))
            profit_range = st.slider("Profit Range", float(df_bt["profit"].min()), float(df_bt["profit"].max()), (float(df_bt["profit"].min()), float(df_bt["profit"].max())))

            if selected_symbol != "All":
                df_bt = df_bt[df_bt["symbol"] == selected_symbol]
            if selected_strategy != "All":
                df_bt = df_bt[df_bt["strategy"] == selected_strategy]

            start_date, end_date = date_range
            df_bt = df_bt[(df_bt["timestamp"] >= pd.to_datetime(start_date)) & (df_bt["timestamp"] <= pd.to_datetime(end_date))]
            df_bt = df_bt[(df_bt["profit"] >= profit_range[0]) & (df_bt["profit"] <= profit_range[1])]

        st.dataframe(df_bt, use_container_width=True)

        if not df_bt.empty:
            st.line_chart(df_bt.set_index("timestamp")["profit"].cumsum())

        st.download_button("📤 Export Filtered to CSV", data=df_bt.to_csv(index=False).encode(), file_name="filtered_backtests.csv")

        with st.expander("📊 Drawdown Summary Table"):
            drawdown_summary = []
            for strategy in df_bt["strategy"].unique():
                strat_df = df_bt[df_bt["strategy"] == strategy].sort_values("timestamp")
                profits = strat_df["profit"]
                timestamps = strat_df["timestamp"]
                dd_series = calculate_drawdown(profits)
                dd = dd_series.min()
                dd_start = timestamps[dd_series.idxmax()] if not dd_series.empty else None
                dd_end = timestamps[dd_series.idxmin()] if not dd_series.empty else None
                dd_duration = (dd_end - dd_start).days if dd_start and dd_end else None
                cagr = compute_cagr(profits, timestamps)
                mar_ratio = cagr / abs(dd) if dd != 0 else None
                stability = "Stable" if mar_ratio is not None and mar_ratio >= mar_stability_cutoff else "Volatile"
                trades = len(strat_df)
                drawdown_summary.append((strategy, dd, dd_start, dd_end, dd_duration, cagr, mar_ratio, stability, trades))
            drawdown_df = pd.DataFrame(drawdown_summary, columns=["Strategy", "Max Drawdown", "DD Start", "DD End", "DD Duration (days)", "CAGR", "MAR Ratio", "Stability", "Trades"])
            if drawdown_filter:
                drawdown_df = drawdown_df[drawdown_df["Max Drawdown"] >= drawdown_threshold]
            if stability_filter != "All":
                drawdown_df = drawdown_df[drawdown_df["Stability"] == stability_filter]
            drawdown_df = drawdown_df.sort_values(by=sort_column, ascending=ascending_sort)
            st.dataframe(drawdown_df)

            st.download_button("📥 Export Drawdown Stats to CSV", data=drawdown_df.to_csv(index=False).encode(), file_name="drawdown_summary.csv")

            alert_df = drawdown_df[drawdown_df["Max Drawdown"] < drawdown_threshold]
            if not alert_df.empty:
                st.error("⚠️ Alert: Some strategies exceed the drawdown threshold!")
                st.dataframe(alert_df)

        with st.expander("📊 Cumulative Profit and Drawdown"):
            filtered_strategies = drawdown_df["Strategy"].unique()
            for strategy in filtered_strategies:
                st.markdown(f"#### {strategy}")
                strat_df = df_bt[df_bt["strategy"] == strategy].sort_values("timestamp")
                profit = strat_df.set_index("timestamp")["profit"].cumsum()
                drawdown = calculate_drawdown(strat_df["profit"])
                fig, ax1 = plt.subplots()
                ax1.set_title(f"{strategy}: Profit vs Drawdown")
                ax1.plot(profit, label="Cumulative Profit", color="blue")
                ax2 = ax1.twinx()
                ax2.plot(drawdown.values, label="Drawdown", color="red")
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                ax1.legend(loc="upper left")
                ax2.legend(loc="upper right")
                fig.autofmt_xdate()
                st.pyplot(fig)

        with st.expander("📈 Strategy Risk Heatmap"):
            if not drawdown_df.empty:
                heatmap_data = drawdown_df.set_index("Strategy")[["CAGR", "MAR Ratio", "Max Drawdown"]]
                st.write("### Risk-adjusted Performance Heatmap")
                fig, ax = plt.subplots(figsize=(8, len(heatmap_data)*0.5))
                sns.heatmap(heatmap_data, annot=True, cmap="RdYlGn", linewidths=0.5, fmt=".2f", ax=ax)
                st.pyplot(fig)

    except Exception as e:
        st.error(f"Failed to load backtest data from DB: {e}")
>>>>>>> 0c0df91 (Initial push)
