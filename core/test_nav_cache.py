from django.core.cache import cache
from django.test import TestCase, override_settings

from products.models import ProductCategory


@override_settings(COMING_SOON=False)
class NavCategoryCacheTests(TestCase):
    """The category nav in base.html is fragment-cached; changes must show at once."""

    def setUp(self):
        cache.clear()
        self.category = ProductCategory.objects.create(name="Jakne", slug="jakne")

    def test_renamed_category_appears_immediately(self):
        self.assertContains(self.client.get("/"), "Jakne")
        self.category.name = "Kaputi"
        self.category.save()
        response = self.client.get("/")
        self.assertContains(response, "Kaputi")
        self.assertNotContains(response, "Jakne")

    def test_new_subcategory_appears_immediately(self):
        self.client.get("/")
        ProductCategory.objects.create(name="Kožne", slug="kozne", parent=self.category)
        self.assertContains(self.client.get("/"), "Kožne")

    def test_deleted_category_disappears_immediately(self):
        self.client.get("/")
        self.category.delete()
        self.assertNotContains(self.client.get("/"), "Jakne")

    def test_cached_nav_skips_category_queries(self):
        self.client.get("/")
        # Only the featured-products query; no category queries for the nav
        with self.assertNumQueries(1):
            self.client.get("/")
