import unittest
from battery import *
class TestBattery(unittest.TestCase):
    def test_behavior(self):
        self.assertEqual(energy(100,1800),50)
        self.assertEqual(energy(0,100),0)
