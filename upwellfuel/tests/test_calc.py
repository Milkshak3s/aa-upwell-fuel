"""Tests for the fuel arithmetic.

These exercise the pure functions only, so they run without Django, a database
or an Alliance Auth installation:

    python -m unittest discover upwellfuel/tests
"""

import unittest

from upwellfuel.fuel.calc import (
    RATE_SOURCE_MEASURED,
    RATE_SOURCE_MODELLED,
    RATE_SOURCE_UNKNOWN,
    measured_rate_per_hour,
    modelled_rate_per_hour,
    project,
    project_consumable,
)


class MeasuredRateTest(unittest.TestCase):
    def test_derives_rate_from_bay_and_expiry(self):
        # 1200 blocks burning over 170 hours, less the truncation correction.
        rate = measured_rate_per_hour(1200, 170)
        self.assertAlmostEqual(rate, 1200 / 170.5, places=6)

    def test_correction_cancels_the_expiry_truncation_bias(self):
        # A citadel clone bay burns exactly 7/h. ESI truncates the expiry to the
        # hour, so a naive division reads high; the correction pulls it back.
        blocks = 1200
        true_hours = 1200 / 7
        naive = blocks / (true_hours - 0.5)
        corrected = measured_rate_per_hour(blocks, true_hours - 0.5)
        self.assertGreater(naive, 7.0)
        self.assertAlmostEqual(corrected, 7.0, places=6)

    def test_returns_none_without_usable_inputs(self):
        self.assertIsNone(measured_rate_per_hour(None, 100))
        self.assertIsNone(measured_rate_per_hour(0, 100))
        self.assertIsNone(measured_rate_per_hour(1000, None))
        self.assertIsNone(measured_rate_per_hour(1000, -10))


class ModelledRateTest(unittest.TestCase):
    """Every expectation here was checked against a live fleet's measured rates."""

    def test_engineering_complex_discounts_manufacturing(self):
        # Raitaru + Standup Manufacturing Plant I: 12/h base, -25% -> 9/h.
        self.assertAlmostEqual(modelled_rate_per_hour(35825, 1404, [35878]), 9.0)

    def test_engineering_complex_does_not_discount_a_clone_bay(self):
        # Sotiyo running industry plus a clone bay: the bay pays full freight.
        rate = modelled_rate_per_hour(35827, 1404, [35878, 35886, 45550, 35881, 35894])
        self.assertAlmostEqual(rate, (12 + 12 + 10 + 24) * 0.75 + 10)

    def test_refinery_discounts_reprocessing_but_not_moon_drilling(self):
        self.assertAlmostEqual(modelled_rate_per_hour(35835, 1406, [35899]), 8.0)
        self.assertAlmostEqual(modelled_rate_per_hour(35835, 1406, [45009]), 5.0)

    def test_tatara_discounts_more_deeply_than_athanor(self):
        athanor = modelled_rate_per_hour(35835, 1406, [35899])
        tatara = modelled_rate_per_hour(35836, 1406, [35899])
        self.assertAlmostEqual(athanor, 8.0)
        self.assertAlmostEqual(tatara, 7.5)

    def test_citadel_clone_bay_uses_the_measured_discount(self):
        # Dogma says -25% (7.5/h) but the game charges 7.0/h.
        self.assertAlmostEqual(modelled_rate_per_hour(35832, 1657, [35894]), 7.0)

    def test_citadel_discount_does_not_reach_reprocessing(self):
        self.assertAlmostEqual(modelled_rate_per_hour(35832, 1657, [35899]), 10.0)

    def test_jump_bridge_has_no_discount(self):
        self.assertAlmostEqual(modelled_rate_per_hour(35841, 1408, [35913]), 30.0)

    def test_unknown_modules_give_no_estimate(self):
        self.assertIsNone(modelled_rate_per_hour(35832, 1657, [999999]))
        self.assertIsNone(modelled_rate_per_hour(35832, 1657, []))


class ProjectionTest(unittest.TestCase):
    def test_deficit_is_burn_less_what_is_already_loaded(self):
        # 10/h for 30 days = 7200 blocks; 100 hours of fuel left = 1000 blocks.
        result = project(10.0, RATE_SOURCE_MEASURED, 30 * 24, hours_until_expiry=100)
        self.assertAlmostEqual(result.blocks_needed, 7200)
        self.assertAlmostEqual(result.blocks_remaining, 1000)
        self.assertAlmostEqual(result.blocks_to_buy, 6200)
        self.assertFalse(result.is_covered)

    def test_a_structure_fuelled_past_the_period_needs_nothing(self):
        result = project(10.0, RATE_SOURCE_MEASURED, 7 * 24, hours_until_expiry=500)
        self.assertEqual(result.blocks_to_buy, 0)
        self.assertTrue(result.is_covered)

    def test_unfuelled_structure_falls_back_to_the_counted_bay(self):
        result = project(
            10.0, RATE_SOURCE_MODELLED, 30 * 24, hours_until_expiry=None, blocks_counted=240
        )
        self.assertAlmostEqual(result.blocks_remaining, 240)
        self.assertAlmostEqual(result.hours_remaining, 24)
        self.assertAlmostEqual(result.blocks_to_buy, 7200 - 240)

    def test_no_rate_yields_an_unknown_projection(self):
        result = project(None, RATE_SOURCE_UNKNOWN, 30 * 24)
        self.assertEqual(result.rate_source, RATE_SOURCE_UNKNOWN)
        self.assertEqual(result.blocks_needed, 0)
        self.assertIsNone(result.rate_per_hour)

    def test_consumable_projection_matches_block_semantics(self):
        # A well stocked gas bay covers the month with nothing left to buy.
        result = project_consumable(100_000, 55.0, 30 * 24)
        self.assertAlmostEqual(result.blocks_needed, 55 * 720)
        self.assertEqual(result.blocks_to_buy, 0)
        self.assertTrue(result.is_covered)

    def test_consumable_shortfall_is_reported(self):
        result = project_consumable(10_000, 55.0, 30 * 24)
        self.assertAlmostEqual(result.blocks_to_buy, 55 * 720 - 10_000)


if __name__ == "__main__":
    unittest.main()
