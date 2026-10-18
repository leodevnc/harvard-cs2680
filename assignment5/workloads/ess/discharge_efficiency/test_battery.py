import unittest
from battery import *
class TestBattery(unittest.TestCase):
    def test_behavior(self):
        self.assertEqual(deliverable(100,.9),90)
        self.assertEqual(deliverable(0,.9),0)
