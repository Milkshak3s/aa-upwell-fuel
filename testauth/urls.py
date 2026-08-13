"""URLs for the local test project."""

from django.urls import include, path

import allianceauth.urls

urlpatterns = [
    path("", include(allianceauth.urls)),
]
