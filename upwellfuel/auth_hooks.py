"""Alliance Auth hooks for Upwell Fuel"""

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class UpwellFuelMenuItem(MenuItemHook):
    """Sidebar entry, shown to anyone who may access aa-structures."""

    def __init__(self):
        MenuItemHook.__init__(
            self,
            "Upwell Fuel",
            "fa-solid fa-gas-pump",
            "upwellfuel:index",
            order=1010,
            navactive=["upwellfuel:"],
        )

    def render(self, request):
        # This app deliberately has no permissions of its own. It is a different
        # view onto data that aa-structures already owns, so it reuses that app's
        # access model: structures.basic_access to reach the page, and the
        # view_*_structures permissions to decide which rows are visible.
        if request.user.has_perm("structures.basic_access"):
            return MenuItemHook.render(self, request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    """Register the menu item"""
    return UpwellFuelMenuItem()


@hooks.register("url_hook")
def register_urls():
    """Register app urls"""
    return UrlHook(urls, "upwellfuel", r"^upwellfuel/")
