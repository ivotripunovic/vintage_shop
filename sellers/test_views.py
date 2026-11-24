"""
Tests for seller views.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now

from products.models import Product, ProductCategory, ProductCondition
from users.models import User

from .models import (
    ANONYMOUS_SELLER_NAME,
    DEFAULT_SHOP_NAME,
    Seller,
    SellerSubscription,
)
from .testing import make_seller

PRODUCT_CREATE = reverse("product_create")


def _make_user(email="ana.petrovic@example.com"):
    user = User.objects.create_user(email=email, username=email, password="pw-123456")
    user.mark_email_verified()
    return user


class TestShopSetupForExistingShop(TestCase):
    """Shop setup edits the store of a paid-tier seller."""

    def setUp(self):
        self.seller = make_seller(
            "google@example.com", shop_name="Stara radnja", tier="odrzivo"
        )
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

    def test_typed_slug_that_is_taken_is_an_error(self):
        make_seller("other@example.com", shop_name="Radnja")
        response = self.client.post(
            self.url, {"shop_name": "Moja", "shop_slug": "radnja"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ova adresa prodavnice je zauzeta.")

    def test_reserved_slug_is_refused(self):
        response = self.client.post(
            self.url, {"shop_name": "Moja", "shop_slug": "dashboard"}
        )
        self.assertContains(response, "Ova adresa prodavnice je zauzeta.")

    def test_next_is_followed_but_external_next_is_ignored(self):
        response = self.client.post(
            self.url, {"shop_name": "Radnja", "next": PRODUCT_CREATE}
        )
        self.assertRedirects(response, PRODUCT_CREATE)
        response = self.client.post(
            self.url, {"shop_name": "Radnja", "next": "https://evil.example.com/"}
        )
        self.assertRedirects(response, reverse("seller_bank_details"))


class TestFirstListing(TestCase):
    """A free user's first "Dodaj oglas" needs no shop setup (#89)."""

    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)

    def test_add_listing_opens_the_form_and_a_hidden_seller(self):
        response = self.client.get(PRODUCT_CREATE)
        self.assertEqual(response.status_code, 200)
        seller = Seller.objects.get(user=self.user)
        self.assertFalse(seller.has_store)
        self.assertEqual(seller.tier, "garazna")
        self.assertEqual(seller.shop_slug, "prodavnica")
        [subscription] = seller.subscriptions.all()
        self.assertEqual(subscription.amount, 0)

    def test_opening_the_form_twice_makes_one_seller(self):
        self.client.get(PRODUCT_CREATE)
        self.client.get(PRODUCT_CREATE)
        self.assertEqual(Seller.objects.filter(user=self.user).count(), 1)
        self.assertEqual(SellerSubscription.objects.count(), 1)

    def test_first_listing_is_saved(self):
        self.client.get(PRODUCT_CREATE)
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
        self.client.get(PRODUCT_CREATE)
        self.assertNotIn("ana", Seller.objects.get(user=self.user).shop_slug)

    def test_free_seller_is_sent_away_from_shop_setup(self):
        self.client.get(PRODUCT_CREATE)
        response = self.client.get(reverse("seller_shop_setup"))
        self.assertRedirects(response, reverse("seller_dashboard"))
        response = self.client.post(
            reverse("seller_shop_setup"), {"shop_name": "Radnja"}
        )
        self.assertRedirects(response, reverse("seller_dashboard"))
        self.assertEqual(
            Seller.objects.get(user=self.user).shop_name, DEFAULT_SHOP_NAME
        )


class TestStoresComeWithPaidTiers(TestCase):
    """Only Održivo and Premijum sellers have a store page (#89)."""

    def _product(self, seller, title="Lampa"):
        return Product.objects.create(
            seller=seller, title=title, price=100, status="published"
        )

    def test_free_seller_has_no_shop_page_and_is_not_listed(self):
        seller = make_seller("free@example.com", shop_name="Radnja")
        self._product(seller)
        url = reverse("shop_detail", args=[seller.shop_slug])
        self.assertEqual(self.client.get(url).status_code, 404)
        shops = self.client.get(reverse("shops_browse"))
        self.assertNotIn(seller, list(shops.context["sellers"]))

    def test_paid_seller_has_a_shop_page_and_is_listed(self):
        for tier in ("odrzivo", "premijum"):
            with self.subTest(tier):
                seller = make_seller(f"{tier}@example.com", shop_name=tier, tier=tier)
                self._product(seller)
                url = reverse("shop_detail", args=[seller.shop_slug])
                self.assertContains(self.client.get(url), seller.shop_name)
                shops = self.client.get(reverse("shops_browse"))
                self.assertIn(seller, list(shops.context["sellers"]))

    def test_free_listing_shows_the_full_name_and_no_shop_link(self):
        seller = make_seller(
            "free@example.com",
            shop_name="Skrivena radnja",
            user_fields={"first_name": "Ana", "last_name": "Petrović"},
        )
        product = self._product(seller)
        response = self.client.get(reverse("product_detail", args=[product.id]))
        self.assertContains(response, "Ana Petrović")
        self.assertNotContains(response, "Skrivena radnja")
        self.assertNotContains(
            response, reverse("shop_detail", args=[seller.shop_slug])
        )

    def test_paid_listing_shows_the_shop(self):
        seller = make_seller(
            "paid@example.com",
            shop_name="Prava radnja",
            tier="odrzivo",
            user_fields={"first_name": "Ana", "last_name": "Petrović"},
        )
        product = self._product(seller)
        response = self.client.get(reverse("product_detail", args=[product.id]))
        self.assertContains(response, "Prava radnja")
        self.assertContains(response, reverse("shop_detail", args=[seller.shop_slug]))

    def test_seller_without_a_name_shows_a_generic_label(self):
        seller = make_seller("noname@example.com")
        self.assertEqual(seller.display_name, ANONYMOUS_SELLER_NAME)

    def test_moving_up_a_tier_asks_for_the_store_name(self):
        self.client.force_login(_make_user())
        self.client.get(PRODUCT_CREATE)
        seller = Seller.objects.get()
        dashboard = reverse("seller_dashboard")
        self.assertNotContains(self.client.get(dashboard), "Podesi prodavnicu")

        seller.change_tier("odrzivo")
        self.assertContains(self.client.get(dashboard), "Podesi prodavnicu")
        self.client.post(reverse("seller_shop_setup"), {"shop_name": "Moja radnja"})
        seller.refresh_from_db()
        self.assertFalse(seller.needs_store_setup)
        self.assertNotContains(self.client.get(dashboard), "Podesi prodavnicu")

    def test_settings_have_no_store_fields_for_a_free_seller(self):
        free = make_seller("free@example.com")
        self.client.force_login(free.user)
        body = self.client.get(reverse("seller_settings")).content.decode()
        self.assertNotIn('name="shop_name"', body)
        self.assertNotIn('name="shop_image"', body)

        paid = make_seller("paid@example.com", tier="odrzivo")
        self.client.force_login(paid.user)
        body = self.client.get(reverse("seller_settings")).content.decode()
        self.assertIn('name="shop_name"', body)


class TestPagesNeedASeller(TestCase):
    """Seller pages send a user who never listed to the listing form."""

    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)

    def test_seller_pages_redirect_to_the_listing_form(self):
        for name in (
            "seller_dashboard",
            "seller_settings",
            "seller_products_list",
            "seller_bank_details",
            "seller_shop_setup",
        ):
            with self.subTest(name):
                response = self.client.get(reverse(name))
                # Not followed: the listing form opens the seller
                self.assertRedirects(
                    response, PRODUCT_CREATE, fetch_redirect_response=False
                )
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

    def test_account_settings_offer_a_listing(self):
        self.client.force_login(_make_user())
        response = self.client.get(reverse("account-settings"))
        self.assertContains(response, "Dodaj oglas")
        self.assertNotContains(response, reverse("seller_shop_setup"))
        self.assertNotContains(response, "Tip naloga")

    def test_account_settings_for_a_free_seller(self):
        self.client.force_login(make_seller("s@example.com", "Moja radnja").user)
        response = self.client.get(reverse("account-settings"))
        self.assertContains(response, reverse("seller_dashboard"))
        self.assertContains(response, "pakete Održivo i Premijum")
        self.assertNotContains(response, "Moja radnja")

    def test_account_settings_name_the_store_of_a_paid_seller(self):
        seller = make_seller("s@example.com", "Moja radnja", tier="premijum")
        self.client.force_login(seller.user)
        response = self.client.get(reverse("account-settings"))
        self.assertContains(response, "Moja radnja")
        self.assertContains(response, reverse("seller_dashboard"))


class TestTraderConfirmation(TestCase):
    """Sellers confirm trader status in settings; buyers see a badge."""

    def setUp(self):
        self.seller = make_seller(
            "trader@example.com", shop_name="Trader", tier="odrzivo"
        )
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
