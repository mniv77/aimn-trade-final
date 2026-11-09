import unittest

from kiss.ai_vision_major_trend_research import assess_at, pilot


def candles(n=130):
    return [{"unix": i * 300, "open": 100, "high": 101,
             "low": 99, "close": 100} for i in range(n)]


def assessor(packet):
    return {
        "last_visible_candle_unix": packet["last_visible_candle_unix"],
        "major_trend": "SHORT",
        "local_trend": "LONG",
        "local_transition_type": "COUNTERTREND_RECOVERY",
        "major_trend_confidence": "Moderate",
        "major_trend_evidence": "Older highs are lower.",
        "major_reversal_evidence": "No confirmed higher high."
    }


class MajorTrendTests(unittest.TestCase):
    def test_separate_major_and_local_trends(self):
        result = assess_at(candles(), 110, assessor)
        self.assertEqual(result["major_trend"], "SHORT")
        self.assertEqual(result["local_trend"], "LONG")
        self.assertEqual(result["local_transition_type"], "COUNTERTREND_RECOVERY")

    def test_reject_wrong_historical_cutoff(self):
        def wrong(packet):
            result = assessor(packet)
            result["last_visible_candle_unix"] += 300
            return result
        with self.assertRaisesRegex(ValueError, "mismatched"):
            assess_at(candles(), 110, wrong)

    def test_pilot_is_trade_free(self):
        result = pilot(candles(), assessor, [100, 110, 120])
        self.assertEqual(result["assessment_count"], 3)
        self.assertNotIn("trades", result)
        self.assertNotIn("realized_net_pnl_pct", result)


if __name__ == "__main__":
    unittest.main()
