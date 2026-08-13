"""Application settings for Upwell Fuel"""

from django.conf import settings

# Planning period offered in the period picker, in days, and the one selected
# by default. Monthly planning is the common case.
UPWELLFUEL_DEFAULT_PERIOD_DAYS = getattr(settings, "UPWELLFUEL_DEFAULT_PERIOD_DAYS", 30)
UPWELLFUEL_PERIOD_CHOICES = getattr(settings, "UPWELLFUEL_PERIOD_CHOICES", [7, 14, 30, 60, 90])
UPWELLFUEL_MAX_PERIOD_DAYS = getattr(settings, "UPWELLFUEL_MAX_PERIOD_DAYS", 365)

# Magmatic gas burned per hour by a Metenox Moon Drill.
#
# Unlike fuel blocks this rate is NOT in dogma -- the Metenox module carries only
# its 5 blocks/h -- and gas has no expiry date in ESI to measure against, so it
# cannot be derived the way block rates are. This default is the community
# figure; override it if CCP changes the drill or if your own bay drawdown
# disagrees. Gas figures on the page are labelled as estimates because of this.
UPWELLFUEL_MAGMATIC_GAS_PER_HOUR = getattr(settings, "UPWELLFUEL_MAGMATIC_GAS_PER_HOUR", 55.0)

# Which fuel block to price when a structure's bay is empty and there is no way
# to tell which variant it burns. Defaults to Oxygen.
UPWELLFUEL_DEFAULT_FUEL_BLOCK_TYPE_ID = getattr(
    settings, "UPWELLFUEL_DEFAULT_FUEL_BLOCK_TYPE_ID", 4312
)
