"""Template helpers for the fuel table."""

from django import template
from django.utils.html import format_html
from django.utils.http import urlencode

from ..fuel.report import SORT_FIELDS, resolve_sort

register = template.Library()

CARET_UP = "fa-caret-up"
CARET_DOWN = "fa-caret-down"


@register.simple_tag(takes_context=True)
def sort_header(context, key, label=""):
    """A column heading that sorts the table when clicked.

    Every other query parameter is carried through, so sorting does not quietly
    drop the period, the corporation filter or the shortfall checkbox.
    """
    field = SORT_FIELDS.get(key)
    if field is None:  # a typo in the template should be loud, not silent
        raise template.TemplateSyntaxError(f"unknown sort column '{key}'")

    request = context.get("request")
    params = request.GET.copy() if request is not None else {}
    active_key, active_descending = resolve_sort(
        params.get("sort", ""), params.get("dir", "")
    )
    is_active = active_key == key

    # Clicking the column you are already on reverses it; clicking any other
    # column starts it in whichever direction reads best for that column.
    descending = not active_descending if is_active else field.descending_by_default

    query = {k: v for k, v in params.items() if k not in ("sort", "dir")}
    query["sort"] = key
    query["dir"] = "desc" if descending else "asc"

    if is_active:
        caret = CARET_DOWN if active_descending else CARET_UP
        icon = format_html('<i class="fa-solid {} ms-1"></i>', caret)
    else:
        icon = format_html('<i class="fa-solid fa-sort ms-1 opacity-25"></i>')

    return format_html(
        '<a href="?{}" class="text-reset text-decoration-none d-inline-flex '
        'align-items-center{}" title="Sort by {}">{}{}</a>',
        urlencode(query),
        " fw-bold" if is_active else "",
        field.label,
        label or field.label,
        icon,
    )


@register.simple_tag(takes_context=True)
def sort_query(context):
    """The current sort as query-string fragment, for the CSV export link."""
    request = context.get("request")
    params = request.GET if request is not None else {}
    key, descending = resolve_sort(params.get("sort", ""), params.get("dir", ""))
    return urlencode({"sort": key, "dir": "desc" if descending else "asc"})
