"""
Search filter that shows only products from Premijum sellers (issue #5).
"""

from django.test import TestCase
from django.urls import reverse

from products.models import Product, ProductCategory, ProductCondition
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


class PremijumFilterTests(TestCase):
    def setUp(self):
        self.category = ProductCategory.objects.create(name="Odeća", slug="odeca")
        self.other_category = ProductCategory.objects.create(name="Knjige", slug="knj")
        self.good = ProductCondition.objects.create(name="Dobro")
        self.worn = ProductCondition.objects.create(name="Nošeno")
        premijum = _make_seller("premijum@test.com", "premijum")
        garazna = _make_seller("garazna@test.com", "garazna")
        self.premijum_jacket = self._make_product(premijum, "Premijum jakna")
        self.premijum_book = self._make_product(
            premijum, "Premijum knjiga", category=self.other_category
        )
        self.premijum_worn = self._make_product(
            premijum, "Premijum jakna nošena", condition=self.worn
        )
        self.garazna_jacket = self._make_product(garazna, "Garažna jakna")

    def _make_product(self, seller, title, category=None, condition=None):
        return Product.objects.create(
            seller=seller,
            title=title,
            description="Opis",
            price=1000,
            category=category or self.category,
            condition=condition or self.good,
            stock=1,
            status="published",
        )

    def _titles(self, url, params):
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        return {product.title for product in response.context["products"]}

    def test_browse_without_filter_shows_all_sellers(self):
        titles = self._titles(reverse("products_browse"), {})
        self.assertIn("Garažna jakna", titles)

    def test_browse_filter_shows_only_premijum_sellers(self):
        titles = self._titles(reverse("products_browse"), {"premijum": "1"})
        self.assertEqual(
            titles,
            {"Premijum jakna", "Premijum knjiga", "Premijum jakna nošena"},
        )

    def test_browse_filter_combines_with_search_category_and_condition(self):
        titles = self._titles(
            reverse("products_browse"),
            {
                "premijum": "1",
                "q": "jakna",
                "category": self.category.id,
                "condition": self.good.id,
            },
        )
        self.assertEqual(titles, {"Premijum jakna"})

    def test_category_filter_shows_only_premijum_sellers(self):
        titles = self._titles(
            reverse("category_products", args=[self.category.id]),
            {"premijum": "1"},
        )
        self.assertEqual(titles, {"Premijum jakna", "Premijum jakna nošena"})

    def test_chip_clears_only_the_premijum_filter(self):
        response = self.client.get(
            reverse("products_browse"),
            {"premijum": "1", "q": "jakna", "condition": self.good.id, "page": 1},
        )
        self.assertContains(response, "Samo Premijum prodavci")
        self.assertContains(response, f'href="?q=jakna&amp;condition={self.good.id}"')
