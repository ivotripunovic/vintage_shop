"""
Pytest configuration with test optimizations.

- Uses faster password hashing for tests
- Configures Django test settings
- Manages test database caching
"""

import os
from unittest import mock

import django
import pytest
from django.conf import settings
from django.core.cache import cache
from django.db import connections, router
from django.db.migrations.executor import MigrationExecutor


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


@pytest.fixture
def scratch_db(tmp_path, django_db_blocker):
    """A throwaway SQLite database for running migrations back and forth.

    A transactional test on the shared test database would flush it
    afterwards, wiping rows seeded by data migrations (SellerTier) that later
    tests on the same xdist worker rely on.
    """
    alias = "migration_scratch"
    connections.settings[alias] = {
        **connections.settings["default"],
        "NAME": str(tmp_path / "scratch.sqlite3"),
        "TEST": {"NAME": str(tmp_path / "scratch.sqlite3")},
    }
    connection = connections[alias]

    class ToScratch:
        """Data migrations query without .using(); send them here too."""

        def db_for_read(self, model, **hints):
            return alias

        db_for_write = db_for_read

        def allow_migrate(self, db, app_label, **hints):
            return True

    try:
        with django_db_blocker.unblock(), mock.patch.object(
            router, "routers", [ToScratch()]
        ):
            yield connection
    finally:
        connection.close()
        del connections[alias]
        del connections.settings[alias]


def migrate_scratch(connection, target, state):
    """Migrate the scratch database to ``target``; return the historical
    apps at ``state`` (the nodes whose models the test uses)."""
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    return executor.loader.project_state(state).apps
