"""
Tests for seller tiers: monthly listing limits, listing expiry and prices.
"""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from products.forms import ProductForm
from products.models import Product, ProductImage
from users.models import User

from .models import INVOICE_DUE_DAYS, SellerTier


def _make_seller(email="seller@example.com", tier="garazna"):
    user = User.objects.create_user(
        email=email,
        username=email.split("@")[0],
        password="testpass123",
        is_seller=True,
        email_verified=True,
    )
    seller = user.seller_profile
    if tier != "garazna":
        seller.tier = tier
        seller.save()
    return seller


def _make_product(seller, status="draft", title="Lamp"):
    return Product.objects.create(
        seller=seller,
        title=title,
        description="Vintage lamp",
        price=Decimal("1500"),
        status=status,
    )


def _form_data(status):
    return {
        "title": "Lamp",
        "description": "Vintage lamp",
        "price": "1500",
        "stock": "1",
        "status": status,
    }


class TestTierSettings(TestCase):
    def test_new_seller_starts_on_garazna(self):
        seller = _make_seller()
        self.assertEqual(seller.tier, "garazna")
        self.assertEqual(seller.monthly_listing_limit, 10)

    def test_tier_defaults_from_migration(self):
        self.assertEqual(
            SellerTier.objects.get(tier="odrzivo").monthly_listing_limit, 50
        )
        self.assertIsNone(SellerTier.objects.get(tier="premijum").monthly_listing_limit)
        self.assertEqual(
            SellerTier.objects.get(tier="premijum").monthly_price, Decimal("9000")
        )
        self.assertEqual(
            SellerTier.objects.get(tier="odrzivo").monthly_price, Decimal("6500")
        )
        self.assertEqual(SellerTier.objects.get(tier="garazna").listing_expiry_days, 30)

    def test_admin_change_to_limit_applies(self):
        SellerTier.objects.filter(tier="garazna").update(monthly_listing_limit=3)
        seller = _make_seller()
        self.assertEqual(seller.monthly_listing_limit, 3)

    def test_initial_subscription_uses_tier_price(self):
        seller = _make_seller()
        self.assertEqual(seller.active_subscription.amount, Decimal("0"))


class TestChangeTier(TestCase):
    def test_upgrade_restarts_subscription_and_creates_invoice(self):
        seller = _make_seller()
        old_subscription = seller.active_subscription
        invoice = seller.change_tier("premijum")

        seller.refresh_from_db()
        old_subscription.refresh_from_db()
        self.assertEqual(seller.tier, "premijum")
        self.assertEqual(old_subscription.status, "cancelled")
        self.assertEqual(seller.active_subscription.amount, Decimal("9000"))
        self.assertEqual(invoice.status, "pending")
        self.assertEqual(invoice.amount, Decimal("9000"))
        self.assertTrue(invoice.invoice_number)
        self.assertEqual(
            invoice.due_date, invoice.period_start + timedelta(days=INVOICE_DUE_DAYS)
        )

    def test_downgrade_to_free_cancels_pending_invoice(self):
        seller = _make_seller()
        old_invoice = seller.change_tier("odrzivo")
        self.assertIsNone(seller.change_tier("garazna"))

        old_invoice.refresh_from_db()
        self.assertEqual(old_invoice.status, "cancelled")
        self.assertEqual(seller.active_subscription.amount, Decimal("0"))
        self.assertEqual(seller.subscriptions.filter(status="active").count(), 1)

    def test_same_tier_changes_nothing(self):
        seller = _make_seller(tier="odrzivo")
        self.assertIsNone(seller.change_tier("odrzivo"))
        self.assertEqual(seller.subscriptions.count(), 1)
        self.assertFalse(seller.invoices.exists())


class TestListingLimit(TestCase):
    def setUp(self):
        SellerTier.objects.filter(tier="garazna").update(monthly_listing_limit=2)
        self.seller = _make_seller()

    def test_publishing_uses_a_slot(self):
        _make_product(self.seller, status="published")
        self.assertEqual(self.seller.listings_left_this_month(), 1)

    def test_limit_blocks_new_listing(self):
        _make_product(self.seller, status="published")
        _make_product(self.seller, status="published")
        self.assertFalse(self.seller.can_publish(_make_product(self.seller)))

    def test_republishing_does_not_use_a_slot(self):
        product = _make_product(self.seller, status="published")
        product.unpublish()
        product.publish()
        self.assertEqual(self.seller.listings_left_this_month(), 1)

    def test_deleting_does_not_free_a_slot(self):
        _make_product(self.seller, status="published").soft_delete()
        self.assertEqual(self.seller.listings_left_this_month(), 1)

    def test_premijum_is_unlimited(self):
        seller = _make_seller(email="premium@example.com", tier="premijum")
        for i in range(5):
            _make_product(seller, status="published", title=f"Item {i}")
        self.assertIsNone(seller.listings_left_this_month())
        self.assertTrue(seller.can_publish(_make_product(seller)))

    def test_form_rejects_publish_over_limit(self):
        _make_product(self.seller, status="published")
        _make_product(self.seller, status="published")
        form = ProductForm(data=_form_data("published"), seller=self.seller)
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_form_allows_draft_over_limit(self):
        _make_product(self.seller, status="published")
        _make_product(self.seller, status="published")
        form = ProductForm(data=_form_data("draft"), seller=self.seller)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_hides_expired_status(self):
        form = ProductForm(seller=self.seller)
        choices = [value for value, _ in form.fields["status"].choices]
        self.assertNotIn("expired", choices)


class TestListingExpiry(TestCase):
    def test_garazna_listing_expires_after_30_days(self):
        product = _make_product(_make_seller(), status="published")
        self.assertAlmostEqual(
            product.expires_at - product.listed_at, timedelta(days=30)
        )

    def test_paid_listing_never_expires(self):
        seller = _make_seller(email="odrzivo@example.com", tier="odrzivo")
        product = _make_product(seller, status="published")
        self.assertIsNone(product.expires_at)

    def test_command_expires_only_past_listings(self):
        seller = _make_seller()
        old = _make_product(seller, status="published", title="Old")
        Product.objects.filter(pk=old.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        fresh = _make_product(seller, status="published", title="Fresh")

        call_command("expire_listings", stdout=StringIO())

        old.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(old.status, "expired")
        self.assertEqual(fresh.status, "published")

    def test_reentering_expired_listing_uses_a_slot(self):
        SellerTier.objects.filter(tier="garazna").update(monthly_listing_limit=2)
        seller = _make_seller()
        product = _make_product(seller, status="published")
        # Pretend it was listed last month and has now expired
        Product.objects.filter(pk=product.pk).update(
            status="expired",
            listed_at=timezone.now() - timedelta(days=40),
            expires_at=timezone.now() - timedelta(days=10),
        )
        product.refresh_from_db()
        self.assertEqual(seller.listings_left_this_month(), 2)

        product.publish()

        self.assertEqual(seller.listings_left_this_month(), 1)
        self.assertGreater(product.expires_at, timezone.now())


class TestPublishViewLimit(TestCase):
    def setUp(self):
        SellerTier.objects.filter(tier="garazna").update(monthly_listing_limit=1)
        self.seller = _make_seller()
        self.client = Client()
        self.client.force_login(self.seller.user)

    def test_publish_blocked_at_limit(self):
        _make_product(self.seller, status="published", title="First")
        product = _make_product(self.seller, title="Second")
        ProductImage.objects.create(product=product, image="products/test.jpg")

        response = self.client.post(reverse("product_publish", args=[product.id]))

        self.assertRedirects(
            response, reverse("seller_products_list"), fetch_redirect_response=False
        )
        product.refresh_from_db()
        self.assertEqual(product.status, "draft")
