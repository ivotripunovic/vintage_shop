"""
Tests for social auth adapters.
"""

import pytest
from unittest.mock import MagicMock, patch

from django.test import TestCase, RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage

from allauth.core.exceptions import ImmediateHttpResponse

from .adapters import AccountAdapter, SocialAccountAdapter
from .models import User


def _make_request(factory):
    request = factory.get("/")
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def _make_sociallogin(*, is_existing=False, email="user@example.com", process="login"):
    sociallogin = MagicMock()
    sociallogin.is_existing = is_existing
    sociallogin.user.email = email
    sociallogin.state = {"process": process}
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

    def test_allows_login_when_email_matches_existing_user(self):
        """Login passes if the provider email matches a registered account."""
        User.objects.create_user(
            email="registered@example.com",
            username="registered",
            password="pass",
        )
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="registered@example.com")
        self.adapter.pre_social_login(request, sociallogin)  # must not raise

    def test_blocks_login_for_unknown_email(self):
        """Login is blocked and redirects to register when email is not registered."""
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="nobody@example.com")
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(request, sociallogin)
        response = ctx.exception.response
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/register/", response["Location"])

    def test_blocks_login_when_provider_returns_no_email(self):
        """Login is blocked when the provider gives no email."""
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin(email="")
        with self.assertRaises(ImmediateHttpResponse) as ctx:
            self.adapter.pre_social_login(request, sociallogin)
        self.assertEqual(ctx.exception.response.status_code, 302)


# ---------------------------------------------------------------------------
# SocialAccountAdapter.save_user
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSaveUser(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = SocialAccountAdapter()

    def test_save_user_marks_buyer_and_verified_email(self):
        """Social signup sets is_buyer=True and email_verified=True."""
        user = User.objects.create(email="social@example.com", username="social")
        request = _make_request(self.factory)
        sociallogin = _make_sociallogin()

        with patch(
            "allauth.socialaccount.adapter.DefaultSocialAccountAdapter.save_user",
            return_value=user,
        ):
            self.adapter.save_user(request, sociallogin)

        user.refresh_from_db()
        self.assertTrue(user.is_buyer)
        self.assertTrue(user.email_verified)
        self.assertIsNotNone(user.email_verified_at)


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
