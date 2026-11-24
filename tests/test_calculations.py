"""Boundary tests for isolated fare and energy estimates."""

import unittest
from decimal import Decimal

from processor.calculations import estimate_energy_kwh, estimate_fare_usd


class FareTests(unittest.TestCase):
    def test_member_classic_rounds_positive_overage_up(self):
        self.assertEqual(estimate_fare_usd(45 * 60, "member", "classic_bike"), Decimal("0.00"))
        self.assertEqual(estimate_fare_usd(45 * 60 + 1, "member", "classic_bike"), Decimal("0.20"))
        self.assertEqual(estimate_fare_usd(46 * 60 + 1, "member", "classic_bike"), Decimal("0.40"))

    def test_casual_classic_base_and_overage(self):
        self.assertEqual(estimate_fare_usd(30 * 60, "casual", "classic_bike"), Decimal("4.50"))
        self.assertEqual(estimate_fare_usd(30 * 60 + 1, "casual", "classic_bike"), Decimal("4.80"))

    def test_ebike_surcharge_uses_exact_minutes_and_rounds_final_cents_half_up(self):
        self.assertEqual(estimate_fare_usd(60, "casual", "electric_bike"), Decimal("4.85"))
        self.assertEqual(estimate_fare_usd(60, "member", "electric_bike"), Decimal("0.25"))

    def test_invalid_fare_inputs_are_explicit(self):
        for duration in (-1, True, 2.5):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                estimate_fare_usd(duration, "member", "classic_bike")


class EnergyTests(unittest.TestCase):
    def test_classic_energy_is_zero_even_without_coordinates(self):
        self.assertEqual(estimate_energy_kwh({"rideable_type": "classic_bike"}), Decimal("0"))

    def test_missing_ebike_coordinates_remain_unknown(self):
        self.assertIsNone(estimate_energy_kwh({"rideable_type": "electric_bike"}))

    def test_ebike_coordinates_produce_nonnegative_energy(self):
        event = {
            "rideable_type": "electric_bike",
            "start_lat": 40.7,
            "start_lng": -74.0,
            "end_lat": 40.71,
            "end_lng": -74.0,
        }
        energy = estimate_energy_kwh(event)
        self.assertIsNotNone(energy)
        self.assertGreater(energy, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
