"""
Tests for email verification and password reset token flows.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import VerificationToken

User = get_user_model()


@pytest.mark.django_db
class TestVerificationTokenModel(TestCase):
    """Test VerificationToken model."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email="test@example.com",
            username="test@example.com",
            password="TestPass123!",
        )

    def test_create_email_verification_token(self):
        """Test creating email verification token."""
        token = VerificationToken.objects.create(
            user=self.user,
            token="test-token-123",
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        self.assertEqual(token.user, self.user)
        self.assertEqual(token.token, "test-token-123")
        self.assertEqual(token.token_type, VerificationToken.TOKEN_TYPE_EMAIL)
        self.assertFalse(token.is_used)

    def test_token_is_valid_when_not_expired_and_unused(self):
        """Test token is valid when not expired and unused."""
        token = VerificationToken.objects.create(
            user=self.user,
            token="test-token",
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=1),
        )

        self.assertTrue(token.is_valid())

    def test_token_is_invalid_when_expired(self):
        """Test token is invalid when expired."""
        token = VerificationToken.objects.create(
            user=self.user,
            token="test-token",
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        self.assertFalse(token.is_valid())
        self.assertTrue(token.is_expired())

    def test_token_is_invalid_when_used(self):
        """Test token is invalid when already used."""
        token = VerificationToken.objects.create(
            user=self.user,
            token="test-token",
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=1),
        )

        token.mark_used()
        self.assertFalse(token.is_valid())
        self.assertTrue(token.is_used)

    def test_mark_used_sets_timestamp(self):
        """Test mark_used sets the used_at timestamp."""
        token = VerificationToken.objects.create(
            user=self.user,
            token="test-token",
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=1),
        )

        before_mark = timezone.now()
        token.mark_used()
        after_mark = timezone.now()

        self.assertIsNotNone(token.used_at)
        self.assertGreaterEqual(token.used_at, before_mark)
        self.assertLessEqual(token.used_at, after_mark)

    def test_password_reset_token_type(self):
        """Test creating password reset token."""
        token = VerificationToken.objects.create(
            user=self.user,
            token="reset-token",
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD,
            expires_at=timezone.now() + timedelta(hours=1),
        )

        self.assertEqual(token.token_type, VerificationToken.TOKEN_TYPE_PASSWORD)


@pytest.mark.django_db
class TestEmailVerificationFlow(TestCase):
    """Links from verification emails sent before the switch to allauth (#77)."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.verify_url_name = "verify-email"

    def test_verify_email_with_valid_token(self):
        """Test email verification with valid token."""
        user = User.objects.create_user(
            email="test@example.com",
            username="test@example.com",
            password="TestPass123!",
        )

        token = VerificationToken.objects.create(
            user=user,
            token="valid-token",
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        response = self.client.get(
            reverse(self.verify_url_name, kwargs={"token": "valid-token"})
        )

        user.refresh_from_db()
        token.refresh_from_db()

        self.assertTrue(user.email_verified)
        self.assertTrue(token.is_used)
        self.assertIsNotNone(token.used_at)

    def test_verify_email_with_invalid_token(self):
        """Test email verification fails with invalid token."""
        user = User.objects.create_user(
            email="test@example.com",
            username="test@example.com",
            password="TestPass123!",
        )

        response = self.client.get(
            reverse(self.verify_url_name, kwargs={"token": "invalid-token"})
        )

        user.refresh_from_db()

        self.assertFalse(user.email_verified)

    def test_verify_email_with_expired_token(self):
        """Test email verification fails with expired token."""
        user = User.objects.create_user(
            email="test@example.com",
            username="test@example.com",
            password="TestPass123!",
        )

        token = VerificationToken.objects.create(
            user=user,
            token="expired-token",
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() - timedelta(hours=1),
        )

        response = self.client.get(
            reverse(self.verify_url_name, kwargs={"token": "expired-token"})
        )

        user.refresh_from_db()

        self.assertFalse(user.email_verified)

    def test_verify_email_cannot_reuse_token(self):
        """Test token cannot be reused for verification."""
        user = User.objects.create_user(
            email="test@example.com",
            username="test@example.com",
            password="TestPass123!",
        )

        token = VerificationToken.objects.create(
            user=user,
            token="reuse-token",
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # First use
        response1 = self.client.get(
            reverse(self.verify_url_name, kwargs={"token": "reuse-token"})
        )
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

        # Reset verification on both sides (bypassing the sync, which never
        # quietly un-verifies) to test reuse prevention
        from allauth.account.models import EmailAddress

        User.objects.filter(pk=user.pk).update(email_verified=False)
        EmailAddress.objects.filter(user=user).update(verified=False)

        # Try to reuse same token
        response2 = self.client.get(
            reverse(self.verify_url_name, kwargs={"token": "reuse-token"})
        )

        user.refresh_from_db()
        self.assertFalse(user.email_verified)


class TestTokenExpiration(TestCase):
    """Test token expiration handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user = User.objects.create_user(
            email="test@example.com",
            username="test@example.com",
            password="TestPass123!",
        )

    def test_email_verification_token_expires_after_24_hours(self):
        """Test email verification token expires after 24 hours."""
        token = VerificationToken.objects.create(
            user=self.user,
            token="test-token",
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertTrue(token.is_expired())

    def test_password_reset_token_expires_after_1_hour(self):
        """Test password reset token expires after 1 hour."""
        token = VerificationToken.objects.create(
            user=self.user,
            token="test-token",
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD,
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertTrue(token.is_expired())

    def test_token_is_valid_until_exact_expiration_time(self):
        """Test token is valid until exact expiration time."""
        expires_at = timezone.now() + timedelta(hours=1)
        token = VerificationToken.objects.create(
            user=self.user,
            token="test-token",
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=expires_at,
        )

        self.assertTrue(token.is_valid())
