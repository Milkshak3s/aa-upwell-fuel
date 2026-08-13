"""Builds the fuel report from the structure data aa-structures maintains.

This app stores nothing of its own. Every number on the page is derived, per
request, from ``structures.Structure`` and the assets aa-structures already
syncs, so the report is exactly as fresh as that app's last sync and cannot
drift out of step with it.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from django.utils.timezone import now

from .calc import (
    RATE_SOURCE_MEASURED,
    RATE_SOURCE_MODELLED,
    RATE_SOURCE_UNKNOWN,
    Projection,
    measured_rate_per_hour,
    modelled_rate_per_hour,
    project,
    project_consumable,
)
from .catalog import (
    FUEL_BLOCK_GROUP_ID,
    FUEL_BLOCK_TYPE_IDS,
    FUEL_BLOCK_VOLUME,
    GROUP_METENOX_MOON_DRILL,
    GROUP_UPWELL_JUMP_BRIDGE,
    LIQUID_OZONE_TYPE_ID,
    MAGMATIC_GAS_TYPE_ID,
    SERVICE_MODULE_SERVICE_NAMES,
)

logger = logging.getLogger(__name__)

SERVICE_SLOT_PREFIX = "ServiceSlot"
STRUCTURE_FUEL_FLAG = "StructureFuel"
SERVICE_STATE_ONLINE = 2


@dataclass
class StructureRow:
    """One structure's fuel outlook over the planning period."""

    structure_id: int
    name: str
    type_name: str
    solar_system: str
    region: str
    corporation: str
    services: List[str]
    power_mode: str
    projection: Projection
    fuel_block_type_id: Optional[int] = None
    fuel_block_type_name: str = ""
    isk_to_buy: Optional[float] = None
    gas: Optional[Projection] = None
    gas_isk_to_buy: Optional[float] = None
    ozone_on_hand: Optional[int] = None

    @property
    def blocks_per_day(self) -> Optional[float]:
        rate = self.projection.rate_per_hour
        return rate * 24 if rate else None

    @property
    def days_remaining(self) -> Optional[float]:
        hours = self.projection.hours_remaining
        return hours / 24 if hours is not None else None

    @property
    def volume_to_buy(self) -> float:
        return self.projection.blocks_to_buy * FUEL_BLOCK_VOLUME

    @property
    def is_measured(self) -> bool:
        return self.projection.rate_source == RATE_SOURCE_MEASURED

    @property
    def needs_attention(self) -> bool:
        """Structures a planner should look at before anything else."""
        return (
            self.projection.rate_source == RATE_SOURCE_UNKNOWN
            or (self.days_remaining is not None and self.days_remaining < 7)
        )


@dataclass
class CorporationTotal:
    """Per-corporation subtotal."""

    corporation: str
    structures: int = 0
    blocks_needed: float = 0.0
    blocks_to_buy: float = 0.0
    isk_to_buy: float = 0.0


@dataclass
class Report:
    """The whole page's data."""

    period_days: int
    rows: List[StructureRow] = field(default_factory=list)
    by_corporation: List[CorporationTotal] = field(default_factory=list)
    blocks_needed: float = 0.0
    blocks_to_buy: float = 0.0
    isk_to_buy: float = 0.0
    volume_to_buy: float = 0.0
    gas_to_buy: float = 0.0
    modelled_count: int = 0
    unknown_count: int = 0
    has_prices: bool = False

    @property
    def structure_count(self) -> int:
        return len(self.rows)


def _market_prices() -> dict:
    """Average price per unit for everything this page can cost out."""
    try:
        from eveuniverse.models import EveMarketPrice
    except ImportError:  # pragma: no cover - eveuniverse is a hard dependency
        return {}

    type_ids = list(FUEL_BLOCK_TYPE_IDS) + [MAGMATIC_GAS_TYPE_ID]
    prices = {}
    for price in EveMarketPrice.objects.filter(eve_type_id__in=type_ids):
        value = price.average_price or price.adjusted_price
        if value:
            prices[price.eve_type_id] = value
    return prices


def _hours_between(later, earlier) -> Optional[float]:
    if not later or not earlier:
        return None
    return (later - earlier).total_seconds() / 3600


def _fuel_bay(structure):
    """Split a structure's fuel bay into blocks, gas and ozone."""
    blocks = 0
    block_type_id = None
    oldest_sync = None
    gas = 0
    ozone = 0

    for item in structure.items.all():
        if item.location_flag != STRUCTURE_FUEL_FLAG:
            continue
        if item.eve_type.eve_group_id == FUEL_BLOCK_GROUP_ID:
            blocks += item.quantity
            block_type_id = block_type_id or item.eve_type_id
            if oldest_sync is None or item.last_updated_at < oldest_sync:
                oldest_sync = item.last_updated_at
        elif item.eve_type_id == MAGMATIC_GAS_TYPE_ID:
            gas += item.quantity
        elif item.eve_type_id == LIQUID_OZONE_TYPE_ID:
            ozone += item.quantity

    return blocks, block_type_id, oldest_sync, gas, ozone


def _burning_module_type_ids(structure) -> List[int]:
    """Fitted service modules to charge fuel for.

    ESI names a structure's services by display name rather than by module, so
    fitted modules are matched against those names. A module whose service names
    are not in the catalog counts as online when the structure is running
    anything at all, which keeps an unrecognised module from silently dropping
    out of the estimate.

    A structure that has run dry is the case this fallback exists for, and it
    reports every service as offline -- they cannot be online without fuel. So
    when nothing is online, every fitted module counts instead, which answers the
    question a planner is actually asking: what would it cost to refuel this and
    bring it back up.
    """
    module_type_ids = [
        item.eve_type_id
        for item in structure.items.all()
        if item.location_flag.startswith(SERVICE_SLOT_PREFIX)
    ]

    online_services = {
        service.name for service in structure.services.all() if service.state == SERVICE_STATE_ONLINE
    }
    if not online_services:
        return module_type_ids

    burning = []
    for type_id in module_type_ids:
        names = SERVICE_MODULE_SERVICE_NAMES.get(type_id)
        if names is None or names & online_services:
            burning.append(type_id)
    return burning


def build_report(structures, period_days: int, magmatic_gas_per_hour: float) -> Report:
    """Project fuel needs for every structure in ``structures``.

    Args:
        structures: a Structure queryset, already filtered for visibility
        period_days: planning horizon
        magmatic_gas_per_hour: gas burn rate for Metenox drills
    """
    period_hours = period_days * 24
    prices = _market_prices()
    report = Report(period_days=period_days, has_prices=bool(prices))
    totals = {}
    right_now = now()

    for structure in structures:
        if not structure.is_upwell_structure:
            continue

        blocks, block_type_id, oldest_sync, gas_on_hand, ozone = _fuel_bay(structure)
        hours_to_expiry = _hours_between(structure.fuel_expires_at, right_now)
        if hours_to_expiry is not None and hours_to_expiry < 0:
            hours_to_expiry = None

        rate = measured_rate_per_hour(
            blocks, _hours_between(structure.fuel_expires_at, oldest_sync)
        )
        rate_source = RATE_SOURCE_MEASURED
        if rate is None:
            rate = modelled_rate_per_hour(
                structure.eve_type_id,
                structure.eve_type.eve_group_id,
                _burning_module_type_ids(structure),
            )
            rate_source = RATE_SOURCE_MODELLED if rate else RATE_SOURCE_UNKNOWN

        projection = project(
            rate_per_hour=rate,
            rate_source=rate_source,
            period_hours=period_hours,
            hours_until_expiry=hours_to_expiry,
            blocks_counted=blocks,
        )

        price_type_id = block_type_id or _default_block_type_id()
        unit_price = prices.get(price_type_id)
        isk = projection.blocks_to_buy * unit_price if unit_price else None

        gas_projection = None
        gas_isk = None
        if structure.eve_type.eve_group_id == GROUP_METENOX_MOON_DRILL:
            gas_projection = project_consumable(
                gas_on_hand, magmatic_gas_per_hour, period_hours
            )
            gas_price = prices.get(MAGMATIC_GAS_TYPE_ID)
            if gas_price:
                gas_isk = gas_projection.blocks_to_buy * gas_price

        row = StructureRow(
            structure_id=structure.id,
            name=structure.name,
            type_name=structure.eve_type.name,
            solar_system=_solar_system_name(structure),
            region=_region_name(structure),
            corporation=str(structure.owner.corporation),
            services=sorted(
                service.name
                for service in structure.services.all()
                if service.state == SERVICE_STATE_ONLINE
            ),
            power_mode=structure.get_power_mode_display(),
            projection=projection,
            fuel_block_type_id=block_type_id,
            fuel_block_type_name=FUEL_BLOCK_TYPE_IDS.get(block_type_id, ""),
            isk_to_buy=isk,
            gas=gas_projection,
            gas_isk_to_buy=gas_isk,
            ozone_on_hand=ozone if structure.eve_type.eve_group_id == GROUP_UPWELL_JUMP_BRIDGE else None,
        )
        report.rows.append(row)

        total = totals.setdefault(row.corporation, CorporationTotal(corporation=row.corporation))
        total.structures += 1
        total.blocks_needed += projection.blocks_needed
        total.blocks_to_buy += projection.blocks_to_buy
        total.isk_to_buy += isk or 0.0

        report.blocks_needed += projection.blocks_needed
        report.blocks_to_buy += projection.blocks_to_buy
        report.isk_to_buy += isk or 0.0
        if gas_projection:
            report.gas_to_buy += gas_projection.blocks_to_buy
        if rate_source == RATE_SOURCE_MODELLED:
            report.modelled_count += 1
        elif rate_source == RATE_SOURCE_UNKNOWN:
            report.unknown_count += 1

    report.volume_to_buy = report.blocks_to_buy * FUEL_BLOCK_VOLUME
    report.by_corporation = sorted(
        totals.values(), key=lambda total: total.blocks_to_buy, reverse=True
    )
    report.rows.sort(key=lambda row: (row.days_remaining is None, row.days_remaining or 0))
    return report


def _default_block_type_id() -> int:
    from ..app_settings import UPWELLFUEL_DEFAULT_FUEL_BLOCK_TYPE_ID

    return UPWELLFUEL_DEFAULT_FUEL_BLOCK_TYPE_ID


def _solar_system_name(structure) -> str:
    try:
        return structure.eve_solar_system.name
    except AttributeError:
        return "?"


def _region_name(structure) -> str:
    try:
        return structure.eve_solar_system.eve_constellation.eve_region.name
    except AttributeError:
        return "?"
