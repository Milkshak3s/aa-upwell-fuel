"""The fuel arithmetic, kept free of Django and the ORM so it can be tested directly."""

from dataclasses import dataclass
from typing import Iterable, Optional

from .catalog import (
    HULL_SERVICE_ROLE_BONUS,
    HULL_SERVICE_ROLE_BONUS_BY_TYPE,
    SERVICE_MODULE_FUEL_PER_HOUR,
)

# ESI reports fuel_expires_at truncated to the hour, so the true expiry is
# somewhere in the following hour and a rate derived from it reads slightly high.
# Adding the midpoint of that window removes most of the bias. On a week of fuel
# it is worth well under a percent, but it is free, and it is what turns a
# measured 7.03 blocks/h into the 7.0 the game is actually charging.
EXPIRY_TRUNCATION_CORRECTION_HOURS = 0.5

RATE_SOURCE_MEASURED = "measured"
RATE_SOURCE_MODELLED = "modelled"
RATE_SOURCE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class Projection:
    """What a structure needs over a planning period, in fuel blocks."""

    rate_per_hour: Optional[float]
    rate_source: str
    blocks_remaining: float
    """Blocks still in the bay right now, projected forward from the last sync."""
    blocks_needed: float
    """Gross burn over the whole period, ignoring what is already loaded."""
    blocks_to_buy: float
    """What must actually be delivered to cover the period."""
    hours_remaining: Optional[float]
    """Hours of fuel left, or None when the structure is not burning fuel."""

    @property
    def is_covered(self) -> bool:
        """True when current fuel already carries the structure through the period."""
        return self.blocks_to_buy <= 0


def measured_rate_per_hour(
    blocks_in_bay: Optional[int], hours_from_snapshot_to_expiry: Optional[float]
) -> Optional[float]:
    """Derive the burn rate a structure is actually running at.

    This is the trustworthy source: it is the game's own expiry date divided by
    the game's own fuel bay contents, so it already accounts for every hull
    bonus, rig and service combination without modelling any of them.

    Args:
        blocks_in_bay: fuel blocks counted at the last asset sync
        hours_from_snapshot_to_expiry: hours between that sync and fuel_expires_at
    """
    if not blocks_in_bay or not hours_from_snapshot_to_expiry:
        return None

    hours = hours_from_snapshot_to_expiry + EXPIRY_TRUNCATION_CORRECTION_HOURS
    if hours <= 0:
        return None

    return blocks_in_bay / hours


def modelled_rate_per_hour(
    hull_type_id: int, hull_group_id: int, online_module_type_ids: Iterable[int]
) -> Optional[float]:
    """Estimate a burn rate from the service modules that are online.

    Only used for structures that cannot report a measured rate -- an unfuelled
    or low-power structure, where the question is what refuelling it would cost.
    Returns None when none of the fitted modules are recognised.
    """
    bonus, bonused_modules = HULL_SERVICE_ROLE_BONUS_BY_TYPE.get(
        hull_type_id, HULL_SERVICE_ROLE_BONUS.get(hull_group_id, (0.0, frozenset()))
    )

    total = 0.0
    matched = False
    for type_id in online_module_type_ids:
        base = SERVICE_MODULE_FUEL_PER_HOUR.get(type_id)
        if base is None:
            continue
        matched = True
        if type_id in bonused_modules:
            total += base * (1 + bonus / 100)
        else:
            total += base

    return total if matched else None


def project(
    rate_per_hour: Optional[float],
    rate_source: str,
    period_hours: float,
    hours_until_expiry: Optional[float] = None,
    blocks_counted: Optional[int] = None,
) -> Projection:
    """Work out the fuel needed to cover ``period_hours`` from now.

    Remaining fuel is preferably derived as rate x hours-until-expiry rather than
    read from the last asset sync. Both numbers come from the same sync, but the
    expiry date is the one the game keeps updating, so deriving from it stays
    correct even when the asset snapshot is hours stale.
    """
    if not rate_per_hour or rate_per_hour <= 0:
        return Projection(
            rate_per_hour=None,
            rate_source=RATE_SOURCE_UNKNOWN,
            blocks_remaining=float(blocks_counted or 0),
            blocks_needed=0.0,
            blocks_to_buy=0.0,
            hours_remaining=None,
        )

    if hours_until_expiry is not None and hours_until_expiry > 0:
        remaining = rate_per_hour * hours_until_expiry
        hours_remaining = hours_until_expiry
    else:
        # Not burning fuel: whatever is sitting in the bay is all it has, and it
        # would last this long once the services come back online.
        remaining = float(blocks_counted or 0)
        hours_remaining = remaining / rate_per_hour if remaining else 0.0

    needed = rate_per_hour * period_hours
    return Projection(
        rate_per_hour=rate_per_hour,
        rate_source=rate_source,
        blocks_remaining=remaining,
        blocks_needed=needed,
        blocks_to_buy=max(0.0, needed - remaining),
        hours_remaining=hours_remaining,
    )


def project_consumable(
    units_on_hand: int, units_per_hour: float, period_hours: float
) -> Projection:
    """Same projection for a non-block consumable such as magmatic gas."""
    needed = units_per_hour * period_hours
    return Projection(
        rate_per_hour=units_per_hour,
        rate_source=RATE_SOURCE_MODELLED,
        blocks_remaining=float(units_on_hand),
        blocks_needed=needed,
        blocks_to_buy=max(0.0, needed - units_on_hand),
        hours_remaining=(units_on_hand / units_per_hour) if units_per_hour else None,
    )
