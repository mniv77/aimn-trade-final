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
                max-width: 1600px;
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
                    <div class="nav-card">
                        <a href="/trader-guide">📚 Trader Guide</a>
                        <div class="nav-desc">Simple explanation for experienced traders</div>
                    </div>
                    <div class="nav-card">
                        <a href="/beginner-guide">🎓 System Overview</a>
                        <div class="nav-desc">Architectural analysis for non-traders</div>
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

@app.route('/trader-guide')
def trader_guide():
    """Serve the Simple Explanation for Traders"""
    file_path = '/home/MeirNiv/aimn-trade-final/doc/Simple Explanation.html'
    
    try:
        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Trader Guide - AIMn Trading</title>
                <style>
                    body { 
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
                        color: white; 
                        padding: 40px 20px;
                        text-align: center;
                    }
                    .container {
                        max-width: 800px;
                        margin: 0 auto;
                        background: rgba(255,255,255,0.05);
                        border-radius: 15px;
                        padding: 40px;
                        backdrop-filter: blur(10px);
                        border: 1px solid rgba(0,255,0,0.3);
                    }
                    h1 { 
                        color: #00ff00; 
                        font-size: 2.5em;
                        margin-bottom: 20px;
                        text-shadow: 0 0 20px rgba(0,255,0,0.5);
                    }
                    .error { 
                        background: rgba(255,0,0,0.1); 
                        border: 1px solid #ff6b6b;
                        padding: 20px; 
                        border-radius: 10px; 
                        margin: 20px 0;
                        color: #ff6b6b;
                    }
                    a { 
                        color: #00ff00; 
                        text-decoration: none; 
                        font-size: 1.2em;
                        background: rgba(0,255,0,0.1);
                        padding: 12px 25px;
                        border-radius: 8px;
                        border: 1px solid #00ff00;
                        display: inline-block;
                        margin-top: 20px;
                        transition: all 0.3s ease;
                    }
                    a:hover {
                        background: rgba(0,255,0,0.2);
                        box-shadow: 0 5px 15px rgba(0,255,0,0.3);
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>📚 Trader Guide</h1>
                    <div class="error">
                        <h3>⚠️ File Not Found</h3>
                        <p>Simple Explanation.html could not be located.</p>
                        <p>Expected: /home/MeirNiv/aimn-trade-final/doc/Simple Explanation.html</p>
                    </div>
                    <a href="/">← Back to Dashboard</a>
                </div>
            </body>
            </html>
            '''
    except Exception as e:
        return f'''Error loading trader guide: {str(e)}'''

@app.route('/beginner-guide')
def beginner_guide():
    """Serve the Architectural Analysis for Non-Traders"""
    file_path = '/home/MeirNiv/aimn-trade-final/doc/Architectural Analysis and Trading Philosophy.html'
    
    try:
        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>System Overview - AIMn Trading</title>
                <style>
                    body { 
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
                        color: white; 
                        padding: 40px 20px;
                        text-align: center;
                    }
                    .container {
                        max-width: 800px;
                        margin: 0 auto;
                        background: rgba(255,255,255,0.05);
                        border-radius: 15px;
                        padding: 40px;
                        backdrop-filter: blur(10px);
                        border: 1px solid rgba(0,255,0,0.3);
                    }
                    h1 { 
                        color: #00ff00; 
                        font-size: 2.5em;
                        margin-bottom: 20px;
                        text-shadow: 0 0 20px rgba(0,255,0,0.5);
                    }
                    .error { 
                        background: rgba(255,0,0,0.1); 
                        border: 1px solid #ff6b6b;
                        padding: 20px; 
                        border-radius: 10px; 
                        margin: 20px 0;
                        color: #ff6b6b;
                    }
                    a { 
                        color: #00ff00; 
                        text-decoration: none; 
                        font-size: 1.2em;
                        background: rgba(0,255,0,0.1);
                        padding: 12px 25px;
                        border-radius: 8px;
                        border: 1px solid #00ff00;
                        display: inline-block;
                        margin-top: 20px;
                        transition: all 0.3s ease;
                    }
                    a:hover {
                        background: rgba(0,255,0,0.2);
                        box-shadow: 0 5px 15px rgba(0,255,0,0.3);
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🎓 System Overview</h1>
                    <div class="error">
                        <h3>⚠️ File Not Found</h3>
                        <p>Architectural Analysis and Trading Philosophy.html could not be located.</p>
                        <p>Expected: /home/MeirNiv/aimn-trade-final/doc/Architectural Analysis and Trading Philosophy.html</p>
                    </div>
                    <a href="/">← Back to Dashboard</a>
                </div>
            </body>
            </html>
            '''
    except Exception as e:
        return f'''Error loading system overview: {str(e)}'''

# CLEAN TUNING ROUTE - THIS IS THE FIX!
@app.route('/tuning')
def tuning_parameters():
    return render_template('tuning.html')

@app.route('/scanner/debug')
def scanner_debug():
    return render_template('aimn_scanner_debug.html')

@app.route('/scanne')
def scanner():
    return render_template('aimn_flowing_scanner.html')

@app.route('/orders')
def orders():
    return '''<!DOCTYPE html>
<html><head><title>Orders - AIMn Trading</title>
<style>body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
h1 { color: #00ff00; } a { color: #00ccff; text-decoration: none; }
.placeholder { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }</style>
</head><body><h1>📈 Orders Management</h1>
<div class="placeholder"><h3>Order History</h3><p>View and manage your trading orders</p></div>
<div class="placeholder"><h3>Active Orders</h3><p>Monitor currently active orders</p></div>
<p><a href="/">← Back to Dashboard</a></p></body></html>'''

@app.route('/popper')
def popper():
    return '''<!DOCTYPE html>
<html><head><title>Trade Popup - AIMn Trading</title>
<style>body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
h1 { color: #00ff00; } a { color: #00ccff; text-decoration: none; }
.trade-box { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }
.pnl { font-size: 24px; color: #00ff00; }</style>
</head><body><h1>🪟 Live Trade Monitor</h1>
<div class="trade-box"><h3>Active Position</h3>
<div class="pnl">P&L: +$1,234.56 (+2.45%)</div>
<p>Symbol: BTC/USD | Entry: $43,250 | Current: $44,310</p>
<button style="background: red; color: white; padding: 10px 20px; border: none; border-radius: 5px;">🚨 Emergency Exit</button></div>
<p><a href="/">← Back to Dashboard</a></p></body></html>'''

@app.route('/loop')
def loop_controls():
    return '''<!DOCTYPE html>
<html><head><title>Loop Controls - AIMn Trading</title>
<style>body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
h1 { color: #00ff00; } a { color: #00ccff; text-decoration: none; }
.control-box { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }
button { background: #0066cc; color: white; padding: 10px 20px; border: none; border-radius: 5px; margin: 5px; }</style>
</head><body><h1>🔄 Trading Loop Controls</h1>
<div class="control-box"><h3>System Status</h3>
<p>Status: <span style="color: #00ff00;">ACTIVE</span></p>
<button>▶️ Start Loop</button><button>⏸️ Pause Loop</button>
<button style="background: red;">🛑 Stop All</button></div>
<p><a href="/">← Back to Dashboard</a></p></body></html>'''

@app.route('/snapshots')
def snapshots():
    return '''<!DOCTYPE html>
<html><head><title>Snapshots - AIMn Trading</title>
<style>body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
h1 { color: #00ff00; } a { color: #00ccff; text-decoration: none; }
.snapshot-box { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }</style>
</head><body><h1>📷 Trade Snapshots</h1>
<div class="snapshot-box"><h3>Recent Snapshots</h3><p>View captured trading moments and analysis</p></div>
<div class="snapshot-box"><h3>Performance History</h3><p>Historical performance data and analytics</p></div>
<p><a href="/">← Back to Dashboard</a></p></body></html>'''

@app.route('/symbols')
def symbols():
    return '''<!DOCTYPE html>
<html><head><title>Symbol & API Management - AIMn Trading</title>
<style>body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; padding: 20px; }
h1 { color: #00ff00; } a { color: #00ccff; text-decoration: none; }
.config-box { background: #333; padding: 20px; border-radius: 5px; margin: 20px 0; }</style>
</head><body><h1>🔧 Symbol & API Management</h1>
<div class="config-box"><h3>Trading Symbols</h3><p>Configure trading pairs and symbols</p></div>
<div class="config-box"><h3>API Credentials</h3><p>Set up broker API connections</p></div>
<p><a href="/">← Back to Dashboard</a></p></body></html>'''

@app.route('/scanner-simulator')
def scanner_simulator():
    return '''<!DOCTYPE html>
<html><head><title>Trade Scanner Simulator</title>
<style>body { background: #0a0a0a; color: #e0e0e0; font-family: monospace; margin: 0; padding: 20px; }
h1 { color: #00ff00; text-align: center; font-size: 2.5em; margin-bottom: 30px; }
.simulator-box { background: #1a1a1a; border: 2px solid #333; border-radius: 10px; padding: 25px; margin: 20px 0; }
button { background: #00ff00; color: black; padding: 15px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 1.1em; font-weight: bold; margin-top: 15px; width: 100%; }</style>
</head><body><h1>Trade Scanner Simulator</h1>
<div class="simulator-box"><h3>Manual Trade Testing</h3><p>Use this form to manually trigger trade popups for testing.</p>
<button onclick="alert('Trade popup triggered!')">🚀 Trigger Test Trade</button></div>
<p style="text-align: center; margin-top: 40px;"><a href="/" style="color: #00ff00; text-decoration: none; font-size: 1.2em;">← Back to Dashboard</a></p></body></html>'''

# API endpoints
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

if __name__ == '__main__':
    app.run(debug=True)