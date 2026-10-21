"""
Home page sections: products picked by admins, and new products from Premijum
sellers (issue #6).
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from config.views import HOME_SECTION_SIZE
from products.models import Product
from sellers.models import Seller
from users.models import User


def _make_seller(email, tier):
    user = User.objects.create_user(
        email=email, username=email, password="testpass123", is_seller=True
    )
    seller = Seller.objects.get(user=user)
    seller.tier = tier
    seller.save()
    return seller


class HomeSectionsTests(TestCase):
    def setUp(self):
        self.premijum = _make_seller("premijum@test.com", "premijum")
        self.odrzivo = _make_seller("odrzivo@test.com", "odrzivo")

    def _make_product(self, seller, title, status="published", is_picked=False):
        return Product.objects.create(
            seller=seller,
            title=title,
            description="Opis",
            price=1000,
            status=status,
            is_picked=is_picked,
        )

    def _section(self, name):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        return [product.title for product in response.context[name]]

    def test_picked_section_shows_picked_products_from_any_tier(self):
        self._make_product(self.odrzivo, "Picked lamp", is_picked=True)
        self._make_product(self.odrzivo, "Plain lamp")
        self.assertEqual(self._section("picked_products"), ["Picked lamp"])

    def test_picked_section_hides_unpublished_products(self):
        self._make_product(self.odrzivo, "Draft", status="draft", is_picked=True)
        self.assertEqual(self._section("picked_products"), [])

    def test_premijum_section_shows_only_premijum_sellers(self):
        self._make_product(self.premijum, "Premijum chair")
        self._make_product(self.odrzivo, "Odrzivo chair")
        self.assertEqual(self._section("premijum_products"), ["Premijum chair"])

    def test_premijum_section_is_newest_first_and_limited(self):
        now = timezone.now()
        for i in range(HOME_SECTION_SIZE + 1):
            product = self._make_product(self.premijum, f"Chair {i}")
            Product.objects.filter(pk=product.pk).update(
                listed_at=now - timedelta(days=i)
            )
        titles = self._section("premijum_products")
        self.assertEqual(titles, [f"Chair {i}" for i in range(HOME_SECTION_SIZE)])

    def test_picked_premijum_product_is_not_shown_twice(self):
        self._make_product(self.premijum, "Picked mirror", is_picked=True)
        self._make_product(self.premijum, "New mirror")
        self.assertEqual(self._section("picked_products"), ["Picked mirror"])
        self.assertEqual(self._section("premijum_products"), ["New mirror"])

    def test_sections_render_with_link_to_premijum_filter(self):
        self._make_product(self.premijum, "Premijum desk", is_picked=True)
        self._make_product(self.premijum, "Premijum bed")
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Izdvojeno")
        self.assertContains(response, "Novo od Premijum prodavaca")
        self.assertContains(response, "?premijum=1")
