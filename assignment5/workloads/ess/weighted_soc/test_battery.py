import unittest
from battery import *
class TestBattery(unittest.TestCase):
    def test_behavior(self):
        self.assertEqual(site_soc([20,80],[1,3]),65)
        self.assertEqual(site_soc([50,50],[1,1]),50)
