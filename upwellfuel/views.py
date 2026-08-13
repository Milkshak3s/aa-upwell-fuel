"""Views for Upwell Fuel"""

import csv
import logging

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import render

from structures.constants import EveCategoryId
from structures.models import Structure

from .app_settings import (
    UPWELLFUEL_DEFAULT_PERIOD_DAYS,
    UPWELLFUEL_MAGMATIC_GAS_PER_HOUR,
    UPWELLFUEL_MAX_PERIOD_DAYS,
    UPWELLFUEL_PERIOD_CHOICES,
)
from .fuel.report import build_report

logger = logging.getLogger(__name__)


def _visible_structures(user):
    """Upwell structures this user may see, with everything the report reads.

    Visibility is delegated to aa-structures: view_all_structures,
    view_alliance_structures and view_corporation_structures all behave exactly
    as they do on that app's own pages.
    """
    return (
        Structure.objects.visible_for_user(user)
        .filter(eve_type__eve_group__eve_category_id=EveCategoryId.STRUCTURE)
        .select_related(
            "eve_type",
            "eve_type__eve_group",
            "eve_solar_system",
            "eve_solar_system__eve_constellation",
            "eve_solar_system__eve_constellation__eve_region",
            "owner",
            "owner__corporation",
        )
        .prefetch_related("items", "items__eve_type", "services")
    )


def _period_days(request) -> int:
    """Planning horizon from the query string, clamped to something sane."""
    try:
        days = int(request.GET.get("days", UPWELLFUEL_DEFAULT_PERIOD_DAYS))
    except (TypeError, ValueError):
        return UPWELLFUEL_DEFAULT_PERIOD_DAYS
    return max(1, min(days, UPWELLFUEL_MAX_PERIOD_DAYS))


def _apply_filters(report, request):
    """Narrow the finished report to what the user asked to see."""
    corporation = request.GET.get("corporation", "")
    if corporation:
        report.rows = [row for row in report.rows if row.corporation == corporation]
    if request.GET.get("shortfall"):
        report.rows = [row for row in report.rows if not row.projection.is_covered]
    return report


def _build(request):
    days = _period_days(request)
    report = build_report(
        _visible_structures(request.user),
        period_days=days,
        magmatic_gas_per_hour=UPWELLFUEL_MAGMATIC_GAS_PER_HOUR,
    )
    corporations = sorted({row.corporation for row in report.rows})
    return _apply_filters(report, request), days, corporations


@login_required
@permission_required("structures.basic_access")
def index(request):
    """Fuel requirements for every visible structure over a planning period."""
    report, days, corporations = _build(request)

    context = {
        "report": report,
        "period_days": days,
        "period_choices": UPWELLFUEL_PERIOD_CHOICES,
        "corporations": corporations,
        "selected_corporation": request.GET.get("corporation", ""),
        "shortfall_only": bool(request.GET.get("shortfall")),
        "gas_rate": UPWELLFUEL_MAGMATIC_GAS_PER_HOUR,
    }
    return render(request, "upwellfuel/index.html", context)


@login_required
@permission_required("structures.basic_access")
def export_csv(request):
    """The same table as a CSV, for handing to whoever runs the buy order."""
    report, days, _ = _build(request)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="upwell-fuel-{days}d.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(
        [
            "Structure",
            "Type",
            "System",
            "Region",
            "Corporation",
            "Services online",
            "Power mode",
            "Blocks/day",
            "Rate source",
            "Days remaining",
            f"Blocks needed ({days}d)",
            "Blocks in bay",
            "Blocks to buy",
            "Volume to buy (m3)",
            "ISK to buy",
            "Magmatic gas to buy",
            "Liquid ozone in bay",
        ]
    )
    for row in report.rows:
        writer.writerow(
            [
                row.name,
                row.type_name,
                row.solar_system,
                row.region,
                row.corporation,
                ", ".join(row.services),
                row.power_mode,
                round(row.blocks_per_day, 1) if row.blocks_per_day else "",
                row.projection.rate_source,
                round(row.days_remaining, 1) if row.days_remaining is not None else "",
                round(row.projection.blocks_needed),
                round(row.projection.blocks_remaining),
                round(row.projection.blocks_to_buy),
                round(row.volume_to_buy),
                round(row.isk_to_buy) if row.isk_to_buy else "",
                round(row.gas.blocks_to_buy) if row.gas else "",
                row.ozone_on_hand if row.ozone_on_hand is not None else "",
            ]
        )
    return response
