"""
Tests for seller views.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now

from products.models import Product, ProductCategory, ProductCondition
from users.models import User

from .models import Seller, SellerSubscription
from .testing import make_seller

PRODUCT_CREATE = reverse("product_create")


def _make_user(email="ana.petrovic@example.com"):
    user = User.objects.create_user(email=email, username=email, password="pw-123456")
    user.mark_email_verified()
    return user


class TestShopSetupForExistingShop(TestCase):
    """Shop setup edits an open shop instead of opening a second one."""

    def setUp(self):
        self.seller = make_seller("google@example.com", shop_name="Stara radnja")
        self.user = self.seller.user
        self.client.force_login(self.user)
        self.url = reverse("seller_shop_setup")

    def test_post_updates_the_existing_shop(self):
        response = self.client.post(
            self.url,
            {
                "shop_name": "Updated Shop",
                "shop_slug": "updated-shop",
                "shop_description": "Updated description",
                "location": "Novi Sad",
            },
        )
        self.assertEqual(response.status_code, 302)
        seller = Seller.objects.get(user=self.user)
        self.assertEqual(seller.shop_name, "Updated Shop")
        self.assertEqual(seller.shop_slug, "updated-shop")
        self.assertEqual(Seller.objects.filter(user=self.user).count(), 1)
        self.assertEqual(seller.subscriptions.count(), 1)

    def test_keeping_the_same_slug_is_allowed(self):
        """The form used to reject the shop's own slug as taken."""
        response = self.client.post(
            self.url, {"shop_name": "Nova", "shop_slug": self.seller.shop_slug}
        )
        self.assertEqual(response.status_code, 302)
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.shop_name, "Nova")

    def test_empty_slug_keeps_the_current_one(self):
        old_slug = self.seller.shop_slug
        self.client.post(self.url, {"shop_name": "Sasvim drugo ime"})
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.shop_slug, old_slug)

    def test_get_prefills_existing_data(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stara radnja")


class TestFirstListingOpensTheShop(TestCase):
    """A signed-in user without a shop clicks "Dodaj oglas" (#89)."""

    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.setup_url = f"{reverse('seller_shop_setup')}?next=%2Fproducts%2Fcreate%2F"

    def test_add_listing_goes_to_shop_setup_first(self):
        response = self.client.get(PRODUCT_CREATE)
        self.assertRedirects(response, self.setup_url)
        self.assertFalse(Seller.objects.exists())

    def test_setup_opens_the_shop_and_continues_to_the_listing(self):
        page = self.client.get(self.setup_url)
        self.assertContains(page, 'name="next" value="/products/create/"')
        self.assertContains(page, "Otvori prodavnicu i nastavi")

        response = self.client.post(
            self.setup_url,
            {
                "shop_name": "Đorđeva Radnja",
                "shop_description": "Stari radio aparati",
                "location": "Niš",
                "next": PRODUCT_CREATE,
            },
        )
        self.assertRedirects(response, PRODUCT_CREATE)
        seller = Seller.objects.get(user=self.user)
        self.assertEqual(seller.shop_name, "Đorđeva Radnja")
        self.assertEqual(seller.shop_slug, "djordjeva-radnja")
        self.assertEqual(seller.location, "Niš")
        self.assertEqual(seller.tier, "garazna")
        [subscription] = seller.subscriptions.all()
        self.assertEqual(subscription.amount, 0)

    def test_first_listing_works_after_setup(self):
        self.client.post(
            self.setup_url, {"shop_name": "Moja radnja", "next": PRODUCT_CREATE}
        )
        self.assertEqual(self.client.get(PRODUCT_CREATE).status_code, 200)
        parent = ProductCategory.objects.create(name="Kuća", slug="kuca")
        category = ProductCategory.objects.create(
            name="Nameštaj", slug="namestaj", parent=parent
        )
        condition = ProductCondition.objects.create(name="Dobro")
        response = self.client.post(
            PRODUCT_CREATE,
            {
                "title": "Stara drvena stolica",
                "description": "Masivno drvo, bez oštećenja.",
                "price": "1500",
                "stock": "1",
                "category": category.id,
                "condition": condition.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(title="Stara drvena stolica")
        self.assertEqual(product.seller.user, self.user)

    def test_slug_never_comes_from_the_email(self):
        self.client.post(self.setup_url, {"shop_name": "Radnja"})
        self.assertNotIn("ana", Seller.objects.get(user=self.user).shop_slug)

    def test_without_next_setup_continues_to_bank_details(self):
        response = self.client.post(
            reverse("seller_shop_setup"), {"shop_name": "Radnja"}
        )
        self.assertRedirects(response, reverse("seller_bank_details"))

    def test_external_next_is_ignored(self):
        response = self.client.post(
            reverse("seller_shop_setup"),
            {"shop_name": "Radnja", "next": "https://evil.example.com/"},
        )
        self.assertRedirects(response, reverse("seller_bank_details"))

    def test_taken_slug_gets_a_suffix(self):
        make_seller("other@example.com", shop_name="Radnja")
        self.client.post(self.setup_url, {"shop_name": "Radnja"})
        self.assertEqual(Seller.objects.get(user=self.user).shop_slug, "radnja-2")

    def test_typed_slug_that_is_taken_is_an_error(self):
        make_seller("other@example.com", shop_name="Radnja")
        response = self.client.post(
            self.setup_url, {"shop_name": "Moja", "shop_slug": "radnja"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ova adresa prodavnice je zauzeta.")
        self.assertFalse(Seller.objects.filter(user=self.user).exists())

    def test_reserved_slug_is_refused(self):
        response = self.client.post(
            self.setup_url, {"shop_name": "Moja", "shop_slug": "dashboard"}
        )
        self.assertContains(response, "Ova adresa prodavnice je zauzeta.")
        self.client.post(self.setup_url, {"shop_name": "Dashboard"})
        self.assertEqual(Seller.objects.get(user=self.user).shop_slug, "dashboard-2")


class TestPagesNeedAShop(TestCase):
    """Seller pages send a user without a shop to setup and never make one."""

    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)

    def test_seller_pages_redirect_to_shop_setup(self):
        for name in (
            "seller_dashboard",
            "seller_settings",
            "seller_products_list",
            "seller_bank_details",
        ):
            with self.subTest(name):
                response = self.client.get(reverse(name))
                self.assertRedirects(response, reverse("seller_shop_setup"))
        self.assertFalse(Seller.objects.exists())
        self.assertFalse(SellerSubscription.objects.exists())

    def test_signup_and_login_make_no_shop(self):
        self.client.get(reverse("account-settings"))
        self.client.get(reverse("home"))
        self.assertFalse(Seller.objects.exists())


class TestNavigation(TestCase):
    def test_signed_in_user_without_shop_sees_add_listing(self):
        self.client.force_login(_make_user())
        body = self.client.get(reverse("home")).content.decode()
        self.assertIn("Dodaj oglas", body)
        self.assertNotIn(reverse("seller_dashboard"), body)

    def test_shop_owner_sees_the_seller_menu(self):
        self.client.force_login(make_seller("s@example.com").user)
        body = self.client.get(reverse("home")).content.decode()
        self.assertIn(reverse("seller_dashboard"), body)
        self.assertIn(reverse("seller_products_list"), body)

    def test_account_settings_offer_a_shop(self):
        self.client.force_login(_make_user())
        response = self.client.get(reverse("account-settings"))
        self.assertContains(response, "Otvori prodavnicu")
        self.assertContains(response, reverse("seller_shop_setup"))
        self.assertNotContains(response, "Tip naloga")

    def test_account_settings_link_the_dashboard_for_shop_owners(self):
        self.client.force_login(make_seller("s@example.com", "Moja radnja").user)
        response = self.client.get(reverse("account-settings"))
        self.assertContains(response, "Moja radnja")
        self.assertContains(response, reverse("seller_dashboard"))
        self.assertNotContains(response, "Otvori prodavnicu")


class TestTraderConfirmation(TestCase):
    """Sellers confirm trader status in settings; buyers see a badge."""

    def setUp(self):
        self.seller = make_seller("trader@example.com", shop_name="Trader")
        self.user = self.seller.user
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
