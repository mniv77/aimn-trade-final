import unittest
from kiss.ai_vision_horizon_comparison import compare


def candles(n=500):
    return [{"unix": i * 300, "open": 200-i*.1, "high": 201-i*.1,
             "low": 199-i*.1, "close": 200-i*.1} for i in range(n)]


class HorizonTests(unittest.TestCase):
    def test_same_cutoff_across_horizons(self):
        result = compare(candles(), [450], horizons=(40, 100, 200))
        case = result["cases"][0]
        self.assertEqual(len(case["horizons"]), 3)
        self.assertEqual(case["cutoff_unix"], 450 * 300)
        self.assertTrue(all(x["major_trend"] == "SHORT" for x in case["horizons"]))

    def test_future_changes_do_not_affect_past(self):
        rows = candles()
        earlier = compare(rows, [450], horizons=(40, 100))
        rows[451]["high"] += 10000
        self.assertEqual(earlier, compare(rows, [450], horizons=(40, 100)))

    def test_disagreement_count(self):
        result = compare(candles(), [450, 460], horizons=(40, 100))
        self.assertEqual(result["disagreement_count"], 0)


if __name__ == "__main__":
    unittest.main()
