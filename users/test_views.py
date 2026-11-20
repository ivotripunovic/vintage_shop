"""
Tests for the account settings page. Auth flows (allauth) are tested in
users/test_auth_flows.py.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


@pytest.mark.django_db
class TestAccountSettingsView(TestCase):
    """Test account settings view."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user = User.objects.create_user(
            email="test@example.com",
            username="test@example.com",
            password="TestPass123!",
        )
        self.settings_url = reverse("account-settings")

    def test_account_settings_requires_login(self):
        """Test account settings page requires login."""
        response = self.client.get(self.settings_url)
        self.assertEqual(response.status_code, 302)

    def test_account_settings_loads_for_authenticated(self):
        """Test account settings page loads for authenticated user."""
        self.client.force_login(self.user)

        response = self.client.get(self.settings_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/account_settings.html")
