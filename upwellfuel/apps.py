"""Django app configuration for Upwell Fuel"""

from django.apps import AppConfig

from . import __version__


class UpwellFuelConfig(AppConfig):
    """App config"""

    name = "upwellfuel"
    label = "upwellfuel"
    verbose_name = f"Upwell Fuel v{__version__}"
