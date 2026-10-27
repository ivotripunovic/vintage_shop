"""
Tests for seller admin.
"""

from django.contrib import admin
from django.test import RequestFactory, TestCase

from users.models import User

from .admin import SellerAdmin
from .models import Seller


class TestSellerAdminTraderFields(TestCase):
    """Staff can see and clear trader confirmations but not set them."""

    def setUp(self):
        user = User.objects.create_user(
            email="trader@example.com",
            username="trader@example.com",
            password="testpass123",
            is_seller=True,
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=user,
            defaults={"shop_name": "Trader Shop", "shop_slug": "trader-shop"},
        )
        self.seller.confirm_trader()
        self.seller.save()
        self.model_admin = SellerAdmin(Seller, admin.site)
        self.request = RequestFactory().get("/")

    def test_trader_fields_are_readonly(self):
        readonly = self.model_admin.get_readonly_fields(self.request)
        self.assertIn("trader_confirmed_at", readonly)
        self.assertIn("trader_statement", readonly)

    def test_clear_action_removes_confirmation(self):
        self.model_admin.clear_trader_confirmation(
            self.request, Seller.objects.filter(pk=self.seller.pk)
        )
        self.seller.refresh_from_db()
        self.assertIsNone(self.seller.trader_confirmed_at)
        self.assertEqual(self.seller.trader_statement, "")

    def test_is_trader_column_sorts_by_confirmation_time(self):
        self.assertEqual(Seller.is_trader.fget.admin_order_field, "trader_confirmed_at")
