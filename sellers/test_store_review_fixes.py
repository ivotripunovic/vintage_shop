"""
Regression tests for the code review of the store-tier change (#89):
only paid tiers have a store; free sellers list under their own name.
"""

import shutil
import tempfile

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from orders.models import Sale
from products.models import Product, ProductCategory, ProductCondition
from products.test_photo_uploads import photo
from users.models import User

from .models import ANONYMOUS_SELLER_NAME, Seller, free_shop_slug
from .testing import make_seller

PRODUCT_CREATE = reverse("product_create")
MEDIA_ROOT = tempfile.mkdtemp()


def _user(email="ana@example.com", **fields):
    return User.objects.create_user(
        email=email, username=email, password="pw-123456", **fields
    )


class TestFreeSellerProfile(TestCase):
    """Free sellers have no shop image or description, so they keep the
    buyer profile form (picture, bio, name)."""

    def test_free_seller_can_edit_the_profile(self):
        seller = make_seller("free@example.com")
        self.client.force_login(seller.user)
        url = reverse("account-settings")
        self.assertContains(self.client.get(url), 'name="bio"')
        self.client.post(
            url, {"bio": "Prodajem stare ploče", "first_name": "Ana", "last_name": "P"}
        )
        seller.user.refresh_from_db()
        self.assertEqual(seller.user.bio, "Prodajem stare ploče")

    def test_store_owner_edits_the_store_instead(self):
        seller = make_seller("paid@example.com", tier="odrzivo")
        self.client.force_login(seller.user)
        body = self.client.get(reverse("account-settings")).content.decode()
        self.assertNotIn('name="bio"', body)
        self.assertIn(reverse("seller_settings"), body)

    def test_name_can_be_set_and_is_shown_to_buyers(self):
        seller = make_seller("free@example.com")
        self.assertEqual(seller.display_name, ANONYMOUS_SELLER_NAME)
        self.client.force_login(seller.user)
        self.client.post(
            reverse("account-settings"),
            {"first_name": "Ana", "last_name": "Petrović", "bio": ""},
        )
        seller = Seller.objects.select_related("user").get(pk=seller.pk)
        self.assertEqual(seller.display_name, "Ana Petrović")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class TestNoSellerUntilTheUserActs(TestCase):
    """Looking at the listing form does not make anyone a seller."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = _user(first_name="Ana", last_name="Petrović")
        self.client.force_login(self.user)

    def test_opening_the_form_makes_no_seller(self):
        response = self.client.get(PRODUCT_CREATE)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana Petrović")
        self.assertFalse(Seller.objects.exists())
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_seller)

    def test_saving_a_listing_opens_the_seller(self):
        parent = ProductCategory.objects.create(name="Kuća", slug="kuca")
        category = ProductCategory.objects.create(
            name="Nameštaj", slug="namestaj", parent=parent
        )
        condition = ProductCondition.objects.create(name="Dobro")
        self.client.post(
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
        seller = Seller.objects.get(user=self.user)
        self.assertEqual(seller.products.get().title, "Stara drvena stolica")

    def test_first_photo_upload_opens_the_seller(self):
        response = self.client.post(reverse("photo_upload"), {"photo": photo()})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(Seller.objects.filter(user=self.user).exists())


class TestStoreSetupAfterUpgrade(TestCase):
    def setUp(self):
        self.user = _user()
        self.client.force_login(self.user)
        self.seller = Seller.open_for(self.user)  # hidden, "Prodavnica"
        self.seller.change_tier("odrzivo")

    def test_empty_url_is_made_from_the_new_name(self):
        self.client.post(reverse("seller_shop_setup"), {"shop_name": "Stari Satovi"})
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.shop_name, "Stari Satovi")
        self.assertEqual(self.seller.shop_slug, "stari-satovi")

    def test_the_default_name_is_refused(self):
        """Saving "Prodavnica" would leave the setup banner up forever."""
        response = self.client.post(
            reverse("seller_shop_setup"), {"shop_name": "Prodavnica"}
        )
        self.assertContains(response, "Izaberite naziv prodavnice.")


class TestFreeShopSlug(TestCase):
    def test_one_query_however_many_are_taken(self):
        for i in range(1, 6):
            make_seller(f"s{i}@example.com", shop_name="Prodavnica")
        # prodavnica, prodavnica-2 ... prodavnica-5
        with self.assertNumQueries(1):
            self.assertEqual(free_shop_slug("prodavnica"), "prodavnica-6")

    def test_reserved_paths_and_similar_slugs(self):
        make_seller("a@example.com", shop_slug="radnja-stara")
        self.assertEqual(free_shop_slug("radnja"), "radnja")
        self.assertEqual(free_shop_slug("dashboard"), "dashboard-2")

    def test_own_slug_is_not_taken(self):
        seller = make_seller("a@example.com", shop_name="Radnja")
        self.assertEqual(free_shop_slug("radnja", exclude_pk=seller.pk), "radnja")


class TestRateSaleQueries(TestCase):
    def test_seller_user_comes_with_the_sale(self):
        seller = make_seller("seller@example.com")
        buyer = _user("buyer@example.com")
        product = Product.objects.create(
            seller=seller, title="Lampa", price=100, status="sold", stock=0
        )
        sale = Sale.objects.create(
            product=product,
            product_title="Lampa",
            seller=seller,
            buyer=buyer,
        )
        self.client.force_login(buyer)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("rate_sale", args=[sale.id]))
        self.assertEqual(response.status_code, 200)
        user_lookups = [
            q["sql"]
            for q in queries
            if q["sql"].split(" FROM ")[1].startswith('"users_user"')
        ]
        # Only the session's user; the seller's user is joined to the sale
        self.assertEqual(len(user_lookups), 1, user_lookups)


class TestNamelessSellerHint(TestCase):
    def test_listing_form_asks_for_a_name_only_when_missing(self):
        self.client.force_login(_user("noname@example.com"))
        hint = "Dodajte ime"
        self.assertContains(self.client.get(PRODUCT_CREATE), hint)
        self.client.force_login(_user("ana@example.com", first_name="Ana"))
        self.assertNotContains(self.client.get(PRODUCT_CREATE), hint)
