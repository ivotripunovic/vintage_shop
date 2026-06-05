"""
Tests for user authentication views.
"""

import pytest
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.utils.crypto import get_random_string
from django.utils import timezone
from datetime import timedelta
from .models import VerificationToken

User = get_user_model()


@pytest.mark.django_db
class TestRegistrationView(TestCase):
    """Test user registration view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.register_url = reverse('register')

    def test_register_page_loads(self):
        """Test registration page loads."""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')
        self.assertIn('form', response.context)

    def test_register_authenticated_user_redirects(self):
        """Test authenticated user is redirected from registration page."""
        user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='pass123'
        )
        self.client.force_login(user)
        
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 302)

    @patch('users.views.send_mail')
    def test_register_valid_submission(self, mock_send_mail):
        """Test valid registration submission."""
        response = self.client.post(self.register_url, {
            'email': 'newuser@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'buyer',
        })
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())

    @patch('users.views.send_mail')
    def test_register_creates_buyer(self, mock_send_mail):
        """Registration always creates a user with buyer role."""
        self.client.post(self.register_url, {
            'email': 'buyer@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })

        user = User.objects.get(email='buyer@example.com')
        self.assertTrue(user.is_buyer)

    @patch('users.views.send_mail')
    def test_register_creates_seller(self, mock_send_mail):
        """Registration always creates a user with seller role."""
        self.client.post(self.register_url, {
            'email': 'seller@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })

        user = User.objects.get(email='seller@example.com')
        self.assertTrue(user.is_seller)

    @patch('users.views.send_mail')
    def test_register_creates_both_buyer_seller(self, mock_send_mail):
        """Test registration creates both buyer and seller."""
        self.client.post(self.register_url, {
            'email': 'both@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'both',
        })
        
        user = User.objects.get(email='both@example.com')
        self.assertTrue(user.is_buyer)
        self.assertTrue(user.is_seller)

    def test_register_duplicate_email(self):
        """Test registration fails with duplicate email."""
        User.objects.create_user(
            email='existing@example.com',
            username='existing@example.com',
            password='pass123'
        )
        
        response = self.client.post(self.register_url, {
            'email': 'existing@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'buyer',
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='existing@example.com').count() > 1)

    def test_register_password_mismatch(self):
        """Test registration fails when passwords don't match."""
        response = self.client.post(self.register_url, {
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'DifferentPass123!',
            'user_type': 'buyer',
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='newuser@example.com').exists())

    @patch('users.views.send_mail')
    def test_register_email_not_verified_initially(self, mock_send_mail):
        """Test newly registered user email is not verified."""
        self.client.post(self.register_url, {
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'buyer',
        })
        
        user = User.objects.get(email='newuser@example.com')
        self.assertFalse(user.email_verified)


@pytest.mark.django_db
class TestLoginView(TestCase):
    """Test user login view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.login_url = reverse('login')
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!',
        )
        self.user.email_verified = True
        self.user.save()

    def test_login_page_loads(self):
        """Test login page loads."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')

    def test_login_authenticated_user_redirects(self):
        """Test authenticated user is redirected from login page."""
        self.client.force_login(self.user)
        
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 302)

    def test_login_valid_credentials(self):
        """Test login with valid credentials."""
        response = self.client.post(self.login_url, {
            'email': 'test@example.com',
            'password': 'TestPass123!',
            'remember_me': False,
        }, follow=True)
        
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_invalid_password(self):
        """Test login with invalid password."""
        response = self.client.post(self.login_url, {
            'email': 'test@example.com',
            'password': 'WrongPassword',
            'remember_me': False,
        })
        
        self.assertEqual(response.status_code, 200)

    def test_login_nonexistent_email(self):
        """Test login with nonexistent email."""
        response = self.client.post(self.login_url, {
            'email': 'nonexistent@example.com',
            'password': 'TestPass123!',
            'remember_me': False,
        })
        
        self.assertEqual(response.status_code, 200)

    def test_login_unverified_email_prevents_login(self):
        """Test login with unverified email prevents login."""
        unverified_user = User.objects.create_user(
            email='unverified@example.com',
            username='unverified@example.com',
            password='TestPass123!',
        )
        
        response = self.client.post(self.login_url, {
            'email': 'unverified@example.com',
            'password': 'TestPass123!',
            'remember_me': False,
        }, follow=True)
        
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_inactive_user(self):
        """Test login with inactive user."""
        inactive_user = User.objects.create_user(
            email='inactive@example.com',
            username='inactive@example.com',
            password='TestPass123!',
        )
        inactive_user.is_active = False
        inactive_user.save()
        
        response = self.client.post(self.login_url, {
            'email': 'inactive@example.com',
            'password': 'TestPass123!',
            'remember_me': False,
        })
        
        self.assertEqual(response.status_code, 200)


@pytest.mark.django_db
class TestLogoutView(TestCase):
    """Test user logout view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.logout_url = reverse('logout')
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )

    def test_logout_authenticated_user(self):
        """Test logout for authenticated user."""
        self.client.force_login(self.user)
        
        response = self.client.get(self.logout_url, follow=True)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_redirects_to_home(self):
        """Test logout redirects to home."""
        self.client.force_login(self.user)
        
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)

    def test_logout_unauthenticated_user_redirects(self):
        """Test unauthenticated user accessing logout redirects to login."""
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)


@pytest.mark.django_db
class TestPasswordResetView(TestCase):
    """Test password reset views."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='OldPass123!'
        )
        self.reset_request_url = reverse('password-reset-request')

    def test_reset_request_page_loads(self):
        """Test password reset request page loads."""
        response = self.client.get(self.reset_request_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/password_reset_request.html')

    def test_reset_request_valid_email(self):
        """Test password reset with valid email."""
        response = self.client.post(self.reset_request_url, {
            'email': 'test@example.com',
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)

    def test_reset_request_nonexistent_email(self):
        """Test password reset with nonexistent email."""
        response = self.client.post(self.reset_request_url, {
            'email': 'nonexistent@example.com',
        })
        
        self.assertEqual(response.status_code, 200)

    def test_reset_request_authenticated_user_redirects(self):
        """Test authenticated user is redirected from reset request page."""
        self.client.force_login(self.user)

        response = self.client.get(self.reset_request_url)
        self.assertEqual(response.status_code, 302)

    def _make_reset_token(self):
        token = get_random_string(50)
        VerificationToken.objects.create(
            user=self.user,
            token=token,
            token_type=VerificationToken.TOKEN_TYPE_PASSWORD,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        return token

    def test_reset_confirm_page_loads(self):
        """Test password reset confirm page loads with a valid token."""
        token = self._make_reset_token()
        response = self.client.get(reverse('password-reset-confirm', args=[token]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/password_reset_confirm.html')

    def test_reset_confirm_renders_password_fields(self):
        """Both password input fields must be present in the rendered HTML."""
        token = self._make_reset_token()
        response = self.client.get(reverse('password-reset-confirm', args=[token]))
        self.assertContains(response, 'name="new_password1"')
        self.assertContains(response, 'name="new_password2"')

    def test_reset_confirm_invalid_token_redirects(self):
        """Invalid token redirects back to reset request page."""
        response = self.client.get(reverse('password-reset-confirm', args=['badtoken']))
        self.assertRedirects(response, reverse('password-reset-request'))

    def test_reset_confirm_sets_new_password(self):
        """Submitting valid passwords changes the user's password."""
        token = self._make_reset_token()
        url = reverse('password-reset-confirm', args=[token])
        response = self.client.post(url, {
            'new_password1': 'NewSecure123!',
            'new_password2': 'NewSecure123!',
        }, follow=True)
        self.assertRedirects(response, reverse('login'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecure123!'))


@pytest.mark.django_db
class TestPasswordChangeView(TestCase):
    """Test password change view for authenticated users."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='OldPass123!'
        )
        self.change_url = reverse('password-change')

    def test_password_change_page_requires_login(self):
        """Test password change page requires login."""
        response = self.client.get(self.change_url)
        self.assertEqual(response.status_code, 302)

    def test_valid_password_change_submission(self):
        """Test valid password change submission."""
        self.client.force_login(self.user)
        
        response = self.client.post(self.change_url, {
            'old_password': 'OldPass123!',
            'new_password1': 'NewPass123!',
            'new_password2': 'NewPass123!',
        }, follow=True)
        
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass123!'))

    def test_password_change_validates_old_password(self):
        """Test password change validates old password."""
        self.client.force_login(self.user)
        
        response = self.client.post(self.change_url, {
            'old_password': 'WrongPass',
            'new_password1': 'NewPass123!',
            'new_password2': 'NewPass123!',
        })
        
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password('NewPass123!'))


@pytest.mark.django_db
class TestAccountSettingsView(TestCase):
    """Test account settings view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )
        self.settings_url = reverse('account-settings')

    def test_account_settings_requires_login(self):
        """Test account settings page requires login."""
        response = self.client.get(self.settings_url)
        self.assertEqual(response.status_code, 302)

    def test_account_settings_loads_for_authenticated(self):
        """Test account settings page loads for authenticated user."""
        self.client.force_login(self.user)
        
        response = self.client.get(self.settings_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/account_settings.html')
