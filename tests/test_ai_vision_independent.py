"""Offline checks: no model calls, no live orders."""
import unittest
from kiss.ai_vision_independent import packet, run

class VisionRunnerTests(unittest.TestCase):
    def test_next_open_execution_and_independent_pnl(self):
        rows = [
            {"unix": 100, "open": 100, "high": 101, "low": 99, "close": 100},
            {"unix": 400, "open": 99, "high": 100, "low": 98, "close": 99},
            {"unix": 700, "open": 98, "high": 99, "low": 97, "close": 98},
            {"unix": 1000, "open": 97, "high": 98, "low": 96, "close": 97},
            {"unix": 1300, "open": 96, "high": 97, "low": 95, "close": 96},
        ]
        actions = iter(["ENTER SHORT", "EXIT SHORT"])
        def assessor(p):
            return {"symbol": "NVDA", "research_direction": "SHORT",
                    "last_visible_candle_unix": p["last_visible_candle_unix"],
                    "decision": next(actions), "confidence": "Moderate",
                    "reason": "Test", "notes": "No live orders."}
        result = run(rows, assessor, warmup=1, step=2, commission_pct=0.1)
        self.assertEqual(len(result["trades"]), 1)
        trade = result["trades"][0]
        self.assertEqual(trade["entry_price"], 99)
        self.assertEqual(trade["exit_price"], 96)
        self.assertEqual(trade["entry_unix"], 400)
        self.assertEqual(trade["exit_unix"], 1300)
        self.assertAlmostEqual(trade["net_pnl_pct"], (99-96)/99*100-0.2, places=5)

    def test_packet_never_sees_future(self):
        rows = [{"unix": i*300, "open": i+1, "high": i+2, "low": i, "close": i+1} for i in range(5)]
        p = packet(rows, 2, "NVDA", "SHORT", None, 2)
        self.assertEqual([r["unix"] for r in p["visible_ohlc"]], [300, 600])
        self.assertEqual(p["visible_count"], 3)

if __name__ == "__main__":
    unittest.main()
