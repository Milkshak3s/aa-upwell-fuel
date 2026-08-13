"""Settings for the local test project.

Just enough Alliance Auth to load this app, resolve its hooks and render its
page against an in-memory database. See README-DEVELOPMENT.md.
"""

# flake8: noqa

import os

from allianceauth.project_template.project_name.settings.base import *  # noqa: F403

SECRET_KEY = "test-secret-key-not-used-anywhere-real"
DEBUG = True
ROOT_URLCONF = "testauth.urls"
SITE_NAME = "testauth"
SITE_URL = "https://example.com"
CSRF_TRUSTED_ORIGINS = [SITE_URL]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS += [  # noqa: F405
    "eveuniverse",
    "structures",
    "upwellfuel",
]

CELERY_ALWAYS_EAGER = True
ESI_SSO_CLIENT_ID = "dummy"
ESI_SSO_CLIENT_SECRET = "dummy"
ESI_SSO_CALLBACK_URL = "https://example.com/sso/callback"
ESI_USER_CONTACT_EMAIL = "dummy@example.com"

# Auth's default logging writes rotating files next to the project template,
# which is read-only when the package is installed. Tests only need the console.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "ERROR"},
}

# Auth needs a real Redis client even under test: its task statistics call
# django_redis.get_redis_connection() directly, and the stub it falls back to
# only catches Redis's own errors, not a non-Redis backend refusing the call.
# Point AA_TEST_REDIS at any spare database; the suite only writes counters.
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("AA_TEST_REDIS", "redis://127.0.0.1:6379/15"),
    }
}
BROKER_URL = os.environ.get("AA_TEST_REDIS", "redis://127.0.0.1:6379/15")
ALLIANCEAUTH_DASHBOARD_TASK_STATISTICS_DISABLED = True
