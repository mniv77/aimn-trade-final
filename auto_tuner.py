# auto_tuner.py
import json
import pandas as pd
from collections import defaultdict

def analyze_trades():
    """Analyze trade history and suggest parameter improvements"""
    
    # Load trades
    with open('aimn_trades.json', 'r') as f:
        trades = [json.loads(line) for line in f.readlines()]
    
    # Convert to DataFrame
    df = pd.DataFrame(trades)
    
    # Analysis by symbol
    print("=== TRADE ANALYSIS ===\n")
    
    symbol_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_pnl': 0, 'trades': 0})
    
    for _, trade in df.iterrows():
        symbol = trade['symbol']
        symbol_stats[symbol]['trades'] += 1
        symbol_stats[symbol]['total_pnl'] += trade['pnl']
        
        if trade['exit_code'] == 'R':
            symbol_stats[symbol]['wins'] += 1
        else:
            symbol_stats[symbol]['losses'] += 1
    
    # Print symbol performance
    print("Symbol Performance:")
    print(f"{'Symbol':<12} {'Trades':<8} {'Wins':<6} {'Win%':<8} {'Total PnL':<12}")
    print("-" * 50)
    
    for symbol, stats in sorted(symbol_stats.items(), key=lambda x: x[1]['total_pnl'], reverse=True):
        win_rate = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
        print(f"{symbol:<12} {stats['trades']:<8} {stats['wins']:<6} {win_rate:<8.1f} ${stats['total_pnl']:<12.2f}")
    
    # Overall statistics
    total_trades = len(df)
    winning_trades = len(df[df['exit_code'] == 'R'])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    avg_win = df[df['exit_code'] == 'R']['pnl_pct'].mean() if winning_trades > 0 else 0
    avg_loss = df[df['exit_code'] == 'S']['pnl_pct'].mean() if (total_trades - winning_trades) > 0 else 0
    
    print(f"\n=== OVERALL STATS ===")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Average Win: {avg_win:.2f}%")
    print(f"Average Loss: {avg_loss:.2f}%")
    print(f"Total PnL: ${df['pnl'].sum():.2f}")
    
    # Generate recommendations
    print(f"\n=== AUTO-TUNING RECOMMENDATIONS ===")
    
    # If losses are bigger than wins, suggest tighter stops
    if abs(avg_loss) > avg_win:
        print("⚠️  Losses are bigger than wins!")
        print(f"   Suggestion: Reduce stop loss from 2% to {abs(avg_loss) * 0.75:.1f}%")
    
    # If win rate is high but profits low, suggest larger targets
    if win_rate > 60 and avg_win < 1:
        print("📈 High win rate but small wins!")
        print("   Suggestion: Increase RSI exit level from 70 to 75")
    
    # Best performing symbols
    best_symbols = [s for s, stats in symbol_stats.items() if stats['total_pnl'] > 0]
    print(f"\n✅ Focus on these profitable symbols: {', '.join(best_symbols[:3])}")
    
    # Worst performing
    worst_symbols = [s for s, stats in symbol_stats.items() if stats['total_pnl'] < -50]
    if worst_symbols:
        print(f"❌ Consider removing: {', '.join(worst_symbols)}")
    
    # Generate optimized config
    print("\n=== OPTIMIZED PARAMETERS ===")
    print("Add these to your config.py:")
    print("""
OPTIMIZED_PARAMS = {
    'rsi_window': 100,
    'rsi_oversold': 32,      # Slightly higher for more signals
    'rsi_overbought': 75,    # Higher to let winners run
    'stop_loss_pct': 1.5,    # Tighter stops
    'take_profit_pct': 2.0,  # Larger targets
    'volume_threshold': 0.85  # Slightly lower for more opportunities
}
    """)
    
    # Time analysis
    df['entry_hour'] = pd.to_datetime(df['entry_time']).dt.hour
    best_hours = df.groupby('entry_hour')['pnl'].sum().sort_values(ascending=False).head(3)
    
    print(f"\n🕐 Best trading hours (UTC): {list(best_hours.index)}")

if __name__ == "__main__":
    analyze_trades()