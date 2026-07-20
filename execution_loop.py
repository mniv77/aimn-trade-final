"""
AIV Execution Loop
"""

from scanner import AIMnScanner


class ExecutionLoop:

    def __init__(self, scanner: AIMnScanner):
        self.scanner = scanner

    def run_cycle(self, market_data: dict):

        results = []

        for symbol, df in market_data.items():

            exit_signal = self.scanner.get_exit_signal(df, symbol)
            if exit_signal:
                results.append({"symbol": symbol, "exit": exit_signal})
                continue

            scale_signal = self.scanner.check_profit_scaling(symbol, df)
            if scale_signal:
                results.append({"symbol": symbol, "scale": scale_signal})

            self.scanner.check_trailing_stop(symbol, df)

            trade = self.scanner.scan_symbol(symbol, df)
            if trade:
                results.append(trade)

        return results
