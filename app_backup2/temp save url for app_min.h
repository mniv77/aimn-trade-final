# --- UI ROUTES -----------------------------------------------------------------

@app.route("/", endpoint="index")
def index():
    return render_template("index.html")

@app.route("/tuning", endpoint="tuning")
def tuning():
    return render_template("tuning.html")

@app.route("/scanner", endpoint="scanner")
def scanner():
    return render_template("aimn_flowing_scanner_auto.html")

@app.route("/scanner-simulator", endpoint="scanner_simulator")
def scanner_simulator():
    return render_template("scanner-simulator.html")

@app.route("/simple-explanation", endpoint="simple_explanation")
def simple_explanation():
    return render_template("Simple_Explanation.html")

@app.route("/symbol-api-manager", endpoint="symbol_api_manager")
def symbol_api_manager():
    return render_template("symbol_api_manager.html")

@app.route("/trade-tester", endpoint="trade_tester")
def trade_tester():
    return render_template("trade_tester.html")

@app.route("/trade-popup-fixed", endpoint="trade_popup_fixed")
def trade_popup_fixed():
    return render_template("trade-popup-fixed.html")

@app.route("/trade-full", endpoint="trade_full")
def trade_full():
    return render_template("trade-full.html")

@app.route("/trading-philosophy", endpoint="trading_philosophy")
def trading_philosophy():
    return render_template("trading_philosophy.html")

@app.route("/architectural-analysis-and-trading-philosophy",
           endpoint="architectural_analysis_and_trading_philosophy")
def architectural_analysis_and_trading_philosophy():
    return render_template("Architectural Analysis and Trading Philosophy.html")

@app.route("/diagnostics", endpoint="diagnostics")
def diagnostics():
    return render_template("functional_scanner_diagnostics.html")
