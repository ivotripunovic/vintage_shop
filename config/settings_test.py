"""
Django test settings - inherits from base settings with optimizations.

Uses faster password hashing for tests to speed up test execution.
"""

from .settings import *  # noqa

# ============================================================================
# FASTER PASSWORD HASHING FOR TESTS
# ============================================================================
# Use PlainPasswordHasher for tests (INSECURE but ~100x faster)
# This only applies to tests, production uses secure PBKDF2

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",  # Fast for testing
]

# ============================================================================
# TEST-SPECIFIC OPTIMIZATIONS
# ============================================================================

# Disable slow/intercepting middleware
MIDDLEWARE = [
    m
    for m in MIDDLEWARE
    if "LoggingMiddleware" not in m and "ComingSoonMiddleware" not in m
]

COMING_SOON = False

# No real DNS lookups or background threads in tests
WAITLIST_CHECK_DNS = False
WAITLIST_EMAIL_ASYNC = False
CHAT_EMAIL_ASYNC = False

# Use simple in-memory cache for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Disable logging in tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {},
    "loggers": {},
}

# A file-backed test database, so --reuse-db (pytest.ini) keeps it between
# runs instead of migrating from scratch in every xdist worker. An in-memory
# SQLite database is never reused. pytest-django adds a _gw<n> suffix per
# worker. New migrations are applied to the kept database; run
# `pytest --create-db` after editing an existing migration or switching to
# a branch with different migrations.
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":  # noqa: F405
    DATABASES["default"]["TEST"] = {  # noqa: F405
        "NAME": str(BASE_DIR / ".test_db.sqlite3")  # noqa: F405
    }

# Disable social providers in tests (no OAuth credentials available)
SOCIALACCOUNT_PROVIDERS = {}
