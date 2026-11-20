"""
allauth's EmailAddress mirrors User.email / User.email_verified (#76).
"""

import importlib

import pytest
from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from django.apps import apps
from django.urls import reverse

from users.email_sync import sync_primary_email
from users.models import User

backfill = importlib.import_module(
    "users.migrations.0004_backfill_allauth_email_addresses"
).backfill

PASSWORD = "Pw-strong-123"


def make_user(email, verified=True, **extra):
    user = User.objects.create_user(
        email=email, username=email, password=PASSWORD, **extra
    )
    if verified:
        # A later save, as the custom verify view does, so the signal runs
        user.email_verified = True
        user.save()
    return user


def addresses(user):
    return list(
        EmailAddress.objects.filter(user=user).values_list(
            "email", "primary", "verified"
        )
    )


@pytest.mark.django_db
class TestBackfill:
    def run(self):
        backfill(apps, None)

    def test_user_without_address_gets_verified_primary(self):
        user = make_user("a@example.com")
        EmailAddress.objects.all().delete()
        self.run()
        assert addresses(user) == [("a@example.com", True, True)]

    def test_unverified_user_gets_unverified_address(self):
        user = make_user("a@example.com", verified=False)
        self.run()
        assert addresses(user) == [("a@example.com", True, False)]

    def test_either_side_verified_wins(self):
        flag_only = make_user("flag@example.com")
        EmailAddress.objects.filter(user=flag_only).update(verified=False)
        row_only = make_user("row@example.com", verified=False)
        EmailAddress.objects.create(
            user=row_only, email="row@example.com", primary=True, verified=True
        )
        self.run()
        assert addresses(flag_only) == [("flag@example.com", True, True)]
        assert addresses(row_only) == [("row@example.com", True, True)]
        row_only.refresh_from_db()
        assert row_only.email_verified

    def test_stale_rows_are_removed_without_colliding(self):
        """B now owns an email whose verified row A kept from before."""
        a = make_user("a@example.com")
        b = make_user("b@example.com")
        EmailAddress.objects.filter(user=b).delete()
        EmailAddress.objects.create(
            user=a, email="b@example.com", primary=False, verified=True
        )
        self.run()
        assert addresses(a) == [("a@example.com", True, True)]
        assert addresses(b) == [("b@example.com", True, True)]

    def test_is_idempotent(self):
        user = make_user("a@example.com")
        self.run()
        self.run()
        assert addresses(user) == [("a@example.com", True, True)]


@pytest.mark.django_db
class TestUserSaveMirrorsIntoAllauth:
    def test_verifying_and_unverifying_is_mirrored(self):
        user = make_user("a@example.com")
        assert addresses(user) == [("a@example.com", True, True)]
        user.email_verified = False
        user.save()
        assert addresses(user) == [("a@example.com", True, False)]

    def test_email_change_moves_the_address(self):
        user = make_user("old@example.com")
        user.email = "new@example.com"
        user.save()
        assert addresses(user) == [("new@example.com", True, True)]

    def test_unrelated_update_fields_skip_the_sync(self):
        user = make_user("a@example.com")
        EmailAddress.objects.filter(user=user).delete()
        user.save(update_fields=["last_login"])
        assert addresses(user) == []

    def test_sync_does_not_write_when_in_step(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        user = make_user("a@example.com")
        with CaptureQueriesContext(connection) as ctx:
            sync_primary_email(user)
        writes = [
            q["sql"]
            for q in ctx.captured_queries
            if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE"))
        ]
        assert writes == []

    def test_new_owner_takes_over_another_users_stale_verified_row(self):
        a = make_user("a@example.com")
        EmailAddress.objects.create(
            user=a, email="b@example.com", primary=False, verified=True
        )
        b = make_user("b@example.com")  # must not raise IntegrityError
        assert addresses(a) == [("a@example.com", True, True)]
        assert addresses(b) == [("b@example.com", True, True)]

    def test_other_users_current_email_in_other_case_is_kept(self):
        upper = make_user("Foo@example.com")
        lower = make_user("foo@example.com")
        assert addresses(upper) == [("Foo@example.com", True, True)]
        assert addresses(lower) == [("foo@example.com", True, True)]


@pytest.mark.django_db
def test_allauth_confirmation_sets_user_flag():
    user = make_user("a@example.com", verified=False)
    sync_primary_email(user)
    address = EmailAddress.objects.get(user=user)
    address.verified = True
    address.save()
    email_confirmed.send(sender=None, request=None, email_address=address)
    user.refresh_from_db()
    assert user.email_verified
    assert user.email_verified_at is not None


@pytest.mark.django_db
def test_custom_register_creates_unverified_address(client):
    client.post(
        reverse("register"),
        {
            "email": "new@example.com",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )
    user = User.objects.get(email="new@example.com")
    assert addresses(user) == [("new@example.com", True, False)]


@pytest.mark.django_db
def test_allauth_signup_still_creates_its_own_address(client):
    """setup_user_email asserts the new user has no EmailAddress yet."""
    client.post(
        "/auth/accounts/signup/",
        {"email": "b@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )
    user = User.objects.get(email="b@example.com")
    assert addresses(user) == [("b@example.com", True, False)]


@pytest.mark.django_db
def test_verified_user_is_not_asked_to_verify_again_by_allauth(client):
    """The original bug: allauth sent verified users to confirm-email."""
    make_user("a@example.com")
    response = client.post(
        "/auth/accounts/login/", {"login": "a@example.com", "password": PASSWORD}
    )
    assert response.status_code == 302
    assert "confirm-email" not in response["Location"]
