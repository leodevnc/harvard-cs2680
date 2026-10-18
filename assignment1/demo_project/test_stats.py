import unittest
from stats import mean


class MeanTest(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(mean([2, 4, 6]), 4)

    def test_single(self):
        self.assertEqual(mean([8]), 8)

    def test_empty(self):
        with self.assertRaises(ValueError):
            mean([])
