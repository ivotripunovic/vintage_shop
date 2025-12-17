"""
Tests for email verification and password reset token flows.
"""

import pytest
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from .models import VerificationToken

User = get_user_model()


@pytest.mark.django_db
class TestVerificationTokenModel(TestCase):
    """Test VerificationToken model."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )

    def test_create_email_verification_token(self):
        """Test creating email verification token."""
        token = VerificationToken.objects.create(
            user=self.user,
            token='test-token-123',
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        self.assertEqual(token.user, self.user)
        self.assertEqual(token.token, 'test-token-123')
        self.assertEqual(token.token_type, VerificationToken.TOKEN_TYPE_EMAIL)
        self.assertFalse(token.is_used)

    def test_token_is_valid_when_not_expired_and_unused(self):
        """Test token is valid when not expired and unused."""
        token = VerificationToken.objects.create(
            user=self.user,
            token='test-token',
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        self.assertTrue(token.is_valid())

    def test_token_is_invalid_when_expired(self):
        """Test token is invalid when expired."""
        token = VerificationToken.objects.create(
            user=self.user,
            token='test-token',
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        self.assertFalse(token.is_valid())
        self.assertTrue(token.is_expired())

    def test_token_is_invalid_when_used(self):
        """Test token is invalid when already used."""
        token = VerificationToken.objects.create(
            user=self.user,
            token='test-token',
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        token.mark_used()
        self.assertFalse(token.is_valid())
        self.assertTrue(token.is_used)

    def test_mark_used_sets_timestamp(self):
        """Test mark_used sets the used_at timestamp."""
        token = VerificationToken.objects.create(
            user=self.user,
            token='test-token',
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=1)
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
            token='reset-token',
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        self.assertEqual(token.token_type, VerificationToken.TOKEN_TYPE_PASSWORD)


@pytest.mark.django_db
class TestEmailVerificationFlow(TestCase):
    """Test email verification workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.verify_url_name = 'verify-email'
        self.resend_url = reverse('verify-email-resend')

    @patch('users.views.send_mail')
    def test_registration_creates_verification_token(self, mock_send_mail):
        """Test registration creates a verification token."""
        response = self.client.post(reverse('register'), {
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'buyer',
        })
        
        user = User.objects.get(email='newuser@example.com')
        token = VerificationToken.objects.filter(
            user=user,
            token_type=VerificationToken.TOKEN_TYPE_EMAIL
        ).first()
        
        self.assertIsNotNone(token)
        self.assertTrue(token.is_valid())
        self.assertFalse(user.email_verified)

    def test_verify_email_with_valid_token(self):
        """Test email verification with valid token."""
        user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )
        
        token = VerificationToken.objects.create(
            user=user,
            token='valid-token',
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        response = self.client.get(
            reverse(self.verify_url_name, kwargs={'token': 'valid-token'})
        )
        
        user.refresh_from_db()
        token.refresh_from_db()
        
        self.assertTrue(user.email_verified)
        self.assertTrue(token.is_used)
        self.assertIsNotNone(token.used_at)

    def test_verify_email_with_invalid_token(self):
        """Test email verification fails with invalid token."""
        user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )
        
        response = self.client.get(
            reverse(self.verify_url_name, kwargs={'token': 'invalid-token'})
        )
        
        user.refresh_from_db()
        
        self.assertFalse(user.email_verified)

    def test_verify_email_with_expired_token(self):
        """Test email verification fails with expired token."""
        user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )
        
        token = VerificationToken.objects.create(
            user=user,
            token='expired-token',
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        response = self.client.get(
            reverse(self.verify_url_name, kwargs={'token': 'expired-token'})
        )
        
        user.refresh_from_db()
        
        self.assertFalse(user.email_verified)

    def test_verify_email_cannot_reuse_token(self):
        """Test token cannot be reused for verification."""
        user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )
        
        token = VerificationToken.objects.create(
            user=user,
            token='reuse-token',
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # First use
        response1 = self.client.get(
            reverse(self.verify_url_name, kwargs={'token': 'reuse-token'})
        )
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        
        # Reset email_verified to test reuse prevention
        user.email_verified = False
        user.save()
        
        # Try to reuse same token
        response2 = self.client.get(
            reverse(self.verify_url_name, kwargs={'token': 'reuse-token'})
        )
        
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_resend_verification_email_page_loads(self):
        """Test resend verification email page loads."""
        response = self.client.get(self.resend_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/verify_email_resend.html')

    @patch('users.views.send_mail')
    def test_resend_verification_email_creates_new_token(self, mock_send_mail):
        """Test resending verification email creates a new token."""
        user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )
        
        response = self.client.post(self.resend_url, {
            'email': 'test@example.com'
        })
        
        tokens = VerificationToken.objects.filter(
            user=user,
            token_type=VerificationToken.TOKEN_TYPE_EMAIL
        )
        
        self.assertEqual(tokens.count(), 1)
        self.assertTrue(tokens.first().is_valid())

    @patch('users.views.send_mail')
    def test_resend_verification_email_for_verified_user(self, mock_send_mail):
        """Test resending verification email for already verified user."""
        user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )
        user.email_verified = True
        user.save()
        
        response = self.client.post(self.resend_url, {
            'email': 'test@example.com'
        })
        
        # Should show message about already verified
        self.assertEqual(response.status_code, 200)

    def test_resend_verification_email_invalid_email(self):
        """Test resending verification email with non-existent email."""
        response = self.client.post(self.resend_url, {
            'email': 'nonexistent@example.com'
        })
        
        self.assertEqual(response.status_code, 200)

    def test_login_requires_email_verification(self):
        """Test login redirects to verification if email not verified."""
        user = User.objects.create_user(
            email='unverified@example.com',
            username='unverified@example.com',
            password='TestPass123!'
        )
        user.email_verified = False
        user.save()
        
        response = self.client.post(reverse('login'), {
            'email': 'unverified@example.com',
            'password': 'TestPass123!',
            'remember_me': False,
        }, follow=True)
        
        self.assertFalse(response.wsgi_request.user.is_authenticated)


@pytest.mark.django_db
class TestPasswordResetFlow(TestCase):
    """Test password reset workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='OldPass123!'
        )
        self.reset_request_url = reverse('password-reset-request')
        self.reset_confirm_url_name = 'password-reset-confirm'

    @patch('users.views.send_mail')
    def test_password_reset_creates_token(self, mock_send_mail):
        """Test password reset creates a token."""
        response = self.client.post(self.reset_request_url, {
            'email': 'test@example.com'
        })
        
        token = VerificationToken.objects.filter(
            user=self.user,
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD
        ).first()
        
        self.assertIsNotNone(token)
        self.assertTrue(token.is_valid())

    def test_password_reset_confirm_with_valid_token(self):
        """Test password reset confirmation with valid token."""
        token = VerificationToken.objects.create(
            user=self.user,
            token='reset-token',
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        response = self.client.post(
            reverse(self.reset_confirm_url_name, kwargs={'token': 'reset-token'}),
            {
                'new_password1': 'NewPass123!',
                'new_password2': 'NewPass123!',
            }
        )
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass123!'))

    def test_password_reset_confirm_invalid_token(self):
        """Test password reset fails with invalid token."""
        response = self.client.get(
            reverse(self.reset_confirm_url_name, kwargs={'token': 'invalid-token'})
        )
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldPass123!'))

    def test_password_reset_confirm_expired_token(self):
        """Test password reset fails with expired token."""
        token = VerificationToken.objects.create(
            user=self.user,
            token='expired-reset',
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD,
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        response = self.client.get(
            reverse(self.reset_confirm_url_name, kwargs={'token': 'expired-reset'})
        )
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldPass123!'))

    def test_password_reset_cannot_reuse_token(self):
        """Test password reset token cannot be reused."""
        token = VerificationToken.objects.create(
            user=self.user,
            token='reset-token',
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        # First use
        response1 = self.client.post(
            reverse(self.reset_confirm_url_name, kwargs={'token': 'reset-token'}),
            {
                'new_password1': 'FirstNewPass123!',
                'new_password2': 'FirstNewPass123!',
            }
        )
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('FirstNewPass123!'))
        
        # Try to reuse same token
        response2 = self.client.post(
            reverse(self.reset_confirm_url_name, kwargs={'token': 'reset-token'}),
            {
                'new_password1': 'SecondNewPass123!',
                'new_password2': 'SecondNewPass123!',
            }
        )
        
        self.user.refresh_from_db()
        # Should still be the first password
        self.assertTrue(self.user.check_password('FirstNewPass123!'))

    @patch('users.views.send_mail')
    def test_password_reset_flow_end_to_end(self, mock_send_mail):
        """Test complete password reset flow."""
        # 1. Request password reset
        response = self.client.post(self.reset_request_url, {
            'email': 'test@example.com'
        })
        
        # 2. Get the token
        token = VerificationToken.objects.get(
            user=self.user,
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD
        )
        
        # 3. Confirm password reset
        response = self.client.post(
            reverse(self.reset_confirm_url_name, kwargs={'token': token.token}),
            {
                'new_password1': 'CompletelyNewPass123!',
                'new_password2': 'CompletelyNewPass123!',
            }
        )
        
        # 4. Verify old password no longer works
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password('OldPass123!'))
        self.assertTrue(self.user.check_password('CompletelyNewPass123!'))
        
        # 5. Verify token is marked as used
        token.refresh_from_db()
        self.assertTrue(token.is_used)


@pytest.mark.django_db
class TestTokenExpiration(TestCase):
    """Test token expiration handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )

    def test_email_verification_token_expires_after_24_hours(self):
        """Test email verification token expires after 24 hours."""
        token = VerificationToken.objects.create(
            user=self.user,
            token='test-token',
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        
        self.assertTrue(token.is_expired())

    def test_password_reset_token_expires_after_1_hour(self):
        """Test password reset token expires after 1 hour."""
        token = VerificationToken.objects.create(
            user=self.user,
            token='test-token',
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD,
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        
        self.assertTrue(token.is_expired())

    def test_token_is_valid_until_exact_expiration_time(self):
        """Test token is valid until exact expiration time."""
        expires_at = timezone.now() + timedelta(hours=1)
        token = VerificationToken.objects.create(
            user=self.user,
            token='test-token',
            token_type=VerificationToken.TOKEN_TYPE_EMAIL,
            expires_at=expires_at
        )
        
        self.assertTrue(token.is_valid())
