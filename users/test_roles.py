"""
The buyer/seller role columns are gone (#89): migration users.0006 and the
admin's "has a shop" filter.
"""

from unittest import mock

import pytest
from django.db import connections, router
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse

from sellers.testing import make_seller
from users.models import User

BEFORE = [("users", "0005_remove_email_verified_and_verificationtoken")]
AFTER = [("users", "0006_remove_user_roles")]
# For the historical models: sellers is not a dependency of users.0005
STATE = BEFORE + [("sellers", "0005_seller_trader_confirmation")]


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


def _migrate(connection, target):
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    return executor.loader.project_state(STATE).apps


def test_migration_lists_flagged_sellers_without_a_shop(scratch_db, capsys):
    apps = _migrate(scratch_db, STATE)
    OldUser = apps.get_model("users", "User")
    Seller = apps.get_model("sellers", "Seller")
    shop_owner = OldUser.objects.create(
        email="shop@example.com", username="shop", is_seller=True
    )
    Seller.objects.create(user=shop_owner, shop_name="Radnja", shop_slug="radnja")
    orphan = OldUser.objects.create(
        email="orphan@example.com", username="orphan", is_seller=True
    )
    OldUser.objects.create(email="buyer@example.com", username="buyer")
    capsys.readouterr()

    _migrate(scratch_db, AFTER)
    output = capsys.readouterr().out
    assert f"user {orphan.pk} (orphan@example.com)" in output
    assert "shop@example.com" not in output
    assert "buyer@example.com" not in output
    with scratch_db.cursor() as cursor:
        columns = {
            c.name
            for c in scratch_db.introspection.get_table_description(
                cursor, "users_user"
            )
        }
    assert not {"is_seller", "is_buyer"} & columns

    # Reversing restores the flag from the shops
    apps = _migrate(scratch_db, STATE)
    flags = dict(
        apps.get_model("users", "User").objects.values_list("email", "is_seller")
    )
    assert flags == {
        "shop@example.com": True,
        "orphan@example.com": False,
        "buyer@example.com": False,
    }


@pytest.mark.django_db
def test_admin_filters_users_by_shop(client):
    admin = User.objects.create_superuser(
        email="root@example.com", username="root", password="pw"
    )
    owner = make_seller("owner@example.com").user
    buyer = User.objects.create_user(email="buyer@example.com", username="buyer")
    client.force_login(admin)
    url = reverse("admin:users_user_changelist")

    def listed(query):
        response = client.get(url + query)
        assert response.status_code == 200
        return set(response.context["cl"].result_list)

    assert listed("?has_shop=yes") == {owner}
    assert listed("?has_shop=no") == {buyer, admin}
    page = client.get(url).content.decode()
    assert "has a shop" in page.lower()
    assert "is_buyer" not in page
