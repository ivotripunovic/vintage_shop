"""
View tests for deleting listings (soft delete).
"""

from django.test import TestCase
from django.urls import reverse

from orders.models import Sale
from products.models import Product, ProductImage
from sellers.models import Seller
from users.models import User


class SoftDeleteListingTests(TestCase):
    """Deleting a listing hides it but keeps history and the used slot (#57)."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="del@test.com",
            username="del@test.com",
            password="testpass123",
            is_seller=True,
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user, defaults={"shop_name": "Del", "shop_slug": "del"}
        )
        self.seller.status = "active"
        self.seller.save()
        self.client.force_login(self.user)
        self.product = Product.objects.create(
            seller=self.seller,
            title="Stara vaza",
            description="Porcelan",
            price=1000,
            status="published",
        )
        self.image = ProductImage.objects.create(
            product=self.product, image="products/v.jpg"
        )

    def _delete(self):
        url = reverse("product_delete", args=[self.product.id])
        return self.client.post(url)

    def test_delete_keeps_the_row(self):
        self.assertRedirects(self._delete(), reverse("seller_products_list"))
        product = Product.all_objects.get(id=self.product.id)
        self.assertTrue(product.is_deleted)
        self.assertIsNotNone(product.deleted_at)
        self.assertFalse(Product.objects.filter(id=self.product.id).exists())

    def test_delete_does_not_free_a_listing_slot(self):
        used = self.seller.listings_used_this_month()
        self._delete()
        self.assertEqual(self.seller.listings_used_this_month(), used)

    def test_sale_keeps_its_product(self):
        buyer = User.objects.create_user(
            email="b@test.com", username="b@test.com", password="p"
        )
        sale = Sale.objects.create(
            product=self.product,
            product_title=self.product.title,
            seller=self.seller,
            buyer=buyer,
        )
        self._delete()
        sale = Sale.objects.get(id=sale.id)
        self.assertEqual(sale.product_id, self.product.id)
        self.assertEqual(sale.product.title, "Stara vaza")

    def test_deleted_listing_is_hidden_from_seller(self):
        self._delete()
        listing = self.client.get(reverse("seller_products_list"))
        self.assertEqual(list(listing.context["products"]), [])
        self.assertEqual(listing.context["status_counts"]["all"], 0)
        for name in ["product_edit", "product_images", "product_seller_detail"]:
            url = reverse(name, args=[self.product.id])
            self.assertEqual(self.client.get(url).status_code, 404, name)
        publish = reverse("product_publish", args=[self.product.id])
        self.assertEqual(self.client.post(publish).status_code, 404)
        move = reverse("product_image_move", args=[self.image.id])
        self.assertEqual(self.client.post(move, {"to": "up"}).status_code, 404)

    def test_deleted_listing_is_hidden_from_buyers(self):
        self._delete()
        self.client.logout()
        detail = reverse("product_detail", args=[self.product.id])
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertNotContains(
            self.client.get(reverse("products_browse")), "Stara vaza"
        )
        shop = self.client.get(reverse("shop_detail", args=["del"]))
        self.assertNotContains(shop, "Stara vaza")
        self.assertEqual(shop.context["seller"].published_count, 0)
        shops = self.client.get(reverse("shops_browse"))
        self.assertNotIn(self.seller, list(shops.context["sellers"]))

    def test_admin_still_lists_deleted_listings(self):
        self._delete()
        admin = User.objects.create_superuser(
            email="admin@test.com", username="admin@test.com", password="p"
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:products_product_changelist"))
        self.assertContains(response, "Stara vaza")
