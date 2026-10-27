"""
Tests for product view counting, wishlist counts and recent viewers.
"""

from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from favourites.models import WishlistItem
from products.models import Product, ProductView
from products.popularity import (
    RECENT_VIEWER_WINDOW,
    recent_viewer_count,
    touch_recent_viewer,
)
from sellers.models import Seller
from users.models import User


class ProductPopularityTests(TestCase):
    """Unique views, wishlist count and recent viewers on product pages."""

    def setUp(self):
        cache.clear()
        self.seller_user = User.objects.create_user(
            email="seller@test.com",
            username="seller@test.com",
            password="testpass123",
            is_seller=True,
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=self.seller_user,
            defaults={"shop_name": "Test Shop", "shop_slug": "test-shop"},
        )
        self.product = Product.objects.create(
            seller=self.seller,
            title="Old Lamp",
            description="A lamp",
            price=10,
            status="published",
        )
        self.url = reverse("product_detail", args=[self.product.id])

    def _buyer(self, n):
        user = User.objects.create_user(
            email=f"buyer{n}@test.com",
            username=f"buyer{n}@test.com",
            password="testpass123",
        )
        client = Client()
        client.force_login(user)
        return user, client

    def _view_count(self):
        self.product.refresh_from_db()
        return self.product.view_count

    def test_logged_in_user_counts_once(self):
        _, client = self._buyer(1)
        client.get(self.url)
        client.get(self.url)
        self.assertEqual(self._view_count(), 1)

    def test_different_users_count_separately(self):
        self._buyer(1)[1].get(self.url)
        self._buyer(2)[1].get(self.url)
        self.assertEqual(self._view_count(), 2)

    def test_anonymous_session_counts_once(self):
        client = Client()
        client.get(self.url)
        client.get(self.url)
        self.assertEqual(self._view_count(), 1)
        Client().get(self.url)
        self.assertEqual(self._view_count(), 2)
        self.assertEqual(ProductView.objects.filter(user=None).count(), 2)

    def test_owner_view_not_counted(self):
        client = Client()
        client.force_login(self.seller_user)
        client.get(self.url)
        self.assertEqual(self._view_count(), 0)
        self.assertEqual(recent_viewer_count(self.product.pk), 0)

    def test_bot_view_not_counted(self):
        Client(HTTP_USER_AGENT="Mozilla/5.0 (compatible; Googlebot/2.1)").get(self.url)
        self.assertEqual(self._view_count(), 0)

    def test_page_shows_view_and_wishlist_counts(self):
        buyer, client = self._buyer(1)
        WishlistItem.objects.create(user=buyer, product=self.product)
        WishlistItem.objects.create(user=self._buyer(2)[0], product=self.product)
        response = client.get(self.url)
        self.assertEqual(response.context["product"].view_count, 1)
        self.assertEqual(response.context["wishlist_count"], 2)
        self.assertContains(response, "Pregledi")

    def test_recent_viewers_excludes_current_visitor(self):
        _, first = self._buyer(1)
        response = first.get(self.url)
        self.assertEqual(response.context["recent_viewers"], 0)
        self.assertNotContains(response, "Gledalo nedavno")

        _, second = self._buyer(2)
        response = second.get(self.url)
        self.assertEqual(response.context["recent_viewers"], 1)
        self.assertContains(response, "Gledalo nedavno")

    def test_recent_viewers_expire_after_window(self):
        with mock.patch("products.popularity.time.time", return_value=1000.0):
            touch_recent_viewer(self.product.pk, "u1")
        later = 1000.0 + RECENT_VIEWER_WINDOW + 1
        with mock.patch("products.popularity.time.time", return_value=later):
            self.assertEqual(recent_viewer_count(self.product.pk), 0)
            touch_recent_viewer(self.product.pk, "u2")
            key = f"product_recent_viewers:{self.product.pk}"
            self.assertEqual(list(cache.get(key)), ["u2"])

    def test_seller_list_shows_counts(self):
        self._buyer(1)[1].get(self.url)
        WishlistItem.objects.create(user=self._buyer(2)[0], product=self.product)
        client = Client()
        client.force_login(self.seller_user)
        response = client.get(reverse("seller_products_list"))
        listed = response.context["products"][0]
        self.assertEqual(listed.view_count, 1)
        self.assertEqual(listed.wishlist_count, 1)
        self.assertContains(response, "1 pregleda")
