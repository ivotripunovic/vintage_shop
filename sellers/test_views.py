"""
Tests for seller views.
"""

import pytest
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.timezone import now

from users.models import User

from .models import Seller, SellerSubscription


def _make_social_seller(email="google@example.com"):
    """Create a user as if they registered via Google and chose to become a seller."""
    user = User.objects.create_user(
        email=email,
        username=email.split("@")[0],
        password=None,  # social users have no password
        is_buyer=True,
        email_verified=True,
    )
    # Simulate what social_become_seller_view does
    user.is_seller = True
    user.save(update_fields=["is_seller"])
    from datetime import timedelta

    from django.utils.timezone import now

    seller = Seller.objects.create(
        user=user,
        shop_name=user.username,
        shop_slug=user.username,
    )
    SellerSubscription.objects.create(
        seller=seller,
        plan_type="monthly",
        start_date=now().date(),
        renewal_date=now().date() + timedelta(days=30),
        status="active",
        amount=9.99,
    )
    return user


@pytest.mark.django_db
class TestShopSetupViewForSocialSeller(TestCase):
    """
    Regression tests for shop setup when the Seller row already exists
    (social registration path: Google signup → become seller → shop setup).
    """

    def setUp(self):
        self.client = Client()
        self.user = _make_social_seller()
        self.client.force_login(self.user)
        self.url = reverse("seller_shop_setup")

    def test_shop_setup_post_does_not_raise_integrity_error(self):
        """Submitting shop setup when Seller already exists must not crash."""
        response = self.client.post(
            self.url,
            {
                "shop_name": "My Vintage Shop",
                "shop_slug": "my-vintage-shop",
                "shop_description": "Great vintage items",
                "location": "Belgrade",
            },
        )
        # Should redirect to next step, not 500
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(response.status_code, 302)

    def test_shop_setup_post_updates_existing_seller(self):
        """Shop setup should update the existing Seller row, not create a new one."""
        self.client.post(
            self.url,
            {
                "shop_name": "Updated Shop",
                "shop_slug": "updated-shop",
                "shop_description": "Updated description",
                "location": "Novi Sad",
            },
        )
        seller = Seller.objects.get(user=self.user)
        self.assertEqual(seller.shop_name, "Updated Shop")
        self.assertEqual(Seller.objects.filter(user=self.user).count(), 1)

    def test_shop_setup_get_prefills_existing_data(self):
        """GET request should pre-fill the form with the existing seller data."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.username)  # shop_name prefilled


class TestTraderConfirmation(TestCase):
    """Sellers confirm trader status in settings; buyers see a badge."""

    def setUp(self):
        self.user = _make_social_seller("trader@example.com")
        self.seller = self.user.seller_profile
        self.client.force_login(self.user)

    def test_settings_post_confirms_trader(self):
        response = self.client.post(
            reverse("seller_settings"),
            {
                "shop_name": self.seller.shop_name,
                "email": self.user.email,
                "is_trader": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.seller.refresh_from_db()
        self.assertIsNotNone(self.seller.trader_confirmed_at)

    def test_shop_detail_shows_badge_only_when_confirmed(self):
        url = reverse("shop_detail", args=[self.seller.shop_slug])
        self.assertNotContains(self.client.get(url), "Trgovac")
        self.seller.trader_confirmed_at = now()
        self.seller.save()
        self.assertContains(self.client.get(url), "Trgovac")
