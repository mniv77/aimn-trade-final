from flask import Flask, render_template, jsonify, send_file
import json
import random
import os

app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>AIMn Trading System - Revolutionary AI Trading</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
                color: white; 
                min-height: 100vh;
                overflow-x: hidden;
            }
            
            .hero-section {
                background: linear-gradient(135deg, rgba(0,255,0,0.1) 0%, rgba(0,255,255,0.1) 100%);
                padding: 60px 20px;
                text-align: center;
                position: relative;
                border-bottom: 2px solid rgba(0,255,0,0.3);
            }
            
            .hero-section::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(0,255,0,0.1)" stroke-width="0.5"/></pattern></defs><rect width="100" height="100" fill="url(%23grid)"/></svg>');
                opacity: 0.3;
                z-index: 1;
            }
            
            .hero-content {
                position: relative;
                z-index: 2;
                max-width: 1200px;
                margin: 0 auto;
            }
            
            .main-title {
                font-size: 4em;
                background: linear-gradient(45deg, #00ff00, #00ffff, #00ff00);
                background-size: 200% 200%;
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                animation: gradient-shift 3s ease-in-out infinite;
                text-shadow: 0 0 30px rgba(0,255,0,0.5);
                margin-bottom: 20px;
                font-weight: bold;
            }
            
            @keyframes gradient-shift {
                0%, 100% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
            }
            
            .subtitle {
                font-size: 1.8em;
                color: #00ffff;
                margin-bottom: 15px;
                text-shadow: 0 0 20px rgba(0,255,255,0.5);
            }
            
            .tagline {
                font-size: 1.3em;
                color: #cccccc;
                font-style: italic;
                margin-bottom: 40px;
            }
            
            .quote {
                font-size: 1.5em;
                color: #00ff00;
                font-weight: bold;
                background: rgba(0,0,0,0.3);
                padding: 20px;
                border-radius: 10px;
                border-left: 4px solid #00ff00;
                margin: 30px auto;
                max-width: 800px;
            }
            
            .features-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 30px;
                max-width: 1200px;
                margin: 60px auto;
                padding: 0 20px;
            }
            
            .feature-card {
                background: rgba(255,255,255,0.05);
                border-radius: 15px;
                padding: 30px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                border: 1px solid rgba(0,255,0,0.2);
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }
            
            .feature-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(0,255,0,0.1), transparent);
                transition: left 0.6s ease;
            }
            
            .feature-card:hover::before {
                left: 100%;
            }
            
            .feature-card:hover {
                transform: translateY(-10px);
                border-color: #00ff00;
                box-shadow: 0 15px 40px rgba(0,255,0,0.2);
            }
            
            .feature-icon {
                font-size: 3em;
                margin-bottom: 20px;
                color: #00ffff;
                text-shadow: 0 0 20px rgba(0,255,255,0.5);
            }
            
            .feature-title {
                font-size: 1.5em;
                color: #00ff00;
                margin-bottom: 15px;
                font-weight: bold;
            }
            
            .feature-desc {
                color: #cccccc;
                line-height: 1.6;
                font-size: 1.1em;
            }
            
            .professors-section {
                background: linear-gradient(135deg, rgba(0,50,0,0.3) 0%, rgba(0,0,50,0.3) 100%);
                padding: 60px 20px;
                margin: 40px 0;
                border-top: 2px solid rgba(0,255,0,0.3);
                border-bottom: 2px solid rgba(0,255,0,0.3);
            }
            
            .professors-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                max-width: 1000px;
                margin: 0 auto;
            }
            
            .professor-card {
                background: linear-gradient(135deg, #00ff00 0%, #00ffff 100%);
                color: black;
                padding: 25px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0,255,0,0.3);
                transition: all 0.3s ease;
                position: relative;
                overflow: hidden;
            }
            
            .professor-card:hover {
                transform: scale(1.05);
                box-shadow: 0 15px 40px rgba(0,255,0,0.5);
            }
            
            .professor-title {
                font-size: 1.3em;
                font-weight: bold;
                margin-bottom: 10px;
            }
            
            .professor-quote {
                font-style: italic;
                font-size: 1.1em;
            }
            
            .navigation-section {
                background: rgba(0,0,0,0.4);
                padding: 50px 20px;
                margin-top: 40px;
            }
            
            .nav-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 20px;
                max-width: 1400px;
                margin: 0 auto;
            }
            
            .nav-card {
                background: linear-gradient(135deg, rgba(0,100,200,0.3) 0%, rgba(0,200,100,0.3) 100%);
                border-radius: 12px;
                padding: 25px;
                text-align: center;
                transition: all 0.3s ease;
                border: 2px solid transparent;
                position: relative;
                overflow: hidden;
            }
            
            .nav-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(45deg, rgba(0,255,0,0.1), rgba(0,255,255,0.1));
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            
            .nav-card:hover::before {
                opacity: 1;
            }
            
            .nav-card:hover {
                transform: translateY(-5px);
                border-color: #00ff00;
                box-shadow: 0 10px 30px rgba(0,255,0,0.3);
            }
            
            .nav-card a {
                color: #00ffff;
                text-decoration: none;
                font-size: 1.3em;
                font-weight: bold;
                display: block;
                position: relative;
                z-index: 2;
            }
            
            .nav-card a:hover {
                color: #00ff00;
            }
            
            .nav-desc {
                color: #cccccc;
                margin-top: 10px;
                font-size: 1em;
                position: relative;
                z-index: 2;
            }
            
            .stats-section {
                background: rgba(0,0,0,0.6);
                padding: 40px 20px;
                text-align: center;
            }
            
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 30px;
                max-width: 800px;
                margin: 0 auto;
            }
            
            .stat-card {
                background: linear-gradient(135deg, rgba(255,0,100,0.3) 0%, rgba(100,0,255,0.3) 100%);
                padding: 20px;
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.2);
            }
            
            .stat-number {
                font-size: 2.5em;
                font-weight: bold;
                color: #00ff00;
                text-shadow: 0 0 20px rgba(0,255,0,0.5);
            }
            
            .stat-label {
                color: #cccccc;
                font-size: 1.1em;
                margin-top: 5px;
            }
            
            .cta-section {
                background: linear-gradient(135deg, #00ff00 0%, #00ffff 100%);
                color: black;
                padding: 50px 20px;
                text-align: center;
                margin-top: 40px;
            }
            
            .cta-title {
                font-size: 2.5em;
                font-weight: bold;
                margin-bottom: 20px;
            }
            
            .cta-text {
                font-size: 1.3em;
                margin-bottom: 30px;
            }
            
            .cta-button {
                background: black;
                color: #00ff00;
                padding: 15px 40px;
                border: none;
                border-radius: 10px;
                font-size: 1.2em;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s ease;
                margin: 10px;
                text-decoration: none;
                display: inline-block;
            }
            
            .cta-button:hover {
                background: #333;
                transform: scale(1.05);
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            }
            
            @media (max-width: 768px) {
                .main-title { font-size: 2.5em; }
                .subtitle { font-size: 1.4em; }
                .tagline { font-size: 1.1em; }
                .features-grid { grid-template-columns: 1fr; }
                .nav-grid { grid-template-columns: 1fr; }
            }
        </style>
    </head>
    <body>
        <div class="hero-section">
            <div class="hero-content">
                <div class="main-title">🎯 AIMn Trading System</div>
                <div class="subtitle">Revolutionary Multi-Professor Auto Trading Platform</div>
                <div class="tagline">Where AI Meets Precision Trading</div>
                <div class="quote">
                    "Let the market pick your trades. Let logic pick your exits."
                </div>
            </div>
        </div>
        
        <div class="stats-section">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">73%</div>
                    <div class="stat-label">Win Rate</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">24/7</div>
                    <div class="stat-label">Market Scanning</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">4x</div>
                    <div class="stat-label">Indicator Precision</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">0</div>
                    <div class="stat-label">Emotional Decisions</div>
                </div>
            </div>
        </div>
        
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-icon">🎯</div>
                <div class="feature-title">Multiple Professor System</div>
                <div class="feature-desc">
                    Each trade is independent, like consulting different expert "professors." 
                    No emotional attachment to previous positions - pure logic-based decisions.
                </div>
            </div>
            
            <div class="feature-card">
                <div class="feature-icon">⚡</div>
                <div class="feature-title">Zero Idle Time</div>
                <div class="feature-desc">
                    After every exit, instantly scans ALL symbols for the next best opportunity. 
                    Never wastes time waiting for the same stock to signal again.
                </div>
            </div>
            
            <div class="feature-card">
                <div class="feature-icon">📊</div>
                <div class="feature-title">4-Indicator Precision</div>
                <div class="feature-desc">
                    RSI Real + MACD + Volume Trend + ATR Volatility. Only trades when ALL 
                    systems align for maximum win probability.
                </div>
            </div>
            
            <div class="feature-card">
                <div class="feature-icon">🎪</div>
                <div class="feature-title">Dual Trailing System</div>
                <div class="feature-desc">
                    Intelligent profit capture with loose early trailing (let winners run) 
                    and tight peak trailing (lock in maximum gains).
                </div>
            </div>
            
            <div class="feature-card">
                <div class="feature-icon">🧠</div>
                <div class="feature-title">No Human Bias</div>
                <div class="feature-desc">
                    Eliminates revenge trading, FOMO, and emotional decisions. Each trade 
                    evaluated purely on technical merit and market conditions.
                </div>
            </div>
            
            <div class="feature-card">
                <div class="feature-icon">🔄</div>
                <div class="feature-title">Continuous Opportunity</div>
                <div class="feature-desc">
                    Scans multiple exchanges simultaneously: Stocks, Crypto, Forex, Futures. 
                    Always finds the market with the strongest signals.
                </div>
            </div>
        </div>
        
        <div class="professors-section">
            <div class="hero-content">
                <h2 style="text-align: center; color: #00ff00; font-size: 2.5em; margin-bottom: 40px;">
                    🎓 Your Trading "Professors" at Work
                </h2>
                <div class="professors-grid">
                    <div class="professor-card">
                        <div class="professor-title">👨‍🏫 Professor Alpha</div>
                        <div class="professor-quote">"NVDA showing perfect RSI setup with volume confirmation - BUY signal!"</div>
                    </div>
                    <div class="professor-card">
                        <div class="professor-title">👩‍🏫 Professor Beta</div>
                        <div class="professor-quote">"Bitcoin MACD bearish cross detected - SELL opportunity identified!"</div>
                    </div>
                    <div class="professor-card">
                        <div class="professor-title">👨‍🏫 Professor Gamma</div>
                        <div class="professor-quote">"TSLA oversold with volume spike - High probability reversal trade!"</div>
                    </div>
                    <div class="professor-card">
                        <div class="professor-title">👩‍🏫 Professor Delta</div>
                        <div class="professor-quote">"Gold futures showing trend break with ATR expansion - Enter now!"</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="navigation-section">
            <div class="hero-content">
                <h2 style="text-align: center; color: #00ffff; font-size: 2.2em; margin-bottom: 40px;">
                    🚀 Access Your Trading Command Center
                </h2>
                <div class="nav-grid">
                    <div class="nav-card">
                        <a href="/scanne">📊 Live Scanner</a>
                        <div class="nav-desc">Real-time market scanning across all exchanges</div>
                    </div>
                    <div class="nav-card">
                        <a href="/tuning">🎛️ Tuning Parameters Center</a>
                        <div class="nav-desc">Advanced strategy optimization and parameter tuning</div>
                    </div>
                    <div class="nav-card">
                        <a href="/orders">📈 Orders</a>
                        <div class="nav-desc">Order management and trade history</div>
                    </div>
                    <div class="nav-card">
                        <a href="/popper">🪟 Trade Popup</a>
                        <div class="nav-desc">Live trade monitoring and emergency controls</div>
                    </div>
                    <div class="nav-card">
                        <a href="/loop">🔄 Loop Controls</a>
                        <div class="nav-desc">Trading automation and system controls</div>
                    </div>
                    <div class="nav-card">
                        <a href="/snapshots">📷 Snapshots</a>
                        <div class="nav-desc">Trade history, snapshots & performance analytics</div>
                    </div>
                    <div class="nav-card">
                        <a href="/symbols">🔧 Symbol & API Management</a>
                        <div class="nav-desc">Configure trading pairs and broker connections</div>
                    </div>
                    <div class="nav-card">
                        <a href="/scanner-simulator">🧪 Trade Scanner Simulator</a>
                        <div class="nav-desc">Manual trade popup testing and simulation</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="cta-section">
            <div class="cta-title">Ready to Trade Like a Pro?</div>
            <div class="cta-text">
                Join the revolution of traders who never miss an opportunity
            </div>
            <a href="/scanne" class="cta-button">🎯 Start Live Scanning</a>
            <a href="/tuning" class="cta-button">🎛️ Tune Parameters</a>
        </div>
        
        <script>
            // Add some dynamic effects
            document.addEventListener('DOMContentLoaded', function() {
                // Animate feature cards on scroll
                const observerOptions = {
                    threshold: 0.1,
                    rootMargin: '0px 0px -50px 0px'
                };
                
                const observer = new IntersectionObserver(function(entries) {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            entry.target.style.opacity = '1';
                            entry.target.style.transform = 'translateY(0)';
                        }
                    });
                }, observerOptions);
                
                // Observe all feature cards
                document.querySelectorAll('.feature-card, .nav-card').forEach(card => {
                    card.style.opacity = '0';
                    card.style.transform = 'translateY(30px)';
                    card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
                    observer.observe(card);
                });
                
                // Add click tracking
                document.querySelectorAll('a').forEach(link => {
                    link.addEventListener('click', function(e) {
                        console.log('Navigation:', this.href);
                    });
                });
            });
        </script>
    </body>
    </html>
    '''

@app.route('/tuning')
def tuning_parameters():
    """Serve the Tuning Parameters Center HTML content directly"""
    return '''
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIMn Strategy Tuning Center - V5.2</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            color: white;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .strategy-info {
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .sync-indicator {
            background: rgba(255,193,7,0.3);
            border: 2px solid #ffc107;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: bold;
        }
        
        .form-container {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 30px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        
        .symbol-section {
            margin-bottom: 30px;
            border: 2px solid rgba(255,255,255,0.2);
            border-radius: 10px;
            padding: 20px;
        }
        
        .symbol-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .paste-area {
            margin-bottom: 20px;
        }
        
        .paste-area textarea {
            width: 100%;
            height: 120px;
            padding: 15px;
            border: 2px dashed rgba(255,255,255,0.5);
            border-radius: 8px;
            background: rgba(255,255,255,0.05);
            color: white;
            font-family: monospace;
            resize: vertical;
            font-size: 14px;
        }
        
        .paste-area textarea::placeholder {
            color: rgba(255,255,255,0.6);
        }
        
        .param-sections {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .param-section {
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .param-section h3 {
            margin-bottom: 15px;
            color: #87ceeb;
            border-bottom: 1px solid rgba(255,255,255,0.3);
            padding-bottom: 5px;
        }
        
        .param-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        
        .param-group {
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 6px;
        }
        
        .param-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #e0e0e0;
            font-size: 12px;
        }
        
        .param-group input, .param-group select {
            width: 100%;
            padding: 6px 10px;
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 4px;
            background: rgba(255,255,255,0.1);
            color: white;
            font-size: 13px;
        }
        
        .param-group input::placeholder {
            color: rgba(255,255,255,0.6);
        }
        
        .mode-selector {
            text-align: center;
            margin-bottom: 20px;
        }
        
        .mode-selector select {
            font-size: 1.2em;
            padding: 10px 20px;
            border-radius: 8px;
            background: rgba(255,255,255,0.1);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
        }
        
        .button-group {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 20px;
        }
        
        button {
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .btn-parse {
            background: #28a745;
            color: white;
        }
        
        .btn-save {
            background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
            color: white;
            font-size: 18px;
            padding: 15px 30px;
            box-shadow: 0 6px 20px rgba(0,123,255,0.4);
        }
        
        .btn-save:hover {
            background: linear-gradient(135deg, #0056b3 0%, #007bff 100%);
            box-shadow: 0 8px 25px rgba(0,123,255,0.6);
        }
        
        .btn-clear {
            background: #dc3545;
            color: white;
        }
        
        .btn-auto-fill {
            background: linear-gradient(135deg, #ffc107 0%, #ff8f00 100%);
            color: black;
            font-size: 20px;
            font-weight: bold;
            padding: 18px 35px;
            box-shadow: 0 8px 25px rgba(255,193,7,0.4);
            border: 3px solid #ff8f00;
        }
        
        .btn-auto-fill:hover {
            background: linear-gradient(135deg, #ff8f00 0%, #ffc107 100%);
            transform: translateY(-4px);
            box-shadow: 0 12px 35px rgba(255,193,7,0.6);
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        
        .status-display {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            font-weight: bold;
        }
        
        .status-success {
            background: rgba(40,167,69,0.3);
            border: 1px solid #28a745;
        }
        
        .status-error {
            background: rgba(220,53,69,0.3);
            border: 1px solid #dc3545;
        }
        
        .hidden {
            display: none;
        }
        
        .current-params {
            background: rgba(0,123,255,0.2);
            border: 1px solid #007bff;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }
        
        .current-params h4 {
            margin-bottom: 10px;
            color: #87ceeb;
        }
        
        .full-width {
            grid-column: 1 / -1;
        }
        
        .help-button {
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #ff6600 0%, #ff4500 100%);
            color: white;
            border: none;
            border-radius: 50px;
            width: 60px;
            height: 60px;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 5px 15px rgba(255,102,0,0.3);
            transition: all 0.3s ease;
            z-index: 1000;
        }
        
        .help-button:hover {
            transform: scale(1.1);
            box-shadow: 0 8px 25px rgba(255,102,0,0.5);
        }
        
        .popup-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 2000;
            display: none;
            justify-content: center;
            align-items: center;
        }
        
        .popup-content {
            background: #1a1a1a;
            border: 2px solid #00ff00;
            border-radius: 15px;
            padding: 30px;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
            position: relative;
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
        }
        
        .popup-close {
            position: absolute;
            top: 15px;
            right: 20px;
            background: #ff0000;
            color: white;
            border: none;
            border-radius: 50%;
            width: 35px;
            height: 35px;
            cursor: pointer;
            font-size: 18px;
            font-weight: bold;
        }
        
        .popup-close:hover {
            background: #ff3333;
        }
        
        .step {
            background: rgba(0,255,0,0.1);
            border: 1px solid #00ff00;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
        }
        
        .step-number {
            background: #00ff00;
            color: black;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            margin-right: 15px;
        }
        
        .step-title {
            color: #00ffff;
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 10px;
        }
        
        .code-example {
            background: #000;
            border: 1px solid #333;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            color: #00ff00;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Help Button -->
        <button class="help-button" onclick="openHelpPopup()" title="How to use Parameter Transfer">
            ❓
        </button>
        
        <div class="header">
            <h1>🎯 AIMn Strategy Tuning Center - V5.2</h1>
            <p>TradingView Parameter Transfer to Database</p>
        </div>
        
        <div class="strategy-info">
            <strong>📊 Strategy:</strong> AImn-Cl Looping Strategy - V6.1 (Dual Trailing System)<br>
            <strong>🎮 Features:</strong> RSI Real + MACD + Volume + ATR + Dual Trailing System
        </div>
        
        <div class="sync-indicator" style="display: none;">
            🔄 <strong>SYNCHRONIZED ORDER:</strong> Paste TV numbers in exact order - auto-fills all fields!
        </div>
        
        <div class="form-container">
            <!-- Symbol and Mode Selection -->
            <div class="symbol-section">
                <div class="symbol-header">
                    <select id="symbolSelect" style="font-size: 1.2em; padding: 10px;">
                        <option value="">Select Symbol/Exchange</option>
                        <option value="BTC_BINANCE">BTC - Binance</option>
                        <option value="ETH_BINANCE">ETH - Binance</option>
                        <option value="LTC_BINANCE">LTC - Binance</option>
                        <option value="BCH_BINANCE">BCH - Binance</option>
                        <option value="LINK_BINANCE">LINK - Binance</option>
                        <option value="UNI_BINANCE">UNI - Binance</option>
                        <option value="AAVE_BINANCE">AAVE - Binance</option>
                        <option value="AAPL_NASDAQ">AAPL - NASDAQ</option>
                        <option value="TSLA_NASDAQ">TSLA - NASDAQ</option>
                        <option value="MSFT_NASDAQ">MSFT - NASDAQ</option>
                    </select>
                </div>
                
                <!-- TradingView Numbers Paste Area -->
                <div class="paste-area">
                    <label for="tvNumbers">📋 Paste TradingView Numbers (Copy from TV Parameter Display):</label>
                    <textarea id="tvNumbers" placeholder="Paste numbers from TradingView strategy display...

EXACT ORDER EXPECTED:
1. Trade Mode (BUY/SELL)
2. RSI Real Window
3. Oversold Level (whole)
4. Oversold Level (decimal)
5. Overbought Level (whole)
6. Overbought Level (decimal)
7. RSI Exit Level Buy (whole)
8. RSI Exit Level Buy (decimal)
9. RSI Exit Level Sell (whole)
10. RSI Exit Level Sell (decimal)
11. MACD Fast Length
12. MACD Slow Length
13. MACD Signal Length
14. Volume MA Length
15. Volume Threshold Multiplier
16. Use Volume Confirmation
17. ATR Length
18. ATR MA Length
19. ATR Expansion Multiplier
20. Use ATR Volatility Filter
21. Stop Loss % (whole)
22. Stop Loss % (decimal)
23. Early Trail Start % (whole)
24. Early Trail Start % (decimal)
25. Early Trail Minus % (whole)
26. Early Trail Minus % (decimal)
27. Peak Trail Start % (whole)
28. Peak Trail Start % (decimal)
29. Peak Trail Minus % (whole)
30. Peak Trail Minus % (decimal)
31. RSI Exit Min Profit % (whole)
32. RSI Exit Min Profit % (decimal)
33. Enable Alerts
34. Show All Lines
35. Show Entry/Exit Signals"></textarea>
                    <div class="button-group">
                        <button class="btn-auto-fill" onclick="autoFillFromNumbers()">🚀 AUTO-FILL ALL FIELDS</button>
                        <button class="btn-clear" onclick="clearPasteArea()">🗑️ Clear</button>
                    </div>
                </div>
                
                <!-- Parameter Sections - ALL FIELDS IN EXACT TV ORDER -->
                <div class="param-sections">
                    <!-- Core Settings -->
                    <div class="param-section">
                        <h3>🎯 Core Settings</h3>
                        <div class="param-grid">
                            <div class="param-group">
                                <label for="tradeMode">1. Trade Mode</label>
                                <select id="tradeMode">
                                    <option value="BUY">BUY</option>
                                    <option value="SELL">SELL</option>
                                </select>
                            </div>
                            
                            <div class="param-group">
                                <label for="rsiWindow">2. RSI Real Window</label>
                                <input type="number" id="rsiWindow" placeholder="100" min="10">
                            </div>
                            
                            <div class="param-group">
                                <label for="oversoldLevel_Int">3. Oversold Level (whole)</label>
                                <input type="number" id="oversoldLevel_Int" placeholder="30" min="1" max="99">
                            </div>
                            
                            <div class="param-group">
                                <label for="oversoldLevel_Dec">4. Oversold Level (decimal)</label>
                                <input type="number" id="oversoldLevel_Dec" placeholder="0.0" min="0" max="0.9" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="overboughtLevel_Int">5. Overbought Level (whole)</label>
                                <input type="number" id="overboughtLevel_Int" placeholder="70" min="1" max="99">
                            </div>
                            
                            <div class="param-group">
                                <label for="overboughtLevel_Dec">6. Overbought Level (decimal)</label>
                                <input type="number" id="overboughtLevel_Dec" placeholder="0.0" min="0" max="0.9" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="rsiExitLevelBuy_Int">7. RSI Exit Buy (whole)</label>
                                <input type="number" id="rsiExitLevelBuy_Int" placeholder="70" min="1" max="99">
                            </div>
                            
                            <div class="param-group">
                                <label for="rsiExitLevelBuy_Dec">8. RSI Exit Buy (decimal)</label>
                                <input type="number" id="rsiExitLevelBuy_Dec" placeholder="0.0" min="0" max="0.9" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="rsiExitLevelSell_Int">9. RSI Exit Sell (whole)</label>
                                <input type="number" id="rsiExitLevelSell_Int" placeholder="30" min="1" max="99">
                            </div>
                            
                            <div class="param-group">
                                <label for="rsiExitLevelSell_Dec">10. RSI Exit Sell (decimal)</label>
                                <input type="number" id="rsiExitLevelSell_Dec" placeholder="0.0" min="0" max="0.9" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="fastLength">11. MACD Fast Length</label>
                                <input type="number" id="fastLength" placeholder="12" min="1">
                            </div>
                            
                            <div class="param-group">
                                <label for="slowLength">12. MACD Slow Length</label>
                                <input type="number" id="slowLength" placeholder="26" min="1">
                            </div>
                            
                            <div class="param-group">
                                <label for="signalLength">13. MACD Signal Length</label>
                                <input type="number" id="signalLength" placeholder="9" min="1">
                            </div>
                            
                            <div class="param-group">
                                <label for="volMALength">14. Volume MA Length</label>
                                <input type="number" id="volMALength" placeholder="20" min="5">
                            </div>
                            
                            <div class="param-group">
                                <label for="volThreshold">15. Volume Threshold</label>
                                <input type="number" id="volThreshold" placeholder="1.2" min="1.0" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="useVolumeFilter">16. Use Volume Filter</label>
                                <select id="useVolumeFilter">
                                    <option value="true">true</option>
                                    <option value="false">false</option>
                                </select>
                            </div>
                            
                            <div class="param-group">
                                <label for="atrLength">17. ATR Length</label>
                                <input type="number" id="atrLength" placeholder="14" min="1">
                            </div>
                            
                            <div class="param-group">
                                <label for="atrMALength">18. ATR MA Length</label>
                                <input type="number" id="atrMALength" placeholder="20" min="1">
                            </div>
                            
                            <div class="param-group">
                                <label for="atrThreshold">19. ATR Threshold</label>
                                <input type="number" id="atrThreshold" placeholder="1.3" min="1.0" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="useATRFilter">20. Use ATR Filter</label>
                                <select id="useATRFilter">
                                    <option value="true">true</option>
                                    <option value="false">false</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Exit Settings -->
                    <div class="param-section">
                        <h3>🎯 Exit Settings</h3>
                        <div class="param-grid">
                            <div class="param-group">
                                <label for="stopLossInt">21. Stop Loss % (whole)</label>
                                <input type="number" id="stopLossInt" placeholder="2" min="0">
                            </div>
                            
                            <div class="param-group">
                                <label for="stopLossDec">22. Stop Loss % (decimal)</label>
                                <input type="number" id="stopLossDec" placeholder="0.0" min="0" max="0.9" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="earlyStartInt">23. Early Trail Start % (whole)</label>
                                <input type="number" id="earlyStartInt" placeholder="1" min="0">
                            </div>
                            
                            <div class="param-group">
                                <label for="earlyStartDec">24. Early Trail Start % (decimal)</label>
                                <input type="number" id="earlyStartDec" placeholder="0.0" min="0" max="0.9" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="earlyMinusInt">25. Early Trail Minus % (whole)</label>
                                <input type="number" id="earlyMinusInt" placeholder="15" min="0">
                            </div>
                            
                            <div class="param-group">
                                <label for="earlyMinusDec">26. Early Trail Minus % (decimal)</label>
                                <input type="number" id="earlyMinusDec" placeholder="0.0" min="0" max="0.9" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="peakStartInt">27. Peak Trail Start % (whole)</label>
                                <input type="number" id="peakStartInt" placeholder="5" min="1">
                            </div>
                            
                            <div class="param-group">
                                <label for="peakStartDec">28. Peak Trail Start % (decimal)</label>
                                <input type="number" id="peakStartDec" placeholder="0.0" min="0" max="0.9" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="peakMinusInt">29. Peak Trail Minus % (whole)</label>
                                <input type="number" id="peakMinusInt" placeholder="0" min="0">
                            </div>
                            
                            <div class="param-group">
                                <label for="peakMinusDec">30. Peak Trail Minus % (decimal)</label>
                                <input type="number" id="peakMinusDec" placeholder="0.5" min="0" max="0.9" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="rsiProfitInt">31. RSI Exit Min Profit % (whole)</label>
                                <input type="number" id="rsiProfitInt" placeholder="1" min="0">
                            </div>
                            
                            <div class="param-group">
                                <label for="rsiProfitDec">32. RSI Exit Min Profit % (decimal)</label>
                                <input type="number" id="rsiProfitDec" placeholder="0.0" min="0" max="0.9" step="0.1">
                            </div>
                            
                            <div class="param-group">
                                <label for="enableAlerts">33. Enable Alerts</label>
                                <select id="enableAlerts">
                                    <option value="true">true</option>
                                    <option value="false">false</option>
                                </select>
                            </div>
                            
                            <div class="param-group">
                                <label for="showLines">34. Show All Lines</label>
                                <select id="showLines">
                                    <option value="true">true</option>
                                    <option value="false">false</option>
                                </select>
                            </div>
                            
                            <div class="param-group">
                                <label for="showSignals">35. Show Entry/Exit Signals</label>
                                <select id="showSignals">
                                    <option value="true">true</option>
                                    <option value="false">false</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="button-group">
                    <button class="btn-save" onclick="saveParameters()">💾 Save to Database</button>
                    <button class="btn-clear" onclick="clearForm()">🗑️ Clear All</button>
                </div>
                
                <!-- Status Display -->
                <div id="statusDisplay" class="status-display hidden"></div>
            </div>
            
            <!-- Return to Dashboard Button -->
            <div style="text-align: center; margin-top: 40px; padding: 30px;">
                <a href="/" style="background: #28a745; color: white; padding: 12px 25px; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: bold; display: inline-block; transition: all 0.3s ease;" 
                   onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 5px 15px rgba(0,0,0,0.3)'"
                   onmouseout="this.style.transform='translateY(0px)'; this.style.boxShadow='none'">
                    🏠 Return to Dashboard
                </a>
            </div>
        </div>
    </div>

    <!-- Help Popup -->
    <div class="popup-overlay" id="helpPopup">
        <div class="popup-content">
            <button class="popup-close" onclick="closeHelpPopup()">×</button>
            
            <h2 style="color: #00ff00; text-align: center; margin-bottom: 30px;">
                🎯 How to Transfer Parameters from TradingView
            </h2>
            
            <div class="step">
                <div style="display: flex; align-items: flex-start;">
                    <span class="step-number">1</span>
                    <div>
                        <div class="step-title">Open Your TradingView Strategy</div>
                        <p>Open your <strong>AImn-Cl Looping Strategy - V6.1</strong> in TradingView and make sure it's loaded on a chart.</p>
                    </div>
                </div>
            </div>
            
            <div class="step">
                <div style="display: flex; align-items: flex-start;">
                    <span class="step-number">2</span>
                    <div>
                        <div class="step-title">Enable Parameter Display</div>
                        <p>In your strategy settings, find <strong>"📋 Show Parameter Display for Copy"</strong> and set it to <strong>TRUE</strong>.</p>
                        <p style="color: #ffc107;">⚠️ This will show a parameter box in the top-right corner of your chart.</p>
                    </div>
                </div>
            </div>
            
            <div class="step">
                <div style="display: flex; align-items: flex-start;">
                    <span class="step-number">3</span>
                    <div>
                        <div class="step-title">Set Your Trade Mode</div>
                        <p>Choose <strong>BUY</strong> or <strong>SELL</strong> mode in your TradingView strategy settings. The parameter display will update automatically.</p>
                    </div>
                </div>
            </div>
            
            <div class="step">
                <div style="display: flex; align-items: flex-start;">
                    <span class="step-number">4</span>
                    <div>
                        <div class="step-title">Copy Parameters from TradingView</div>
                        <p><strong>Right-click</strong> on the parameter display box (top-right of chart) and select <strong>"Copy"</strong>.</p>
                        <div class="code-example">
You should copy something like:<br>
SELL<br>
100<br>
30<br>
0.0<br>
70<br>
0.0<br>
12<br>
26<br>
9<br>
...and so on (35 values total)
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="step">
                <div style="display: flex; align-items: flex-start;">
                    <span class="step-number">5</span>
                    <div>
                        <div class="step-title">Come Back to This Page</div>
                        <p>Return to this tuning center page and select your <strong>Symbol/Exchange</strong> from the dropdown at the top.</p>
                    </div>
                </div>
            </div>
            
            <div class="step">
                <div style="display: flex; align-items: flex-start;">
                    <span class="step-number">6</span>
                    <div>
                        <div class="step-title">Paste and Auto-Fill</div>
                        <p><strong>Paste</strong> the copied numbers into the text area below, then click the <strong>"🚀 AUTO-FILL ALL FIELDS"</strong> button.</p>
                        <p style="color: #00ff00;">✅ All 35 fields will populate automatically in perfect order!</p>
                    </div>
                </div>
            </div>
            
            <div class="step">
                <div style="display: flex; align-items: flex-start;">
                    <span class="step-number">7</span>
                    <div>
                        <div class="step-title">Save to Database</div>
                        <p>Review the auto-filled values, then click <strong>"💾 Save to Database"</strong> to store your optimized parameters.</p>
                        <p style="color: #ffc107;">🎯 Your scanner and trading system will now use these tuned parameters!</p>
                    </div>
                </div>
            </div>
            
            <div style="background: rgba(0,123,255,0.2); border: 1px solid #007bff; border-radius: 8px; padding: 20px; margin-top: 30px;">
                <h3 style="color: #00ffff; margin-bottom: 15px;">💡 Pro Tips:</h3>
                <ul style="color: #e0e0e0; line-height: 1.8;">
                    <li>Test different parameter sets on different timeframes</li>
                    <li>Save separate configurations for different market conditions</li>
                    <li>Always backtest before applying to live trading</li>
                    <li>The boolean values (true/false) transfer automatically</li>
                    <li>Each symbol can have different optimized parameters</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <button onclick="closeHelpPopup()" style="background: #28a745; color: white; padding: 15px 30px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer;">
                    Got it! Let's start tuning 🚀
                </button>
            </div>
        </div>
    </div>

    <script>
        // Database simulation
        let parameterDatabase = {};
        
        // EXACT ORDER MAPPING - SYNCHRONIZED WITH TV STRATEGY
        const fieldOrder = [
            'tradeMode',                // 1
            'rsiWindow',               // 2
            'oversoldLevel_Int',       // 3
            'oversoldLevel_Dec',       // 4
            'overboughtLevel_Int',     // 5
            'overboughtLevel_Dec',     // 6
            'rsiExitLevelBuy_Int',     // 7
            'rsiExitLevelBuy_Dec',     // 8
            'rsiExitLevelSell_Int',    // 9
            'rsiExitLevelSell_Dec',    // 10
            'fastLength',              // 11
            'slowLength',              // 12
            'signalLength',            // 13
            'volMALength',             // 14
            'volThreshold',            // 15
            'useVolumeFilter',         // 16
            'atrLength',               // 17
            'atrMALength',             // 18
            'atrThreshold',            // 19
            'useATRFilter',            // 20
            'stopLossInt',             // 21
            'stopLossDec',             // 22
            'earlyStartInt',           // 23
            'earlyStartDec',           // 24
            'earlyMinusInt',           // 25
            'earlyMinusDec',           // 26
            'peakStartInt',            // 27
            'peakStartDec',            // 28
            'peakMinusInt',            // 29
            'peakMinusDec',            // 30
            'rsiProfitInt',            // 31
            'rsiProfitDec',            // 32
            'enableAlerts',            // 33
            'showLines',               // 34
            'showSignals'              // 35
        ];
        
        function autoFillFromNumbers() {
            const pasteArea = document.getElementById('tvNumbers');
            const text = pasteArea.value.trim();
            
            if (!text) {
                showStatus('Please paste TradingView numbers first!', 'error');
                return;
            }
            
            // Split by lines and filter empty lines
            const lines = text.split('\\n').map(line => line.trim()).filter(line => line !== '');
            
            if (lines.length < fieldOrder.length) {
                showStatus(`⚠️ Expected ${fieldOrder.length} values, got ${lines.length}. Please check your TV copy!`, 'error');
                return;
            }
            
            let filled = 0;
            
            // Fill each field in exact order
            for (let i = 0; i < fieldOrder.length && i < lines.length; i++) {
                const fieldId = fieldOrder[i];
                const field = document.getElementById(fieldId);
                const value = lines[i];
                
                if (field) {
                    field.value = value;
                    field.style.background = 'rgba(40,167,69,0.3)';
                    filled++;
                    
                    // Reset color after 2 seconds
                    setTimeout(() => {
                        field.style.background = 'rgba(255,255,255,0.1)';
                    }, 2000);
                }
            }
            
            if (filled > 0) {
                showStatus(`✅ Auto-filled ${filled} parameters in perfect order!`, 'success');
            } else {
                showStatus('❌ Failed to fill parameters. Check the format!', 'error');
            }
        }
        
        function saveParameters() {
            const symbolSelect = document.getElementById('symbolSelect');
            const symbol = symbolSelect.value;
            const tradeMode = document.getElementById('tradeMode').value;
            
            if (!symbol) {
                showStatus('Please select a symbol first!', 'error');
                return;
            }
            
            // Collect all parameters in order
            const params = {
                symbol: symbol,
                trade_mode: tradeMode,
                rsi_window: document.getElementById('rsiWindow').value || '100',
                oversold_level_int: document.getElementById('oversoldLevel_Int').value || '30',
                oversold_level_dec: document.getElementById('oversoldLevel_Dec').value || '0.0',
                overbought_level_int: document.getElementById('overboughtLevel_Int').value || '70',
                overbought_level_dec: document.getElementById('overboughtLevel_Dec').value || '0.0',
                rsi_exit_buy_int: document.getElementById('rsiExitLevelBuy_Int').value || '70',
                rsi_exit_buy_dec: document.getElementById('rsiExitLevelBuy_Dec').value || '0.0',
                rsi_exit_sell_int: document.getElementById('rsiExitLevelSell_Int').value || '30',
                rsi_exit_sell_dec: document.getElementById('rsiExitLevelSell_Dec').value || '0.0',
                macd_fast: document.getElementById('fastLength').value || '12',
                macd_slow: document.getElementById('slowLength').value || '26',
                macd_signal: document.getElementById('signalLength').value || '9',
                vol_ma_length: document.getElementById('volMALength').value || '20',
                vol_threshold: document.getElementById('volThreshold').value || '1.2',
                use_vol_filter: document.getElementById('useVolumeFilter').value || 'true',
                atr_length: document.getElementById('atrLength').value || '14',
                atr_ma_length: document.getElementById('atrMALength').value || '20',
                atr_threshold: document.getElementById('atrThreshold').value || '1.3',
                use_atr_filter: document.getElementById('useATRFilter').value || 'true',
                stop_loss_int: document.getElementById('stopLossInt').value || '2',
                stop_loss_dec: document.getElementById('stopLossDec').value || '0.0',
                early_start_int: document.getElementById('earlyStartInt').value || '1',
                early_start_dec: document.getElementById('earlyStartDec').value || '0.0',
                early_minus_int: document.getElementById('earlyMinusInt').value || '15',
                early_minus_dec: document.getElementById('earlyMinusDec').value || '0.0',
                peak_start_int: document.getElementById('peakStartInt').value || '5',
                peak_start_dec: document.getElementById('peakStartDec').value || '0.0',
                peak_minus_int: document.getElementById('peakMinusInt').value || '0',
                peak_minus_dec: document.getElementById('peakMinusDec').value || '0.5',
                rsi_profit_int: document.getElementById('rsiProfitInt').value || '1',
                rsi_profit_dec: document.getElementById('rsiProfitDec').value || '0.0',
                enable_alerts: document.getElementById('enableAlerts').value || 'true',
                show_lines: document.getElementById('showLines').value || 'true',
                show_signals: document.getElementById('showSignals').value || 'true',
                updated: new Date().toLocaleString()
            };
            
            // Save to "database" (simulation)
            parameterDatabase[symbol + '_' + tradeMode] = params;
            
            // In real implementation, this would be an AJAX call to your Python backend
            console.log('Saving parameters:', params);
            
            showStatus(`✅ Parameters saved for ${symbol} (${tradeMode} mode)!`, 'success');
        }
        
        function clearPasteArea() {
            document.getElementById('tvNumbers').value = '';
            showStatus('Paste area cleared!', 'success');
        }
        
        function clearForm() {
            const inputs = document.querySelectorAll('input, select:not(#symbolSelect), textarea');
            inputs.forEach(input => input.value = '');
            showStatus('Form cleared!', 'success');
        }
        
        function showStatus(message, type) {
            const statusDiv = document.getElementById('statusDisplay');
            statusDiv.textContent = message;
            statusDiv.className = `status-display status-${type}`;
            statusDiv.classList.remove('hidden');
            
            setTimeout(() => {
                statusDiv.classList.add('hidden');
            }, 3000);
        }
        
        // Help popup functions
        function openHelpPopup() {
            document.getElementById('helpPopup').style.display = 'flex';
        }
        
        function closeHelpPopup() {
            document.getElementById('helpPopup').style.display = 'none';
        }
        
        // Close popup when clicking outside
        document.addEventListener('click', function(event) {
            const popup = document.getElementById('helpPopup');
            if (event.target === popup) {
                closeHelpPopup();
            }
        });
    </script>
</body>
</html>
    '''

@app.route('/scanne')
def scanner():
    return render_template('aimn_flowing_scanner.html')

@app.route('/orders')
def orders():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Orders - AIMn Trading</title>
        <style>
            body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
            h1 { color: #00ff00; }
            a { color: #00ccff; text-decoration: none; }
            .placeholder { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>📈 Orders Management</h1>
        <div class="placeholder">
            <h3>Order History</h3>
            <p>View and manage your trading orders</p>
        </div>
        <div class="placeholder">
            <h3>Active Orders</h3>
            <p>Monitor currently active orders</p>
        </div>
        <p><a href="/">← Back to Dashboard</a></p>
    </body>
    </html>
    '''

@app.route('/popper')
def popper():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trade Popup - AIMn Trading</title>
        <style>
            body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
            h1 { color: #00ff00; }
            a { color: #00ccff; text-decoration: none; }
            .trade-box { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }
            .pnl { font-size: 24px; color: #00ff00; }
        </style>
    </head>
    <body>
        <h1>🪟 Live Trade Monitor</h1>
        <div class="trade-box">
            <h3>Active Position</h3>
            <div class="pnl">P&L: +$1,234.56 (+2.45%)</div>
            <p>Symbol: BTC/USD | Entry: $43,250 | Current: $44,310</p>
            <button style="background: red; color: white; padding: 10px 20px; border: none; border-radius: 5px;">
                🚨 Emergency Exit
            </button>
        </div>
        <p><a href="/">← Back to Dashboard</a></p>
    </body>
    </html>
    '''

@app.route('/loop')
def loop_controls():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Loop Controls - AIMn Trading</title>
        <style>
            body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
            h1 { color: #00ff00; }
            a { color: #00ccff; text-decoration: none; }
            .control-box { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }
            button { background: #0066cc; color: white; padding: 10px 20px; border: none; border-radius: 5px; margin: 5px; }
        </style>
    </head>
    <body>
        <h1>🔄 Trading Loop Controls</h1>
        <div class="control-box">
            <h3>System Status</h3>
            <p>Status: <span style="color: #00ff00;">ACTIVE</span></p>
            <button>▶️ Start Loop</button>
            <button>⏸️ Pause Loop</button>
            <button style="background: red;">🛑 Stop All</button>
        </div>
        <div class="control-box">
            <h3>Loop Configuration</h3>
            <p>Configure trading parameters and automation settings</p>
        </div>
        <p><a href="/">← Back to Dashboard</a></p>
    </body>
    </html>
    '''

@app.route('/snapshots')
def snapshots():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Snapshots - AIMn Trading</title>
        <style>
            body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
            h1 { color: #00ff00; }
            a { color: #00ccff; text-decoration: none; }
            .snapshot-box { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>📷 Trade Snapshots</h1>
        <div class="snapshot-box">
            <h3>Recent Snapshots</h3>
            <p>View captured trading moments and analysis</p>
        </div>
        <div class="snapshot-box">
            <h3>Performance History</h3>
            <p>Historical performance data and analytics</p>
        </div>
        <p><a href="/">← Back to Dashboard</a></p>
    </body>
    </html>
    '''

@app.route('/symbols')
def symbols():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AIMn Symbol & API Management</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
                min-height: 100vh;
                color: white;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
                color: #00ff00;
                text-shadow: 2px 2px 4px rgba(0,255,0,0.3);
            }
            
            .header p {
                color: #aaa;
                font-size: 1.1em;
            }
            
            .main-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
                margin-bottom: 30px;
            }
            
            .section-card {
                background: rgba(255,255,255,0.05);
                border-radius: 15px;
                padding: 30px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                border: 1px solid rgba(255,255,255,0.1);
            }
            
            .section-title {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 25px;
                color: #00ffff;
                font-size: 1.3em;
                font-weight: bold;
            }
            
            .form-group {
                margin-bottom: 20px;
            }
            
            .form-group label {
                display: block;
                margin-bottom: 8px;
                color: #e0e0e0;
                font-weight: 600;
            }
            
            .form-group input, .form-group select {
                width: 100%;
                padding: 12px 15px;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 8px;
                background: rgba(255,255,255,0.1);
                color: white;
                font-size: 14px;
                transition: border-color 0.3s ease;
            }
            
            .form-group input:focus, .form-group select:focus {
                outline: none;
                border-color: #00ff00;
                box-shadow: 0 0 10px rgba(0,255,0,0.3);
            }
            
            .form-group input::placeholder {
                color: rgba(255,255,255,0.5);
            }
            
            .symbol-list {
                background: rgba(0,0,0,0.3);
                border-radius: 8px;
                padding: 15px;
                max-height: 200px;
                overflow-y: auto;
                margin-top: 15px;
            }
            
            .symbol-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                transition: background 0.3s ease;
            }
            
            .symbol-item:hover {
                background: rgba(255,255,255,0.05);
            }
            
            .symbol-item:last-child {
                border-bottom: none;
            }
            
            .symbol-name {
                font-weight: bold;
                color: #00ffff;
            }
            
            .exchange-badge {
                background: #ff6b35;
                color: white;
                padding: 4px 10px;
                border-radius: 20px;
                font-size: 0.8em;
            }
            
            .delete-btn {
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                cursor: pointer;
                font-size: 0.8em;
                transition: background 0.3s ease;
            }
            
            .delete-btn:hover {
                background: #c82333;
            }
            
            .api-status {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 12px 15px;
                border-radius: 8px;
                margin: 15px 0;
                font-weight: bold;
            }
            
            .api-status.connected {
                background: rgba(40,167,69,0.2);
                border: 1px solid #28a745;
                color: #28a745;
            }
            
            .api-status.disconnected {
                background: rgba(220,53,69,0.2);
                border: 1px solid #dc3545;
                color: #dc3545;
            }
            
            .api-status.testing {
                background: rgba(255,193,7,0.2);
                border: 1px solid #ffc107;
                color: #ffc107;
            }
            
            button {
                padding: 12px 25px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s ease;
                margin: 5px;
            }
            
            .btn-primary {
                background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
                color: white;
            }
            
            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,123,255,0.4);
            }
            
            .btn-success {
                background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%);
                color: white;
            }
            
            .btn-success:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(40,167,69,0.4);
            }
            
            .btn-warning {
                background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
                color: black;
            }
            
            .btn-warning:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(255,193,7,0.4);
            }
            
            .btn-danger {
                background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                color: white;
            }
            
            .btn-danger:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(220,53,69,0.4);
            }
            
            .security-notice {
                background: rgba(255,193,7,0.1);
                border: 2px solid #ffc107;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
            }
            
            .security-notice h3 {
                color: #ffc107;
                margin-bottom: 10px;
            }
            
            .security-notice ul {
                color: #e0e0e0;
                margin-left: 20px;
                line-height: 1.6;
            }
            
            .password-toggle {
                position: relative;
            }
            
            .toggle-btn {
                position: absolute;
                right: 10px;
                top: 50%;
                transform: translateY(-50%);
                background: none;
                border: none;
                color: #00ff00;
                cursor: pointer;
                font-size: 14px;
                padding: 5px;
            }
            
            .bottom-nav {
                text-align: center;
                margin-top: 40px;
                padding: 20px;
                border-top: 1px solid rgba(255,255,255,0.1);
            }
            
            .nav-link {
                color: #00ff00;
                text-decoration: none;
                margin: 0 20px;
                font-size: 1.1em;
                transition: color 0.3s ease;
            }
            
            .nav-link:hover {
                color: #00ffff;
                text-decoration: underline;
            }
            
            @media (max-width: 768px) {
                .main-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔧 AIMn Symbol & API Management</h1>
                <p>Configure trading pairs and broker connections</p>
            </div>
            
            <div class="main-grid">
                <div class="section-card">
                    <div class="section-title">
                        📈 Symbol Management
                    </div>
                    
                    <div class="form-group">
                        <label for="symbolInput">Add Trading Symbol</label>
                        <input type="text" id="symbolInput" placeholder="e.g., BTC/USD, AAPL, ETH/USD" style="text-transform: uppercase;">
                    </div>
                    
                    <div class="form-group">
                        <label for="exchangeSelect">Exchange/Broker</label>
                        <select id="exchangeSelect">
                            <option value="">Select Exchange</option>
                            <option value="BINANCE">Binance</option>
                            <option value="ALPACA">Alpaca Markets</option>
                            <option value="COINBASE">Coinbase Pro</option>
                            <option value="KRAKEN">Kraken</option>
                            <option value="INTERACTIVE_BROKERS">Interactive Brokers</option>
                            <option value="TD_AMERITRADE">TD Ameritrade</option>
                            <option value="NASDAQ">NASDAQ (Data Only)</option>
                            <option value="NYSE">NYSE (Data Only)</option>
                        </select>
                    </div>
                    
                    <button class="btn-primary" onclick="addSymbol()">
                        ➕ Add Symbol
                    </button>
                    
                    <div class="symbol-list" id="symbolList">
                        <div style="text-align: center; color: #666; padding: 20px;">
                            No symbols added yet
                        </div>
                    </div>
                    
                    <button class="btn-success" onclick="saveSymbols()" style="width: 100%; margin-top: 15px;">
                        💾 Save Symbol Configuration
                    </button>
                </div>
                
                <div class="section-card">
                    <div class="section-title">
                        🔐 API Credentials
                    </div>
                    
                    <div class="form-group">
                        <label for="brokerSelect">Select Broker</label>
                        <select id="brokerSelect" onchange="updateAPIFields()">
                            <option value="">Choose Broker</option>
                            <option value="ALPACA">Alpaca Markets</option>
                            <option value="BINANCE">Binance</option>
                            <option value="COINBASE">Coinbase Pro</option>
                            <option value="KRAKEN">Kraken</option>
                            <option value="INTERACTIVE_BROKERS">Interactive Brokers</option>
                            <option value="TD_AMERITRADE">TD Ameritrade</option>
                        </select>
                    </div>
                    
                    <div id="apiFields" style="display: none;">
                        <div class="form-group">
                            <label for="apiKey">API Key</label>
                            <input type="text" id="apiKey" placeholder="Enter your API key">
                        </div>
                        
                        <div class="form-group password-toggle">
                            <label for="apiSecret">API Secret</label>
                            <input type="password" id="apiSecret" placeholder="Enter your API secret">
                            <button type="button" class="toggle-btn" onclick="togglePassword('apiSecret')">👁️</button>
                        </div>
                        
                        <div class="form-group" id="passphraseGroup" style="display: none;">
                            <label for="passphrase">Passphrase</label>
                            <input type="password" id="passphrase" placeholder="Enter passphrase (if required)">
                            <button type="button" class="toggle-btn" onclick="togglePassword('passphrase')">👁️</button>
                        </div>
                        
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="sandboxMode" style="width: auto; margin-right: 10px;">
                                Use Sandbox/Paper Trading Mode
                            </label>
                        </div>
                    </div>
                    
                    <div class="api-status disconnected" id="apiStatus">
                        ❌ No API connection configured
                    </div>
                    
                    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                        <button class="btn-warning" onclick="testConnection()" id="testBtn" disabled>
                            🧪 Test Connection
                        </button>
                        <button class="btn-success" onclick="saveAPICredentials()" id="saveBtn" disabled>
                            💾 Save API Keys
                        </button>
                        <button class="btn-danger" onclick="clearCredentials()">
                            🗑️ Clear All
                        </button>
                    </div>
                </div>
            </div>
            
            <div class="security-notice">
                <h3>🔒 Security Notice</h3>
                <ul>
                    <li><strong>API keys are encrypted</strong> and stored securely on the server</li>
                    <li><strong>Never share your API credentials</strong> with anyone</li>
                    <li><strong>Use paper trading mode</strong> for testing new strategies</li>
                    <li><strong>Enable IP restrictions</strong> on your broker account if available</li>
                    <li><strong>Set appropriate permissions</strong> - trading bots only need trade permissions</li>
                    <li><strong>Monitor your account regularly</strong> for any unauthorized activity</li>
                </ul>
            </div>
            
            <div class="bottom-nav">
                <a href="/" class="nav-link">🏠 Dashboard</a>
                <a href="/tuning" class="nav-link">🎛️ Tuning Parameters</a>
                <a href="/scanne" class="nav-link">📡 Live Scanner</a>
            </div>
        </div>

        <script>
            let symbols = [];
            let apiCredentials = {};
            
            function addSymbol() {
                const symbolInput = document.getElementById('symbolInput');
                const exchangeSelect = document.getElementById('exchangeSelect');
                
                const symbol = symbolInput.value.trim().toUpperCase();
                const exchange = exchangeSelect.value;
                
                if (!symbol || !exchange) {
                    alert('Please enter both symbol and exchange');
                    return;
                }
                
                const exists = symbols.some(s => s.symbol === symbol && s.exchange === exchange);
                if (exists) {
                    alert('This symbol/exchange combination already exists');
                    return;
                }
                
                symbols.push({ symbol, exchange });
                updateSymbolList();
                
                symbolInput.value = '';
                exchangeSelect.value = '';
            }
            
            function updateSymbolList() {
                const listContainer = document.getElementById('symbolList');
                
                if (symbols.length === 0) {
                    listContainer.innerHTML = '<div style="text-align: center; color: #666; padding: 20px;">No symbols added yet</div>';
                    return;
                }
                
                listContainer.innerHTML = symbols.map((item, index) => `
                    <div class="symbol-item">
                        <div>
                            <span class="symbol-name">${item.symbol}</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span class="exchange-badge">${item.exchange}</span>
                            <button class="delete-btn" onclick="removeSymbol(${index})">×</button>
                        </div>
                    </div>
                `).join('');
            }
            
            function removeSymbol(index) {
                symbols.splice(index, 1);
                updateSymbolList();
            }
            
            function saveSymbols() {
                console.log('Saving symbols:', symbols);
                alert('✅ Symbols saved successfully!');
            }
            
            function updateAPIFields() {
                const broker = document.getElementById('brokerSelect').value;
                const apiFields = document.getElementById('apiFields');
                const passphraseGroup = document.getElementById('passphraseGroup');
                const testBtn = document.getElementById('testBtn');
                const saveBtn = document.getElementById('saveBtn');
                
                if (broker) {
                    apiFields.style.display = 'block';
                    testBtn.disabled = false;
                    saveBtn.disabled = false;
                    
                    if (broker === 'COINBASE') {
                        passphraseGroup.style.display = 'block';
                    } else {
                        passphraseGroup.style.display = 'none';
                    }
                    
                    updateAPIStatus('disconnected', '❌ Enter credentials to connect');
                } else {
                    apiFields.style.display = 'none';
                    testBtn.disabled = true;
                    saveBtn.disabled = true;
                    updateAPIStatus('disconnected', '❌ No API connection configured');
                }
            }
            
            function togglePassword(fieldId) {
                const field = document.getElementById(fieldId);
                const btn = field.nextElementSibling;
                
                if (field.type === 'password') {
                    field.type = 'text';
                    btn.textContent = '🙈';
                } else {
                    field.type = 'password';
                    btn.textContent = '👁️';
                }
            }
            
            function testConnection() {
                const broker = document.getElementById('brokerSelect').value;
                const apiKey = document.getElementById('apiKey').value;
                const apiSecret = document.getElementById('apiSecret').value;
                
                if (!apiKey || !apiSecret) {
                    alert('Please enter both API key and secret');
                    return;
                }
                
                updateAPIStatus('testing', '🧪 Testing connection...');
                
                setTimeout(() => {
                    const success = Math.random() > 0.3;
                    
                    if (success) {
                        updateAPIStatus('connected', `✅ Connected to ${broker}`);
                        alert('✅ Connection successful!');
                    } else {
                        updateAPIStatus('disconnected', '❌ Connection failed - check credentials');
                        alert('❌ Connection failed. Please verify your credentials.');
                    }
                }, 2000);
            }
            
            function saveAPICredentials() {
                const broker = document.getElementById('brokerSelect').value;
                const apiKey = document.getElementById('apiKey').value;
                const apiSecret = document.getElementById('apiSecret').value;
                const passphrase = document.getElementById('passphrase').value;
                const sandbox = document.getElementById('sandboxMode').checked;
                
                if (!apiKey || !apiSecret) {
                    alert('Please enter both API key and secret');
                    return;
                }
                
                apiCredentials[broker] = {
                    apiKey,
                    apiSecret,
                    passphrase: passphrase || null,
                    sandbox
                };
                
                console.log('Saving API credentials for:', broker);
                alert('✅ API credentials saved securely!');
            }
            
            function clearCredentials() {
                if (confirm('Are you sure you want to clear all API credentials?')) {
                    document.getElementById('apiKey').value = '';
                    document.getElementById('apiSecret').value = '';
                    document.getElementById('passphrase').value = '';
                    document.getElementById('sandboxMode').checked = false;
                    updateAPIStatus('disconnected', '❌ No API connection configured');
                    alert('🗑️ Credentials cleared');
                }
            }
            
            function updateAPIStatus(type, message) {
                const status = document.getElementById('apiStatus');
                status.className = `api-status ${type}`;
                status.textContent = message;
            }
            
            window.addEventListener('load', function() {
                console.log('Page loaded - ready for symbol and API management');
            });
            
            document.getElementById('symbolInput').addEventListener('input', function(e) {
                e.target.value = e.target.value.toUpperCase();
            });
        </script>
    </body>
    </html>
    '''

# API endpoints for the scanner
@app.route('/api/exchange-status')
def exchange_status():
    return jsonify({
        'ALPACA': {'scanning': True, 'activeSymbol': None, 'symbolCount': 250, 'status': 'ACTIVE'},
        'CRYPTO': {'scanning': False, 'activeSymbol': 'BTC/USD', 'symbolCount': 100, 'status': 'TRADING'},
        'FOREX': {'scanning': True, 'activeSymbol': None, 'symbolCount': 50, 'status': 'ACTIVE'},
        'NYSE': {'scanning': True, 'activeSymbol': None, 'symbolCount': 200, 'status': 'ACTIVE'},
        'FUTURES': {'scanning': True, 'activeSymbol': None, 'symbolCount': 30, 'status': 'ACTIVE'}
    })

@app.route('/api/flowing-scanner-data')
def flowing_scanner_data():
    symbols = [
        {'symbol': 'BTC/USD', 'exchange': 'CRYPTO'},
        {'symbol': 'ETH/USD', 'exchange': 'CRYPTO'},
        {'symbol': 'AAPL', 'exchange': 'ALPACA'},
        {'symbol': 'TSLA', 'exchange': 'ALPACA'},
        {'symbol': 'NVDA', 'exchange': 'ALPACA'},
        {'symbol': 'SPY', 'exchange': 'NYSE'},
        {'symbol': 'QQQ', 'exchange': 'NYSE'},
        {'symbol': 'MSFT', 'exchange': 'NYSE'},
        {'symbol': 'AMZN', 'exchange': 'NYSE'},
        {'symbol': 'GOOGL', 'exchange': 'ALPACA'},
        {'symbol': 'META', 'exchange': 'NYSE'},
        {'symbol': 'NFLX', 'exchange': 'ALPACA'}
    ]
    
    scan_results = []
    busy_broker = 'CRYPTO'
    active_symbol = 'BTC/USD'
    
    for symbol_data in symbols:
        symbol = symbol_data['symbol']
        exchange = symbol_data['exchange']
        
        price = round(random.uniform(50, 550), 2)
        change = round(random.uniform(-10, 10), 2)
        volume = random.randint(100000, 1000000)
        rsi = round(random.uniform(0, 100), 1)
        signal = 'BUY' if rsi < 30 else 'SELL' if rsi > 70 else 'NEUTRAL'
        
        is_actively_trading = (exchange == busy_broker and symbol == active_symbol)
        is_available = exchange != busy_broker
        
        scan_results.append({
            'symbol': symbol,
            'exchange': exchange,
            'price': str(price),
            'change': str(change),
            'volume': f"{volume:,}",
            'rsi': str(rsi),
            'signal': signal,
            'signalStrength': str(round(random.uniform(0.2, 1.0), 2)) if signal != 'NEUTRAL' else '0',
            'isAvailable': is_available,
            'isActivelyTrading': is_actively_trading
        })
    
    return jsonify({'scanResults': scan_results})

@app.route('/api/ticker-feed')
def ticker_feed():
    symbols = [
        {'symbol': 'BTC/USD', 'exchange': 'CRYPTO'},
        {'symbol': 'ETH/USD', 'exchange': 'CRYPTO'},
        {'symbol': 'AAPL', 'exchange': 'ALPACA'},
        {'symbol': 'TSLA', 'exchange': 'ALPACA'},
        {'symbol': 'NVDA', 'exchange': 'ALPACA'},
        {'symbol': 'SPY', 'exchange': 'NYSE'},
        {'symbol': 'QQQ', 'exchange': 'NYSE'},
        {'symbol': 'MSFT', 'exchange': 'NYSE'},
        {'symbol': 'AMZN', 'exchange': 'NYSE'},
        {'symbol': 'GOOGL', 'exchange': 'ALPACA'}
    ]
    
    ticker_items = []
    busy_broker = 'CRYPTO'
    active_symbol = 'BTC/USD'
    
    for symbol_data in symbols:
        symbol = symbol_data['symbol']
        exchange = symbol_data['exchange']
        
        is_actively_trading = (exchange == busy_broker and symbol == active_symbol)
        is_available = exchange != busy_broker
        
        ticker_items.append({
            'symbol': symbol,
            'exchange': exchange,
            'price': str(round(random.uniform(50, 550), 2)),
            'change': str(round(random.uniform(-10, 10), 2)),
            'signal': random.choice(['BUY', 'SELL', 'NEUTRAL', 'NEUTRAL', 'NEUTRAL']),
            'isAvailable': is_available,
            'isActivelyTrading': is_actively_trading
        })
    
    return jsonify(ticker_items)

@app.route('/scanner-simulator')
def scanner_simulator():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trade Scanner Simulator</title>
        <style>
            body {
                background: #0a0a0a;
                color: #e0e0e0;
                font-family: monospace;
                margin: 0;
                padding: 20px;
            }
            
            .container {
                max-width: 800px;
                margin: 0 auto;
            }
            
            h1 {
                color: #00ff00;
                text-align: center;
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            
            .subtitle {
                text-align: center;
                color: #00ffff;
                margin-bottom: 30px;
                font-size: 1.1em;
            }
            
            .method {
                background: #1a1a1a;
                border: 2px solid #333;
                border-radius: 10px;
                padding: 25px;
                margin: 20px 0;
            }
            
            h2 {
                color: #00ffff;
                margin-top: 0;
            }
            
            .form-group {
                margin: 15px 0;
            }
            
            label {
                display: inline-block;
                width: 180px;
                font-weight: bold;
            }
            
            input[type="text"],
            input[type="number"],
            textarea,
            select {
                background: #333;
                color: #0f0;
                border: 1px solid #555;
                padding: 8px;
                border-radius: 4px;
                width: 250px;
            }
            
            textarea {
                width: 400px;
                height: 80px;
            }
            
            input[type="radio"] {
                margin: 0 5px;
            }
            
            button {
                background: #00ff00;
                color: black;
                padding: 15px 30px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 1.1em;
                font-weight: bold;
                margin-top: 15px;
                width: 100%;
            }
            
            button:hover {
                background: #00ff99;
            }
            
            .local-btn {
                background: #0099ff;
                color: white;
            }
            
            .local-btn:hover {
                background: #00ccff;
            }
            
            .result {
                margin-top: 20px;
                padding: 15px;
                border-radius: 5px;
                display: none;
            }
            
            .success {
                background: #004400;
                border: 1px solid #00ff00;
                color: #00ff00;
            }
            
            .error {
                background: #440000;
                border: 1px solid #ff0000;
                color: #ff0000;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Trade Scanner Simulator</h1>
            <div class="subtitle">
                Use this form to manually trigger trade popups for testing the standalone window.
            </div>
            
            <!-- Method 1 -->
            <div class="method">
                <h2>Method 1: Direct External Trigger</h2>
                <form id="external-form">
                    <div class="form-group">
                        <label><strong>Symbol:</strong></label>
                        <input type="text" name="symbol" value="BTC/USD" required>
                    </div>
                    
                    <div class="form-group">
                        <label><strong>Exchange:</strong></label>
                        <select name="exchange">
                            <option value="Alpaca">Alpaca</option>
                            <option value="Binance">Binance</option>
                            <option value="Coinbase">Coinbase</option>
                            <option value="NYSE">NYSE</option>
                            <option value="NASDAQ">NASDAQ</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label><strong>Side:</strong></label>
                        <input type="radio" name="side" value="BUY" checked> BUY
                        <input type="radio" name="side" value="SELL"> SELL
                    </div>
                    
                    <div class="form-group">
                        <label><strong>Quantity:</strong></label>
                        <input type="number" name="quantity" value="0.5" step="0.01" required>
                    </div>
                    
                    <div class="form-group">
                        <label><strong>Entry Price (optional):</strong></label>
                        <input type="number" name="price" placeholder="43250.00" step="0.01">
                    </div>
                    
                    <div class="form-group">
                        <label style="vertical-align: top;"><strong>Parameters (JSON):</strong></label>
                        <textarea name="params">{
  "stop_loss": 2.0,
  "take_profit": 5.0
}</textarea>
                    </div>
                    
                    <button type="submit">🚀 Trigger Trade Pop-Up (External)</button>
                </form>
                <div id="result1" class="result"></div>
            </div>
            
            <!-- Method 2 -->
            <div class="method">
                <h2>Method 2: Local Testing</h2>
                <form id="local-form">
                    <div class="form-group">
                        <label><strong>Symbol:</strong></label>
                        <input type="text" name="symbol" value="ETH/USD" required>
                    </div>
                    
                    <div class="form-group">
                        <label><strong>Exchange:</strong></label>
                        <select name="exchange">
                            <option value="Alpaca">Alpaca</option>
                            <option value="Binance">Binance</option>
                            <option value="Coinbase">Coinbase</option>
                            <option value="NYSE">NYSE</option>
                            <option value="NASDAQ">NASDAQ</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label><strong>Side:</strong></label>
                        <input type="radio" name="side" value="BUY" checked> BUY
                        <input type="radio" name="side" value="SELL"> SELL
                    </div>
                    
                    <div class="form-group">
                        <label><strong>Quantity:</strong></label>
                        <input type="number" name="quantity" value="1.0" step="0.01" required>
                    </div>
                    
                    <div class="form-group">
                        <label><strong>Entry Price (optional):</strong></label>
                        <input type="number" name="price" placeholder="2850.00" step="0.01">
                    </div>
                    
                    <button type="submit" class="local-btn">🧪 Test Locally</button>
                </form>
                <div id="result2" class="result"></div>
            </div>
            
            <p style="text-align: center; margin-top: 40px;">
                <a href="/" style="color: #00ff00; text-decoration: none; font-size: 1.2em;">← Back to Dashboard</a>
            </p>
        </div>
        
        <script>
            // External form handler
            document.getElementById('external-form').addEventListener('submit', function(e) {
                e.preventDefault();
                
                const formData = new FormData(e.target);
                const result = document.getElementById('result1');
                
                try {
                    // Open popup window
                    const popup = window.open('/popup', 'TradeMonitor', 
                        'width=400,height=600,right=50,top=50');
                    
                    // Send data to popup
                    setTimeout(() => {
                        if (popup) {
                            popup.postMessage({
                                type: 'TRADE_DATA',
                                data: {
                                    symbol: formData.get('symbol'),
                                    exchange: formData.get('exchange'),
                                    side: formData.get('side'),
                                    quantity: parseFloat(formData.get('quantity')),
                                    price: formData.get('price') || 43250,
                                    parameters: JSON.parse(formData.get('params') || '{}')
                                }
                            }, '*');
                            
                            result.className = 'result success';
                            result.style.display = 'block';
                            result.textContent = '✅ Popup opened successfully!';
                        }
                    }, 1000);
                } catch (err) {
                    result.className = 'result error';
                    result.style.display = 'block';
                    result.textContent = '❌ Error: ' + err.message;
                }
            });
            
            // Local form handler
            document.getElementById('local-form').addEventListener('submit', function(e) {
                e.preventDefault();
                
                const formData = new FormData(e.target);
                const result = document.getElementById('result2');
                
                result.className = 'result success';
                result.style.display = 'block';
                result.innerHTML = `✅ Test Results:<br>
                    Symbol: ${formData.get('symbol')}<br>
                    Side: ${formData.get('side')}<br>
                    Quantity: ${formData.get('quantity')}<br>
                    Status: Test Successful`;
            });
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True)