"""
Tests for social auth adapters.
"""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sites.models import Site
from django.test import RequestFactory, TestCase
from django.utils import timezone

from .adapters import AccountAdapter, SocialAccountAdapter
from .models import User, VerificationToken


def _make_request(factory):
    request = factory.get("/")
    request.session = {}
    request._messages = FallbackStorage(request)
    request.user = AnonymousUser()
    return request


def _make_sociallogin(
    *, is_existing=False, email="user@example.com", process="login", verified=True
):
    sociallogin = MagicMock()
    sociallogin.is_existing = is_existing
    sociallogin.user.email = email
    sociallogin.state = {"process": process}
    sociallogin.email_addresses = (
        [MagicMock(email=email, verified=verified)] if email else []
    )
    return sociallogin


# ---------------------------------------------------------------------------
# SocialAccountAdapter.pre_social_login
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPreSocialLogin(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = SocialAccountAdapter()

    def test_allows_signup_process(self):
        """Coming from the register page always passes through, even for new emails."""
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(process="signup", is_existing=False)
        self.adapter.pre_social_login(request, sociallogin)  # must not raise

    def test_allows_existing_linked_account(self):
        """An already-linked social account is always allowed through."""
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(is_existing=True)
        self.adapter.pre_social_login(request, sociallogin)  # must not raise

    def test_connects_existing_user_when_email_matches(self):
        """A verified provider email matching a registered account links the two."""
        user = User.objects.create_user(
            email="registered@example.com",
            username="registered",
            password="pass",
            email_verified=True,
        )
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="Registered@example.com")
        self.adapter.pre_social_login(request, sociallogin)  # must not raise
        sociallogin.connect.assert_called_once_with(request, user)
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())

    def test_connects_existing_user_from_signup_process(self):
        """Using Google on the register page with a taken email logs into it."""
        user = User.objects.create_user(
            email="registered@example.com",
            username="registered",
            password="pass",
            email_verified=True,
        )
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(
            email="registered@example.com", process="signup"
        )
        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_called_once_with(request, user)

    def test_connecting_unverified_user_wipes_password_and_verifies(self):
        """An unverified local account may belong to someone else: lock its password."""
        user = User.objects.create_user(
            email="registered@example.com",
            username="registered",
            password="pass",
        )
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="registered@example.com")
        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_called_once_with(request, user)
        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.email_verified)
        self.assertIsNotNone(user.email_verified_at)

    def test_unverified_provider_email_redirects_to_login(self):
        """Without provider verification nothing is linked; user goes to login."""
        User.objects.create_user(
            email="registered@example.com",
            username="registered",
            password="pass",
        )
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="registered@example.com", verified=False)
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(request, sociallogin)
        self.assertIn("/auth/login/", ctx.exception.response["Location"])
        sociallogin.connect.assert_not_called()

    def test_connecting_unverified_user_invalidates_tokens(self):
        """Reset/verification links issued before the takeover stop working."""
        user = User.objects.create_user(
            email="registered@example.com", username="registered", password="pass"
        )
        token = VerificationToken.objects.create(
            user=user,
            token="tok",
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        request = _make_request(self.factory)
        self.adapter.pre_social_login(
            request, _make_sociallogin(email="registered@example.com")
        )
        token.refresh_from_db()
        self.assertTrue(token.is_used)

    def test_ambiguous_case_match_is_not_linked(self):
        """Two accounts differing only in case and no exact match: link neither."""
        for i, addr in enumerate(["Foo@example.com", "FOO@example.com"]):
            User.objects.create_user(email=addr, username=f"u{i}", password="pass")
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="foo@example.com")
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_exact_case_match_wins_over_other_case(self):
        """With case-variant duplicates, only the exact-case account is linked."""
        User.objects.create_user(
            email="Foo@example.com", username="other", password="pass"
        )
        exact = User.objects.create_user(
            email="foo@example.com",
            username="exact",
            password="pass",
            email_verified=True,
        )
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="foo@example.com")
        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_called_once_with(request, exact)

    def test_inactive_user_is_left_untouched(self):
        """A deactivated account is neither linked nor modified."""
        user = User.objects.create_user(
            email="registered@example.com",
            username="registered",
            password="pass",
            is_active=False,
        )
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="registered@example.com")
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertFalse(user.email_verified)

    def test_connect_process_is_left_to_allauth(self):
        """Connecting from account settings never links to another user."""
        User.objects.create_user(
            email="registered@example.com", username="registered", password="pass"
        )
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(
            email="registered@example.com", process="connect"
        )
        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_logged_in_user_is_left_to_allauth(self):
        """An authenticated request never links the social account elsewhere."""
        User.objects.create_user(
            email="registered@example.com", username="registered", password="pass"
        )
        request = _make_request(self.factory)
        request.user = User.objects.create_user(
            email="me@example.com", username="me", password="pass"
        )
        sociallogin = _make_sociallogin(email="registered@example.com")
        self.adapter.pre_social_login(request, sociallogin)
        sociallogin.connect.assert_not_called()

    def test_real_sociallogin_persists_link(self):
        """With allauth's real SocialLogin, a SocialAccount row is saved."""
        user = User.objects.create_user(
            email="registered@example.com",
            username="registered",
            password="pass",
            email_verified=True,
        )
        SocialApp.objects.create(
            provider="google", name="google", client_id="id", secret="s"
        ).sites.add(Site.objects.get_current())
        sociallogin = SocialLogin(
            user=User(email="registered@example.com"),
            account=SocialAccount(provider="google", uid="g-123"),
            email_addresses=[
                EmailAddress(email="registered@example.com", verified=True)
            ],
        )
        request = _make_request(self.factory)
        self.adapter.pre_social_login(request, sociallogin)
        self.assertTrue(sociallogin.is_existing)
        self.assertTrue(
            SocialAccount.objects.filter(
                user=user, provider="google", uid="g-123"
            ).exists()
        )

    def test_allows_signup_from_login_page_for_unknown_email(self):
        """#78: a new Google account signs up from the login page too."""
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="nobody@example.com", process="login")
        self.assertIsNone(self.adapter.pre_social_login(request, sociallogin))

    def test_new_account_needs_an_email_the_provider_verified(self):
        """#87 review: otherwise anyone could claim an address through the
        social signup form and keep a social login on it."""
        for email, verified in (("", True), ("claimed@example.com", False)):
            with self.subTest(email=email, verified=verified):
                request = _make_request(self.factory)
                sociallogin = _make_sociallogin(email=email, verified=verified)
                with self.assertRaises(ImmediateHttpResponse) as ctx:
                    self.adapter.pre_social_login(request, sociallogin)
                self.assertIn("/auth/signup/", ctx.exception.response["Location"])
                [message] = list(request._messages)
                self.assertIn("Registrujte se email adresom", str(message))

    def test_linking_revokes_social_logins_on_a_never_verified_account(self):
        """#87 review takeover: someone registered the owner's email first and
        attached their own Facebook; the owner's Google link must drop it."""
        squatter = User.objects.create_user(
            email="owner@example.com", username="owner", password="pw-12345678"
        )
        SocialAccount.objects.create(user=squatter, provider="facebook", uid="fb-1")
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="owner@example.com", verified=True)
        self.adapter.pre_social_login(request, sociallogin)
        self.assertFalse(
            SocialAccount.objects.filter(provider="facebook", uid="fb-1").exists()
        )
        squatter.refresh_from_db()
        self.assertFalse(squatter.has_usable_password())

    def test_linking_removes_other_addresses_of_a_never_verified_account(self):
        """A squatter's own verified address must not survive: a password
        reset sent to it would hand the account back (#87 review)."""
        squatter = User.objects.create_user(
            email="owner@example.com", username="owner", password="pw-12345678"
        )
        EmailAddress.objects.create(
            user=squatter, email="squatter@example.com", verified=True
        )
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="owner@example.com", verified=True)
        self.adapter.pre_social_login(request, sociallogin)
        self.assertEqual(
            list(
                EmailAddress.objects.filter(user=squatter).values_list(
                    "email", flat=True
                )
            ),
            ["owner@example.com"],
        )

    def test_failed_link_revokes_nothing(self):
        squatter = User.objects.create_user(
            email="owner@example.com", username="owner", password="pw-12345678"
        )
        SocialAccount.objects.create(user=squatter, provider="facebook", uid="fb-3")
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="owner@example.com", verified=True)
        sociallogin.connect.side_effect = RuntimeError("connect failed")
        with self.assertRaises(RuntimeError):
            self.adapter.pre_social_login(request, sociallogin)
        squatter.refresh_from_db()
        self.assertTrue(squatter.has_usable_password())
        self.assertTrue(SocialAccount.objects.filter(uid="fb-3").exists())

    def test_new_signup_for_another_users_verified_address_goes_to_login(self):
        other = User.objects.create_user(
            email="a@example.com", username="a", password="pw-12345678"
        )
        EmailAddress.objects.create(user=other, email="bob@gmail.com", verified=True)
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="bob@gmail.com", verified=True)
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(request, sociallogin)
        self.assertIn("/auth/login/", ctx.exception.response["Location"])
        [message] = list(request._messages)
        self.assertIn("povezana sa drugim nalogom", str(message))

    def test_linking_keeps_social_logins_on_a_verified_account(self):
        owner = User.objects.create_user(
            email="owner@example.com", username="owner", password="pw-12345678"
        )
        owner.email_verified = True
        owner.save()
        SocialAccount.objects.create(user=owner, provider="facebook", uid="fb-2")
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="owner@example.com", verified=True)
        self.adapter.pre_social_login(request, sociallogin)
        self.assertTrue(SocialAccount.objects.filter(uid="fb-2").exists())

    def test_email_verified_for_another_account_is_not_linked(self):
        """Case-variant duplicates: Foo@ is verified for A; B is foo@."""
        a = User.objects.create_user(
            email="Foo@example.com", username="a", password="pw-12345678"
        )
        a.email_verified = True
        a.save()
        b = User.objects.create_user(
            email="foo@example.com", username="b", password="pw-12345678"
        )
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="foo@example.com", verified=True)
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(request, sociallogin)
        self.assertIn("/auth/login/", ctx.exception.response["Location"])
        b.refresh_from_db()
        self.assertTrue(b.has_usable_password())


# ---------------------------------------------------------------------------
# SocialAccountAdapter.save_user
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSaveUser(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = SocialAccountAdapter()

    def _save(self, email, verified):
        from django.contrib.sessions.backends.db import SessionStore

        request = _make_request(self.factory)
        request.session = SessionStore()
        sociallogin = SocialLogin(
            user=User(email=email),
            account=SocialAccount(provider="google", uid=email),
            email_addresses=[
                EmailAddress(email=email, verified=verified, primary=True)
            ],
        )
        return self.adapter.save_user(request, sociallogin)

    def test_provider_verified_email_is_verified(self):
        user = self._save("social@example.com", verified=True)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertIsNotNone(user.email_verified_at)
        self.assertTrue(EmailAddress.objects.get(user=user).verified)

    def test_unverified_provider_email_stays_unverified(self):
        """#78: it used to be marked verified regardless."""
        user = self._save("fb@example.com", verified=False)
        user.refresh_from_db()
        self.assertFalse(user.email_verified)
        self.assertFalse(EmailAddress.objects.get(user=user).verified)

    def test_sets_no_seller_role(self):
        user = self._save("social@example.com", verified=True)
        self.assertFalse(user.is_seller)


# ---------------------------------------------------------------------------
# AccountAdapter.populate_username
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPopulateUsername(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = AccountAdapter()

    def _user_with_email(self, email):
        user = User(email=email)
        return user

    def test_generates_username_from_email_prefix(self):
        user = self._user_with_email("john.doe@example.com")
        self.adapter.populate_username(self.factory.get("/"), user)
        self.assertEqual(user.username, "john.doe")

    def test_appends_number_on_conflict(self):
        User.objects.create_user(email="a@b.com", username="john", password="x")
        user = self._user_with_email("john@example.com")
        self.adapter.populate_username(self.factory.get("/"), user)
        self.assertEqual(user.username, "john1")

    def test_increments_until_unique(self):
        User.objects.create_user(email="a@b.com", username="john", password="x")
        User.objects.create_user(email="c@d.com", username="john1", password="x")
        user = self._user_with_email("john@example.com")
        self.adapter.populate_username(self.factory.get("/"), user)
        self.assertEqual(user.username, "john2")
