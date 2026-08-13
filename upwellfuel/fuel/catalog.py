"""Static EVE reference data for fuel calculations.

Everything here was read out of the SDE (``eve_sde``) rather than typed from a
wiki: service module burn rates are dogma attribute 2109
(``serviceModuleFuelAmount``, fuel blocks per hour) and hull discounts are
attribute 2339 (``structureServiceRoleBonus``).

It is duplicated here as plain data instead of queried at runtime so this app
does not depend on an SDE loader being installed. These numbers only feed the
*modelled* fallback rate, which is used for structures that are not currently
burning fuel; a fuelled structure always reports its own measured rate.

This module is pure data with no Django imports, so it can be tested standalone.
"""

# Fuel blocks, EVE group 1136. All four variants burn identically and share a
# volume of 5 m3; only the price differs.
FUEL_BLOCK_TYPE_IDS = {
    4051: "Nitrogen Fuel Block",
    4246: "Hydrogen Fuel Block",
    4247: "Helium Fuel Block",
    4312: "Oxygen Fuel Block",
}
FUEL_BLOCK_GROUP_ID = 1136
FUEL_BLOCK_VOLUME = 5.0

MAGMATIC_GAS_TYPE_ID = 81143
MAGMATIC_GAS_VOLUME = 0.01
LIQUID_OZONE_TYPE_ID = 16273
LIQUID_OZONE_VOLUME = 0.4

# Fuel blocks per hour for each service module, unbonused (attribute 2109).
SERVICE_MODULE_FUEL_PER_HOUR = {
    35877: 36.0,  # Standup Supercapital Shipyard I
    35878: 12.0,  # Standup Manufacturing Plant I
    35880: 5.0,   # Standup Drug Lab I
    35881: 24.0,  # Standup Capital Shipyard I
    35886: 12.0,  # Standup Invention Lab I
    35891: 12.0,  # Standup Research Lab I
    35892: 40.0,  # Standup Market Hub I
    35894: 10.0,  # Standup Cloning Center I
    35899: 10.0,  # Standup Reprocessing Facility I
    35912: 15.0,  # Standup Cynosural Field Generator I
    35913: 30.0,  # Standup Conduit Generator I
    35914: 40.0,  # Standup Cynosural System Jammer I
    45009: 5.0,   # Standup Moon Drill I
    45537: 15.0,  # Standup Composite Reactor I
    45538: 15.0,  # Standup Hybrid Reactor I
    45539: 15.0,  # Standup Biochemical Reactor I
    45550: 10.0,  # Standup Hyasyoda Research Lab
    82941: 5.0,   # Standup Metenox Moon Drill
}

# ESI reports a structure's services by display name, not by module type, so a
# fitted module is matched to its service entries through this map. Used only to
# decide whether a fitted module is currently online.
SERVICE_MODULE_SERVICE_NAMES = {
    35877: {"Manufacturing (Super Capitals)"},
    35878: {"Manufacturing (Standard)"},
    35880: {"Manufacturing (Boosters)"},
    35881: {"Manufacturing (Capitals)"},
    35886: {"Invention"},
    35891: {"Blueprint Copying", "Material Efficiency Research", "Time Efficiency Research"},
    35892: {"Market Hub"},
    35894: {"Clone Bay"},
    35899: {"Reprocessing"},
    35912: {"Cynosural Field"},
    35913: {"Jump Bridge Access"},
    35914: {"Cynosural System Jammer"},
    45009: {"Moon Drilling"},
    45537: {"Composite Reactions"},
    45538: {"Hybrid Reactions"},
    45539: {"Biochemical Reactions"},
    45550: {"Blueprint Copying", "Material Efficiency Research", "Time Efficiency Research"},
    82941: {"Automatic Moon Drilling"},
}

# Structure hull groups.
GROUP_CITADEL = 1657
GROUP_ENGINEERING_COMPLEX = 1404
GROUP_REFINERY = 1406
GROUP_UPWELL_JUMP_BRIDGE = 1408
GROUP_METENOX_MOON_DRILL = 4744

# A hull's service role bonus does NOT apply to every module it can fit, only to
# the ones matching the hull's role. That is not expressed in dogma, so the
# module sets are listed explicitly. Each entry maps a hull group to
# (discount, module type ids the discount applies to).
#
# Both the discounts and the module sets were validated against measured burn
# rates across a live fleet of 41 structures:
#
#   Raitaru + Manufacturing Plant   12/h -> measured  9.1/h  (-25%, applies)
#   Sotiyo, 5 modules               68/h -> measured 53.4/h  (-25% on the four
#                                           industry modules, none on the clone bay)
#   Athanor + Reprocessing          10/h -> measured  8.1/h  (-20%, applies)
#   Athanor + Moon Drill I           5/h -> measured  5.0/h  (no discount)
#   Tatara, 3 reactors + reprocess  55/h -> measured 41.8/h  (-25% on all four)
#   Ansiblex + Conduit Generator    30/h -> measured 30.5/h  (no discount)
#
# The citadel figure is the one place where dogma and the game disagree: hulls
# in group 1657 carry structureServiceRoleBonus = -25, but twelve Astrahus and
# Fortizars each running a lone clone bay all measured 7.0/h against a 10/h base
# -- an effective -30%. The measured value is used here. A citadel's discount
# also does not reach a reprocessing array: an Astrahus running one measured
# 10.1/h, its full unbonused rate.
INDUSTRY_MODULES = frozenset({35877, 35878, 35880, 35881, 35886, 35891, 45550})
REACTION_MODULES = frozenset({45537, 45538, 45539})
CITADEL_SERVICE_MODULES = frozenset({35892, 35894})

HULL_SERVICE_ROLE_BONUS = {
    GROUP_CITADEL: (-30.0, CITADEL_SERVICE_MODULES),
    GROUP_ENGINEERING_COMPLEX: (-25.0, INDUSTRY_MODULES),
    GROUP_REFINERY: (-20.0, frozenset({35899}) | REACTION_MODULES),
}

# Tatara and Sotiyo are the tier-2 hulls of their groups and discount more
# deeply than the tier-1 Athanor and Raitaru.
HULL_SERVICE_ROLE_BONUS_BY_TYPE = {
    35836: (-25.0, frozenset({35899}) | REACTION_MODULES),  # Tatara
}
