<?php
// ========================================================
// 1. DATABASE CONNECTION
// ========================================================
$servername = "localhost";
$username   = "MeirNiv";          // <--- UPDATE THIS
$password   = "mayyam28"; // <--- UPDATE THIS
$dbname     = "MeirNiv$default"; // <--- UPDATE THIS

$conn = new mysqli($servername, $username, $password, $dbname);

// Check connection
if ($conn->connect_error) {
    die("❌ Connection failed: " . $conn->connect_error);
}

// ========================================================
// 2. GET DATA FROM HTML FORM
// ========================================================
// These names match the 'name="..."' in your HTML file
$broker     = $_POST['broker'];
$symbol     = $_POST['symbol'];
$tradeMode  = $_POST['tradeMode'];

// Indicators
$rsiEntry   = $_POST['rsiEntry'];
$rsiExit    = $_POST['rsiExit'];
$macdFast   = $_POST['macdFast'];
$macdSlow   = $_POST['macdSlow'];
$macdSig    = $_POST['macdSig'];

// Risk & Exit
$stopLoss   = $_POST['stopLoss'];
$initProfit = $_POST['initProfit']; // Maps to rsi_exit_min_profit

// Trailing
$trailStart = $_POST['trailStart']; // Maps to peak_trail_start
$trailDrop  = $_POST['trailMinus']; // Maps to peak_trail_minus

// Decay (New!)
$decayStart = $_POST['decayStart'];
$decayRate  = $_POST['decayRate'];

// ========================================================
// 3. LOGIC: MAP RSI FOR BUY vs SELL
// ========================================================
// Your table separates Entry/Exit columns for Buy and Sell.
// We set defaults, then overwrite based on the Trade Mode.

$oversold   = 30;
$overbought = 70;
$exitBuy    = 70;
$exitSell   = 30;

if ($tradeMode == "BUY") {
    // In BUY mode: Entry is Low (Oversold), Exit is High
    $oversold = $rsiEntry;
    $exitBuy  = $rsiExit;
} else {
    // In SELL mode: Entry is High (Overbought), Exit is Low
    $overbought = $rsiEntry;
    $exitSell   = $rsiExit;
}

// ========================================================
// 4. SQL QUERY (INSERT OR UPDATE)
// ========================================================
// We use 'ON DUPLICATE KEY UPDATE' so if you save BTCUSD/BUY again,
// it just updates the numbers instead of creating an error.

$sql = "INSERT INTO strategy_params
        (
            user_id, broker, symbol, timeframe, trade_mode,
            rsi_window,
            oversold_level, overbought_level,
            rsi_exit_buy, rsi_exit_sell,
            rsi_exit_min_profit,
            stop_loss_pct,
            peak_trail_start, peak_trail_minus,
            decay_start_hrs, decay_rate_pct,
            macd_fast, macd_slow, macd_signal,
            use_atr_filter, use_volume_filter, enable_alerts, show_lines, show_signals
        )
        VALUES
        (
            1, '$broker', '$symbol', '1h', '$tradeMode',
            100,
            '$oversold', '$overbought',
            '$exitBuy', '$exitSell',
            '$initProfit',
            '$stopLoss',
            '$trailStart', '$trailDrop',
            '$decayStart', '$decayRate',
            '$macdFast', '$macdSlow', '$macdSig',
            0, 0, 1, 1, 1
        )
        ON DUPLICATE KEY UPDATE
            broker = VALUES(broker),
            oversold_level = VALUES(oversold_level),
            overbought_level = VALUES(overbought_level),
            rsi_exit_buy = VALUES(rsi_exit_buy),
            rsi_exit_sell = VALUES(rsi_exit_sell),
            rsi_exit_min_profit = VALUES(rsi_exit_min_profit),
            stop_loss_pct = VALUES(stop_loss_pct),
            peak_trail_start = VALUES(peak_trail_start),
            peak_trail_minus = VALUES(peak_trail_minus),
            decay_start_hrs = VALUES(decay_start_hrs),
            decay_rate_pct = VALUES(decay_rate_pct),
            macd_fast = VALUES(macd_fast),
            macd_slow = VALUES(macd_slow),
            macd_signal = VALUES(macd_signal),
            updated_at = NOW()
        ";

// ========================================================
// 5. EXECUTE AND FEEDBACK
// ========================================================
if ($conn->query($sql) === TRUE) {
    echo "<h1>✅ Settings Saved!</h1>";
    echo "<div style='font-family: sans-serif; line-height: 1.6;'>";
    echo "Target: <b>$symbol</b> on <b>$broker</b><br>";
    echo "Mode: <b>$tradeMode</b><br>";
    echo "Stop Loss: <b>$stopLoss%</b> | Trail: <b>$trailStart% / $trailDrop%</b><br>";
    echo "Decay: Start after <b>{$decayStart}h</b> at <b>{$decayRate}%/hr</b><br>";
    echo "<br><a href='tuner.html' style='background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;'>⬅ Return to Tuner</a>";
    echo "</div>";
} else {
    echo "<h1>❌ Database Error</h1>";
    echo "Message: " . $conn->error;
}

$conn->close();
?>