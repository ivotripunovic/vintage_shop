"""
Pytest configuration with test optimizations.

- Uses faster password hashing for tests
- Configures Django test settings
- Manages test database caching
"""

import os

import django
import pytest
from django.conf import settings
from django.core.cache import cache


def pytest_configure():
    """Configure Django with test settings before running tests."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")

    if not settings.configured:
        django.setup()


@pytest.fixture(autouse=True)
def _clear_cache():
    """Start every test with an empty cache, so rate-limit counters and
    cached fragments never leak between tests sharing a worker."""
    cache.clear()
    yield


def pytest_collection_modifyitems(config, items):
    """
    Mark slow tests automatically.

    This allows developers to skip slow tests during development with:
    $ pytest -m "not slow"
    """
    for item in items:
        # Mark view tests as slow (they're slower than model/form tests)
        if "test_views" in str(item.fspath):
            item.add_marker(pytest.mark.slow)
