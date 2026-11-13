import unittest

from kiss.ai_vision_offline_structure import assess_at, replay


def sample(count=240):
    bars = []
    for i in range(count):
        p = 200 - 0.3 * i
        if i >= 225:
            p += (i - 224) * 0.8
        bars.append({"unix": i * 300, "open": p, "high": p + 0.5,
                     "low": p - 0.5, "close": p})
    return bars


class OfflineStructureTests(unittest.TestCase):
    def test_major_short_local_long_recovery(self):
        result = assess_at(sample(), 239)
        self.assertEqual(result["major_trend"], "SHORT")
        self.assertEqual(result["local_trend"], "LONG")
        self.assertEqual(result["local_transition_type"], "COUNTERTREND_RECOVERY")

    def test_future_candles_cannot_change_past_judgment(self):
        rows = sample()
        earlier = assess_at(rows, 220)
        for row in rows[221:]:
            row["high"] += 1000
            row["low"] -= 1000
            row["close"] += 100
        self.assertEqual(earlier, assess_at(rows, 220))

    def test_replay_contains_no_trades(self):
        result = replay(sample(), [219, 229, 239])
        self.assertEqual(len(result["assessments"]), 3)
        self.assertNotIn("trades", result)

    def test_uncertain_on_short_history(self):
        result = assess_at(sample(), 50)
        self.assertEqual(result["major_trend"], "UNCERTAIN")


if __name__ == "__main__":
    unittest.main()
