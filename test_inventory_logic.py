"""Unit tests for the formulas, the load-cell model and the reorder logic.

Usage:  python -m unittest test_inventory_logic
"""
import math
import unittest

import config
from inventory_logic import (LoadCell, ReorderLogic, periodic_reorder_level,
                             reorder_point, safety_stock)

BOLT = config.ITEMS[0]


class FormulaTest(unittest.TestCase):
    def test_safety_stock(self):
        # SS = z * sigma_d * sqrt(L) = 1.65 * 45 * sqrt(5)
        self.assertAlmostEqual(safety_stock(BOLT), 1.65 * 45 * math.sqrt(5))

    def test_reorder_point(self):
        # ROP = d * L + SS = 180 * 5 + 166.0
        self.assertEqual(round(reorder_point(BOLT)), 1066)

    def test_periodic_level_higher_than_rop(self):
        self.assertGreater(periodic_reorder_level(BOLT, 5), reorder_point(BOLT))


class LoadCellTest(unittest.TestCase):
    def test_quantity_conversion(self):
        cell = LoadCell(BOLT, seed=1)
        self.assertEqual(cell.to_quantity(17.0 * 100), 100)
        self.assertEqual(cell.to_quantity(-3.0), 0)

    def test_measurement_error_small(self):
        cell = LoadCell(BOLT, seed=1)
        errors = [abs(cell.to_quantity(cell.measure(500)) - 500) for _ in range(200)]
        self.assertLessEqual(max(errors), 1)


class ReorderLogicTest(unittest.TestCase):
    def test_one_alert_per_cycle(self):
        logic = ReorderLogic(BOLT)
        self.assertEqual(logic.on_measurement(2000), 0)       # above ROP
        self.assertEqual(logic.on_measurement(1000), BOLT["Q"])  # reaches ROP
        self.assertEqual(logic.on_measurement(900), 0)        # order already open
        logic.on_delivery()
        self.assertEqual(logic.on_measurement(1050), BOLT["Q"])  # next cycle


if __name__ == "__main__":
    unittest.main()
