"""
Tests for User model and authentication.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import authenticate
from .models import User


@pytest.mark.django_db
class TestUserModel(TestCase):
    """Test User model functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.user_data = {
            'email': 'test@example.com',
            'username': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User',
        }

    def test_create_user(self):
        """Test creating a basic user."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_blank_email_allowed(self):
        """Test that creating user with blank email is allowed (username-based)."""
        user = User.objects.create_user(
            email='',
            username='test',
            password='testpass123'
        )
        self.assertEqual(user.username, 'test')

    def test_create_superuser(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(
            email='admin@example.com',
            username='admin@example.com',
            password='adminpass123'
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_user_is_buyer_by_default(self):
        """Test that new users are buyers by default."""
        user = User.objects.create_user(**self.user_data)
        self.assertTrue(user.is_buyer)
        self.assertFalse(user.is_seller)

    def test_user_can_be_seller(self):
        """Test setting user as seller."""
        user = User.objects.create_user(**self.user_data)
        user.is_seller = True
        user.save()
        
        self.assertTrue(user.is_seller)
        self.assertTrue(user.is_buyer)

    def test_email_verified_defaults_to_false(self):
        """Test that email_verified defaults to False."""
        user = User.objects.create_user(**self.user_data)
        self.assertFalse(user.email_verified)
        self.assertIsNone(user.email_verified_at)

    def test_user_string_representation(self):
        """Test user string representation returns email."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(str(user), 'test@example.com')

    def test_user_password_hashing(self):
        """Test that password is hashed when saved."""
        user = User.objects.create_user(**self.user_data)
        self.assertNotEqual(user.password, 'testpass123')
        self.assertTrue(user.check_password('testpass123'))

    def test_authenticate_user(self):
        """Test authenticating user with email."""
        User.objects.create_user(**self.user_data)
        user = authenticate(username='test@example.com', password='testpass123')
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'test@example.com')

    def test_authenticate_with_wrong_password(self):
        """Test authentication fails with wrong password."""
        User.objects.create_user(**self.user_data)
        user = authenticate(username='test@example.com', password='wrongpass')
        self.assertIsNone(user)

    def test_authenticate_nonexistent_user(self):
        """Test authentication fails for nonexistent user."""
        user = authenticate(username='nonexistent@example.com', password='pass')
        self.assertIsNone(user)

    def test_unique_email_constraint(self):
        """Test that email field is unique."""
        User.objects.create_user(**self.user_data)
        
        with self.assertRaises(Exception):
            User.objects.create_user(**self.user_data)

    def test_user_inactive(self):
        """Test creating inactive user."""
        user = User.objects.create_user(**self.user_data)
        user.is_active = False
        user.save()
        
        # Inactive users cannot authenticate
        auth_user = authenticate(username='test@example.com', password='testpass123')
        self.assertIsNone(auth_user)

    def test_has_complete_seller_profile_without_profile(self):
        """Test has_complete_seller_profile returns False without profile."""
        user = User.objects.create_user(**self.user_data)
        user.is_seller = True
        user.save()
        
        self.assertFalse(user.has_complete_seller_profile())

    def test_has_complete_seller_profile_non_seller(self):
        """Test has_complete_seller_profile returns False for non-seller."""
        user = User.objects.create_user(**self.user_data)
        self.assertFalse(user.has_complete_seller_profile())

    def test_user_ordering(self):
        """Test users are ordered by date_joined descending."""
        user1 = User.objects.create_user(
            email='user1@example.com',
            username='user1@example.com',
            password='pass123'
        )
        user2 = User.objects.create_user(
            email='user2@example.com',
            username='user2@example.com',
            password='pass123'
        )
        
        users = User.objects.all()
        self.assertEqual(users[0].id, user2.id)  # Latest first
        self.assertEqual(users[1].id, user1.id)

    def test_user_with_first_and_last_name(self):
        """Test creating user with first and last name."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')

    def test_user_can_be_both_buyer_and_seller(self):
        """Test user can be both buyer and seller."""
        user = User.objects.create_user(**self.user_data)
        user.is_seller = True
        user.save()
        
        self.assertTrue(user.is_buyer)
        self.assertTrue(user.is_seller)
