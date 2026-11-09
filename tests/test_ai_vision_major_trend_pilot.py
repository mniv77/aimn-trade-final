import unittest

from kiss.ai_vision_major_trend_pilot import select_indices


class PilotSelectionTests(unittest.TestCase):
    def test_five_spaced_cutoffs_are_deterministic(self):
        indices = select_indices(4680, warmup=500, samples=5)
        self.assertEqual(len(indices), 5)
        self.assertEqual(indices[0], 499)
        self.assertEqual(indices[-1], 4678)
        self.assertEqual(indices, sorted(set(indices)))

    def test_no_future_candle_assessed(self):
        indices = select_indices(501, warmup=500, samples=1)
        self.assertEqual(indices, [499])

    def test_rejects_short_history(self):
        with self.assertRaises(ValueError):
            select_indices(300, warmup=500)


if __name__ == "__main__":
    unittest.main()
