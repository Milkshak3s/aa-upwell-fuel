"""Tests for the layer that turns aa-structures rows into projections.

build_report only ever reads attributes off the objects it is handed, so it can
be driven with stand-ins instead of a populated database. That keeps these tests
about this app's logic rather than about aa-structures' fixtures.
"""

import datetime as dt
from unittest.mock import patch

from django.test import TestCase
from django.utils.timezone import now

from upwellfuel.fuel import report as report_module
from upwellfuel.fuel.calc import RATE_SOURCE_MEASURED, RATE_SOURCE_MODELLED, RATE_SOURCE_UNKNOWN
from upwellfuel.fuel.report import build_report

ASTRAHUS = (35832, 1657, "Astrahus")
METENOX = (81826, 4744, "Metenox Moon Drill")
ANSIBLEX = (35841, 1408, "Ansiblex Jump Bridge")

CLONING_CENTER = 35894
REPROCESSING = 35899
METENOX_DRILL = 82941
OXYGEN_BLOCK = 4312


class _Item:
    def __init__(self, type_id, group_id, quantity, location_flag, last_updated_at=None):
        self.eve_type_id = type_id
        self.quantity = quantity
        self.location_flag = location_flag
        self.last_updated_at = last_updated_at
        self.eve_type = type("EveType", (), {"eve_group_id": group_id, "name": ""})()


class _Service:
    def __init__(self, name, state=2):
        self.name = name
        self.state = state


class _Related:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Structure:
    """Stands in for structures.Structure."""

    def __init__(self, hull, name="Test", fuel_expires_at=None, items=(), services=()):
        type_id, group_id, type_name = hull
        self.id = 1_000_000_000_001
        self.name = name
        self.eve_type_id = type_id
        self.eve_type = type(
            "EveType", (), {"eve_group_id": group_id, "name": type_name}
        )()
        self.fuel_expires_at = fuel_expires_at
        self.items = _Related(list(items))
        self.services = _Related(list(services))
        self.is_upwell_structure = True
        self.owner = type(
            "Owner", (), {"corporation": "Test Corp"}
        )()
        region = type("Region", (), {"name": "Test Region"})()
        constellation = type("Constellation", (), {"eve_region": region})()
        self.eve_solar_system = type(
            "System", (), {"name": "J000001", "eve_constellation": constellation}
        )()

    def get_power_mode_display(self):
        return "Full Power" if self.fuel_expires_at else "Abandoned"


def _fuelled_citadel(blocks=1200, hours_of_fuel=None):
    """An Astrahus running a clone bay, burning a known 7 blocks/hour."""
    hours_of_fuel = hours_of_fuel if hours_of_fuel is not None else blocks / 7
    synced_at = now()
    return _Structure(
        ASTRAHUS,
        name="Fuelled Citadel",
        fuel_expires_at=synced_at + dt.timedelta(hours=hours_of_fuel),
        items=[
            _Item(OXYGEN_BLOCK, 1136, blocks, "StructureFuel", synced_at),
            _Item(CLONING_CENTER, 1321, 1, "ServiceSlot0"),
        ],
        services=[_Service("Clone Bay")],
    )


class BuildReportTest(TestCase):
    def setUp(self):
        patcher = patch.object(report_module, "_market_prices", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_fuelled_structure_reports_a_measured_rate(self):
        report = build_report([_fuelled_citadel()], period_days=30, magmatic_gas_per_hour=55)
        row = report.rows[0]
        self.assertEqual(row.projection.rate_source, RATE_SOURCE_MEASURED)
        self.assertAlmostEqual(row.blocks_per_day, 168, delta=1)
        self.assertEqual(report.modelled_count, 0)

    def test_deficit_covers_the_period_beyond_current_fuel(self):
        report = build_report(
            [_fuelled_citadel(blocks=1200)], period_days=30, magmatic_gas_per_hour=55
        )
        row = report.rows[0]
        # 7/h for 30 days is 5040 blocks, of which 1200 are already loaded.
        self.assertAlmostEqual(row.projection.blocks_needed, 5040, delta=20)
        self.assertAlmostEqual(row.projection.blocks_to_buy, 3840, delta=20)

    def test_an_unfuelled_structure_is_costed_from_its_fitted_modules(self):
        """The case the modelled fallback exists for.

        A structure that has run dry reports every service offline, so the
        estimate has to come from what is fitted rather than what is running.
        """
        dry = _Structure(
            ASTRAHUS,
            name="Dry Citadel",
            fuel_expires_at=None,
            items=[_Item(CLONING_CENTER, 1321, 1, "ServiceSlot0")],
            services=[_Service("Clone Bay", state=1)],
        )
        report = build_report([dry], period_days=30, magmatic_gas_per_hour=55)
        row = report.rows[0]
        self.assertEqual(row.projection.rate_source, RATE_SOURCE_MODELLED)
        self.assertAlmostEqual(row.blocks_per_day, 168)
        self.assertAlmostEqual(row.projection.blocks_to_buy, 5040)
        self.assertEqual(report.modelled_count, 1)

    def test_a_structure_with_nothing_fitted_is_flagged_not_guessed(self):
        bare = _Structure(ASTRAHUS, name="Bare", fuel_expires_at=None)
        report = build_report([bare], period_days=30, magmatic_gas_per_hour=55)
        self.assertEqual(report.rows[0].projection.rate_source, RATE_SOURCE_UNKNOWN)
        self.assertEqual(report.unknown_count, 1)
        self.assertEqual(report.blocks_to_buy, 0)

    def test_only_online_services_are_charged_for(self):
        """A fitted but offline module burns nothing while others are running."""
        synced_at = now()
        structure = _Structure(
            ASTRAHUS,
            fuel_expires_at=None,
            items=[
                _Item(CLONING_CENTER, 1321, 1, "ServiceSlot0"),
                _Item(REPROCESSING, 1321, 1, "ServiceSlot1"),
            ],
            services=[_Service("Clone Bay"), _Service("Reprocessing", state=1)],
        )
        report = build_report([structure], period_days=1, magmatic_gas_per_hour=55)
        self.assertAlmostEqual(report.rows[0].blocks_per_day, 168)

    def test_metenox_gas_is_projected_separately(self):
        synced_at = now()
        metenox = _Structure(
            METENOX,
            name="Drill",
            fuel_expires_at=synced_at + dt.timedelta(hours=100),
            items=[
                _Item(OXYGEN_BLOCK, 1136, 500, "StructureFuel", synced_at),
                _Item(report_module.MAGMATIC_GAS_TYPE_ID, 4729, 10_000, "StructureFuel"),
                _Item(METENOX_DRILL, 1321, 1, "ServiceSlot0"),
            ],
            services=[_Service("Automatic Moon Drilling")],
        )
        report = build_report([metenox], period_days=30, magmatic_gas_per_hour=55)
        row = report.rows[0]
        self.assertIsNotNone(row.gas)
        self.assertAlmostEqual(row.gas.blocks_needed, 55 * 720)
        self.assertAlmostEqual(row.gas.blocks_to_buy, 55 * 720 - 10_000)
        self.assertAlmostEqual(report.gas_to_buy, 55 * 720 - 10_000)

    def test_ozone_is_reported_as_stock_for_jump_bridges_only(self):
        synced_at = now()
        ansiblex = _Structure(
            ANSIBLEX,
            fuel_expires_at=synced_at + dt.timedelta(hours=100),
            items=[
                _Item(OXYGEN_BLOCK, 1136, 3000, "StructureFuel", synced_at),
                _Item(report_module.LIQUID_OZONE_TYPE_ID, 423, 50_000, "StructureFuel"),
            ],
            services=[_Service("Jump Bridge Access")],
        )
        report = build_report(
            [ansiblex, _fuelled_citadel()], period_days=30, magmatic_gas_per_hour=55
        )
        by_type = {row.type_name: row for row in report.rows}
        self.assertEqual(by_type["Ansiblex Jump Bridge"].ozone_on_hand, 50_000)
        self.assertIsNone(by_type["Astrahus"].ozone_on_hand)

    def test_totals_are_grouped_by_corporation(self):
        report = build_report(
            [_fuelled_citadel(), _fuelled_citadel()],
            period_days=30,
            magmatic_gas_per_hour=55,
        )
        self.assertEqual(len(report.by_corporation), 1)
        self.assertEqual(report.by_corporation[0].structures, 2)
        self.assertAlmostEqual(
            report.blocks_needed, report.by_corporation[0].blocks_needed
        )

    def test_rows_are_ordered_by_urgency(self):
        urgent = _fuelled_citadel(blocks=200)
        urgent.name = "Urgent"
        comfortable = _fuelled_citadel(blocks=20_000)
        comfortable.name = "Comfortable"
        report = build_report(
            [comfortable, urgent], period_days=30, magmatic_gas_per_hour=55
        )
        self.assertEqual([row.name for row in report.rows], ["Urgent", "Comfortable"])

    def test_isk_is_costed_when_prices_are_available(self):
        with patch.object(
            report_module, "_market_prices", return_value={OXYGEN_BLOCK: 20.0}
        ):
            report = build_report(
                [_fuelled_citadel(blocks=1200)], period_days=30, magmatic_gas_per_hour=55
            )
        row = report.rows[0]
        self.assertTrue(report.has_prices)
        self.assertAlmostEqual(row.isk_to_buy, row.projection.blocks_to_buy * 20.0)
