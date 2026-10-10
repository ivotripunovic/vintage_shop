"""
Listing pages must run a fixed number of queries, however many products are
shown (no per-product lookups for images, category, condition or seller).
"""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from products.models import Product, ProductCategory, ProductCondition, ProductImage
from sellers.models import Seller
from users.models import User


class ListingQueryCountTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="seller@test.com",
            username="seller@test.com",
            password="testpass123",
            is_seller=True,
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=user, defaults={"shop_name": "Shop", "shop_slug": "shop"}
        )
        self.parent = ProductCategory.objects.create(name="Odeća", slug="odeca")
        self.child = ProductCategory.objects.create(
            name="Jakne", slug="jakne", parent=self.parent
        )
        ProductCategory.objects.create(name="Kožne", slug="kozne", parent=self.child)
        self.condition = ProductCondition.objects.create(name="Dobro")
        self.add_products(1)

    def add_products(self, count):
        for i in range(count):
            product = Product.objects.create(
                seller=self.seller,
                title=f"Proizvod {Product.objects.count()}",
                description="Opis",
                price=1000,
                category=self.child,
                condition=self.condition,
                stock=1,
                status="published",
            )
            ProductImage.objects.create(
                product=product, image=f"products/p{product.pk}.jpg", order=0
            )

    def count_queries(self, url):
        self.client.get(url)  # warm the nav fragment cache
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(queries), response

    def assert_constant_queries(self, url):
        with_one, _ = self.count_queries(url)
        self.add_products(9)
        with_ten, response = self.count_queries(url)
        self.assertEqual(with_one, with_ten)
        self.assertContains(response, "products/p")  # images still rendered
        self.assertContains(response, self.seller.shop_name)  # seller rendered

    def test_browse_page(self):
        self.assert_constant_queries(reverse("products_browse"))

    def test_category_page(self):
        self.assert_constant_queries(
            reverse("category_products", args=[self.parent.id])
        )

    def test_category_page_includes_all_descendants(self):
        grandchild = ProductCategory.objects.get(slug="kozne")
        self.assertEqual(
            set(self.parent.get_all_ids()),
            {self.parent.id, self.child.id, grandchild.id},
        )
