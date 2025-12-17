"""
Tests for user authentication forms.
"""

import pytest
from django.test import TestCase
from .forms import (
    UserRegistrationForm,
    UserLoginForm,
    UserPasswordResetForm,
    UserPasswordSetForm,
    UserPasswordChangeForm,
)
from .models import User


@pytest.mark.django_db
class TestUserRegistrationForm(TestCase):
    """Test UserRegistrationForm."""

    def test_valid_registration(self):
        """Test valid registration form submission."""
        form_data = {
            'email': 'newuser@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'buyer',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_registration_creates_user(self):
        """Test that form saves user to database."""
        form_data = {
            'email': 'newuser@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'both',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        user = form.save()
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertTrue(user.is_seller)
        self.assertTrue(user.is_buyer)

    def test_registration_both_user_type(self):
        """Test registration with both buyer and seller."""
        form_data = {
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'both',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        user = form.save()
        self.assertTrue(user.is_buyer)
        self.assertTrue(user.is_seller)

    def test_registration_buyer_only(self):
        """Test registration as buyer only."""
        form_data = {
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'buyer',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        user = form.save()
        self.assertTrue(user.is_buyer)
        self.assertFalse(user.is_seller)

    def test_registration_duplicate_email(self):
        """Test registration fails with duplicate email."""
        User.objects.create_user(
            email='existing@example.com',
            username='existing@example.com',
            password='pass123'
        )
        
        form_data = {
            'email': 'existing@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'buyer',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_registration_password_mismatch(self):
        """Test registration fails when passwords don't match."""
        form_data = {
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'DifferentPass123!',
            'user_type': 'buyer',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    def test_registration_invalid_email(self):
        """Test registration fails with invalid email."""
        form_data = {
            'email': 'not-an-email',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'buyer',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_registration_optional_name_fields(self):
        """Test registration with optional name fields."""
        form_data = {
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'user_type': 'buyer',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())


@pytest.mark.django_db
class TestUserLoginForm(TestCase):
    """Test UserLoginForm."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='TestPass123!'
        )

    def test_valid_login(self):
        """Test valid login form."""
        form_data = {
            'email': 'test@example.com',
            'password': 'TestPass123!',
            'remember_me': False,
        }
        form = UserLoginForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertIsNotNone(form.get_user())

    def test_login_wrong_password(self):
        """Test login fails with wrong password."""
        form_data = {
            'email': 'test@example.com',
            'password': 'WrongPassword',
            'remember_me': False,
        }
        form = UserLoginForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_login_nonexistent_email(self):
        """Test login fails with nonexistent email."""
        form_data = {
            'email': 'nonexistent@example.com',
            'password': 'TestPass123!',
            'remember_me': False,
        }
        form = UserLoginForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_login_inactive_user(self):
        """Test login fails for inactive user."""
        self.user.is_active = False
        self.user.save()
        
        form_data = {
            'email': 'test@example.com',
            'password': 'TestPass123!',
            'remember_me': False,
        }
        form = UserLoginForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_login_remember_me(self):
        """Test login form with remember_me option."""
        form_data = {
            'email': 'test@example.com',
            'password': 'TestPass123!',
            'remember_me': True,
        }
        form = UserLoginForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_login_missing_email(self):
        """Test login form with missing email."""
        form_data = {
            'email': '',
            'password': 'TestPass123!',
        }
        form = UserLoginForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_login_missing_password(self):
        """Test login form with missing password."""
        form_data = {
            'email': 'test@example.com',
            'password': '',
        }
        form = UserLoginForm(data=form_data)
        self.assertFalse(form.is_valid())


@pytest.mark.django_db
class TestUserPasswordResetForm(TestCase):
    """Test UserPasswordResetForm."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='OldPass123!'
        )

    def test_valid_reset_request(self):
        """Test valid password reset request."""
        form_data = {
            'email': 'test@example.com',
        }
        form = UserPasswordResetForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.get_user(), self.user)

    def test_reset_nonexistent_email(self):
        """Test reset request with nonexistent email."""
        form_data = {
            'email': 'nonexistent@example.com',
        }
        form = UserPasswordResetForm(data=form_data)
        self.assertFalse(form.is_valid())

    def test_reset_invalid_email(self):
        """Test reset request with invalid email format."""
        form_data = {
            'email': 'not-an-email',
        }
        form = UserPasswordResetForm(data=form_data)
        self.assertFalse(form.is_valid())


@pytest.mark.django_db
class TestUserPasswordChangeForm(TestCase):
    """Test UserPasswordChangeForm."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='OldPass123!'
        )

    def test_valid_password_change(self):
        """Test valid password change."""
        form_data = {
            'old_password': 'OldPass123!',
            'new_password1': 'NewPass123!',
            'new_password2': 'NewPass123!',
        }
        form = UserPasswordChangeForm(user=self.user, data=form_data)
        self.assertTrue(form.is_valid())

    def test_password_change_wrong_old_password(self):
        """Test password change fails with wrong old password."""
        form_data = {
            'old_password': 'WrongPass',
            'new_password1': 'NewPass123!',
            'new_password2': 'NewPass123!',
        }
        form = UserPasswordChangeForm(user=self.user, data=form_data)
        self.assertFalse(form.is_valid())

    def test_password_change_new_passwords_dont_match(self):
        """Test password change fails when new passwords don't match."""
        form_data = {
            'old_password': 'OldPass123!',
            'new_password1': 'NewPass123!',
            'new_password2': 'DifferentPass123!',
        }
        form = UserPasswordChangeForm(user=self.user, data=form_data)
        self.assertFalse(form.is_valid())

    def test_password_change_new_same_as_old(self):
        """Test password change fails when new password is same as old."""
        form_data = {
            'old_password': 'OldPass123!',
            'new_password1': 'OldPass123!',
            'new_password2': 'OldPass123!',
        }
        form = UserPasswordChangeForm(user=self.user, data=form_data)
        self.assertFalse(form.is_valid())

    def test_password_change_saves_correctly(self):
        """Test that password change saves correctly."""
        form_data = {
            'old_password': 'OldPass123!',
            'new_password1': 'NewPass123!',
            'new_password2': 'NewPass123!',
        }
        form = UserPasswordChangeForm(user=self.user, data=form_data)
        self.assertTrue(form.is_valid())
        
        form.save()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass123!'))
        self.assertFalse(self.user.check_password('OldPass123!'))
