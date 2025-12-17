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
    'django.contrib.auth.hashers.MD5PasswordHasher',  # Fast for testing
]

# ============================================================================
# TEST-SPECIFIC OPTIMIZATIONS
# ============================================================================

# Disable slow middleware
MIDDLEWARE = [m for m in MIDDLEWARE if 'LoggingMiddleware' not in m]

# Use simple in-memory cache for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Disable logging in tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {},
    'loggers': {},
}

# Skip migrations for faster test setup (if using pytest)
# For manage.py test, Django handles this automatically
