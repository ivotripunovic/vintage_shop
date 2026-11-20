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
        EmailAddress.objects.filter(user=row_only).update(verified=True)
        self.run()
        assert addresses(flag_only) == [("flag@example.com", True, True)]
        assert addresses(row_only) == [("row@example.com", True, True)]
        row_only.refresh_from_db()
        assert row_only.email_verified

    def test_another_users_verified_row_is_kept_and_blocks_verification(self):
        """A's verified extra email b@ stays A's; B owns it but stays unverified."""
        a = make_user("a@example.com")
        b = make_user("b@example.com")
        EmailAddress.objects.filter(user=b).delete()
        EmailAddress.objects.create(
            user=a, email="b@example.com", primary=False, verified=True
        )
        self.run()
        assert sorted(addresses(a)) == [
            ("a@example.com", True, True),
            ("b@example.com", False, True),
        ]
        assert addresses(b) == [("b@example.com", True, False)]

    def test_another_users_unverified_leftover_is_removed(self):
        a = make_user("a@example.com")
        b = make_user("b@example.com")
        EmailAddress.objects.filter(user=b).delete()
        EmailAddress.objects.create(
            user=a, email="b@example.com", primary=False, verified=False
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
    def test_verifying_is_mirrored(self):
        user = make_user("a@example.com", verified=False)
        assert addresses(user) == [("a@example.com", True, False)]
        user.email_verified = True
        user.save()
        assert addresses(user) == [("a@example.com", True, True)]

    def test_stale_unverified_save_does_not_undo_allauth_verification(self):
        user = make_user("a@example.com", verified=False)
        stale = User.objects.get(pk=user.pk)  # e.g. request.user in another tab
        EmailAddress.objects.filter(user=user).update(verified=True)  # allauth
        stale.save()
        assert addresses(user) == [("a@example.com", True, True)]
        user.refresh_from_db()
        assert user.email_verified

    def test_addresses_are_stored_lowercased(self):
        user = make_user("Mixed.Case@Example.com")
        assert addresses(user) == [("mixed.case@example.com", True, True)]

    def test_blank_email_removes_the_address(self):
        user = make_user("a@example.com")
        User.objects.filter(pk=user.pk).update(email="")
        user.refresh_from_db()
        user.save()
        assert addresses(user) == []

    def test_users_created_outside_the_register_views_get_an_address(self):
        admin = User.objects.create_superuser(
            email="admin@example.com", username="admin", password=PASSWORD
        )
        assert addresses(admin) == [("admin@example.com", True, False)]

    def test_email_change_makes_the_new_address_unverified(self):
        """Admin or shell edits: the old flag must not vouch for b@."""
        user = make_user("old@example.com")
        user.email = "new@example.com"
        user.save()
        assert addresses(user) == [("new@example.com", True, False)]
        user.refresh_from_db()
        assert not user.email_verified
        assert user.email_verified_at is None

    def test_email_change_voids_links_sent_to_the_old_address(self):
        from datetime import timedelta

        from django.utils import timezone

        from users.models import VerificationToken

        user = make_user("old@example.com", verified=False)
        for kind in (
            VerificationToken.TOKEN_TYPE_EMAIL,
            VerificationToken.TOKEN_TYPE_PASSWORD,
        ):
            VerificationToken.objects.create(
                user=user,
                token=f"t-{kind}",
                token_type=kind,
                expires_at=timezone.now() + timedelta(hours=1),
            )
        user.email = "new@example.com"
        user.save()
        assert not user.verification_tokens.filter(is_used=False).exists()

    def test_case_only_change_is_not_an_email_change(self):
        user = make_user("Old@example.com")
        user.email = "old@example.com"
        user.save()
        assert addresses(user) == [("old@example.com", True, True)]
        user.refresh_from_db()
        assert user.email_verified

    def test_making_a_verified_secondary_primary_keeps_it_verified(self):
        """allauth's set_as_primary changes User.email to a proven address."""
        user = make_user("a@example.com")
        work = EmailAddress.objects.create(
            user=user, email="work@example.com", primary=False, verified=True
        )
        work.set_as_primary()
        user.refresh_from_db()
        assert user.email == "work@example.com"
        assert user.email_verified
        assert addresses(user) == [("work@example.com", True, True)]

    def test_email_change_keeps_other_rows_the_user_owns(self):
        user = make_user("a@example.com")
        EmailAddress.objects.create(
            user=user, email="work@example.com", primary=False, verified=True
        )
        user.email = "b@example.com"
        user.save()
        assert sorted(addresses(user)) == [
            ("b@example.com", True, False),
            ("work@example.com", False, True),
        ]

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

    def test_another_users_verified_row_is_never_deleted(self):
        a = make_user("a@example.com")
        EmailAddress.objects.create(
            user=a, email="b@example.com", primary=False, verified=True
        )
        b = make_user("b@example.com")  # must not raise or delete A's row
        assert ("b@example.com", False, True) in addresses(a)
        assert addresses(b) == [("b@example.com", True, False)]

    def test_case_variant_duplicates_do_not_crash_and_first_keeps_verified(self):
        upper = make_user("Foo@example.com")
        lower = make_user("foo@example.com")  # must not raise IntegrityError
        assert addresses(upper) == [("foo@example.com", True, True)]
        assert addresses(lower) == [("foo@example.com", True, False)]


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


@pytest.mark.django_db
def test_verified_mixed_case_user_can_log_in_through_allauth(client):
    """allauth looks addresses up lowercased (review of #85)."""
    make_user("Foo.Bar@Example.com")
    response = client.post(
        "/auth/accounts/login/",
        {"login": "Foo.Bar@Example.com", "password": PASSWORD},
    )
    assert response.status_code == 302
    assert "confirm-email" not in response["Location"]


@pytest.mark.django_db
def test_social_signup_keeps_extra_verified_provider_emails(rf):
    """The sync must not delete secondary addresses allauth just created."""
    from allauth.socialaccount.models import SocialAccount, SocialLogin
    from django.contrib.auth.models import AnonymousUser
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.contrib.sessions.backends.db import SessionStore

    from users.adapters import SocialAccountAdapter

    request = rf.get("/")
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    request.user = AnonymousUser()
    user = User(email="a@gmail.com")
    sociallogin = SocialLogin(
        user=user,
        account=SocialAccount(provider="google", uid="123"),
        email_addresses=[
            EmailAddress(email="a@gmail.com", verified=True, primary=True),
            EmailAddress(email="a@work.com", verified=True, primary=False),
        ],
    )
    SocialAccountAdapter().save_user(request, sociallogin)
    assert sorted(addresses(user)) == [
        ("a@gmail.com", True, True),
        ("a@work.com", False, True),
    ]
    user.refresh_from_db()
    assert user.email_verified


@pytest.mark.django_db
def test_registration_is_atomic_when_the_sync_fails(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("sync failed")

    monkeypatch.setattr("users.signals.sync_primary_email", boom)
    with pytest.raises(RuntimeError):
        client.post(
            reverse("register"),
            {"email": "new@example.com", "password1": PASSWORD, "password2": PASSWORD},
        )
    assert not User.objects.filter(email="new@example.com").exists()


@pytest.mark.django_db
def test_social_signup_through_the_signup_form_does_not_crash(rf):
    """Nested adapters: AccountAdapter.save_user must not clear the flag that
    SocialAccountAdapter.save_user set (review of #85)."""
    from allauth.socialaccount.models import SocialAccount, SocialLogin
    from django.contrib.auth.models import AnonymousUser
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.contrib.sessions.backends.db import SessionStore

    from users.adapters import SocialAccountAdapter

    class SignupForm:
        cleaned_data = {"email": "form@example.com"}

    request = rf.get("/")
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    request.user = AnonymousUser()
    user = User(email="form@example.com")
    sociallogin = SocialLogin(
        user=user,
        account=SocialAccount(provider="google", uid="456"),
        email_addresses=[
            EmailAddress(email="form@example.com", verified=True, primary=True)
        ],
    )
    SocialAccountAdapter().save_user(request, sociallogin, form=SignupForm())
    assert addresses(user) == [("form@example.com", True, True)]
