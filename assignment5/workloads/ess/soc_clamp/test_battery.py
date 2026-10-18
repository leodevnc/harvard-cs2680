import unittest
from battery import *
class TestBattery(unittest.TestCase):
    def test_behavior(self):
        self.assertEqual(clamp(-2),0)
        self.assertEqual(clamp(52),52)
        self.assertEqual(clamp(103),100)
