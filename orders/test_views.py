"""
Marking a product as sold to a buyer from chat (issue #9).
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chat.models import Conversation
from orders.models import Sale
from products.models import Product
from users.models import User


def _make_user(email, is_seller=False):
    return User.objects.create_user(
        email=email, username=email, password="testpass123", is_seller=is_seller
    )


class MarkSoldTests(TestCase):
    def setUp(self):
        self.seller_user = _make_user("seller@test.com", is_seller=True)
        self.seller = self.seller_user.seller_profile
        self.buyer = _make_user("buyer@test.com")
        self.product = Product.objects.create(
            seller=self.seller,
            title="Lampa",
            description="Opis",
            price=1000,
            status="published",
        )
        Conversation.objects.create(
            buyer=self.buyer, seller=self.seller, product=self.product
        )
        self.url = reverse("product_mark_sold", args=[self.product.id])
        self.client.force_login(self.seller_user)

    def test_lists_buyers_from_chat_only(self):
        _make_user("stranger@test.com")
        admin = _make_user("admin@test.com")
        Conversation.objects.create(
            buyer=admin, seller=self.seller, product=self.product, is_team=True
        )
        response = self.client.get(self.url)
        self.assertEqual(list(response.context["candidates"]), [self.buyer])

    def test_other_users_cannot_mark_sold(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(
            self.client.post(self.url, {"buyer": self.buyer.pk}).status_code, 403
        )
        self.assertFalse(Sale.objects.exists())

    def test_sale_marks_last_item_sold(self):
        response = self.client.post(self.url, {"buyer": self.buyer.pk})
        self.assertRedirects(response, reverse("seller_products_list"))
        sale = Sale.objects.get()
        self.assertEqual(
            (sale.buyer, sale.seller, sale.product_title),
            (self.buyer, self.seller, "Lampa"),
        )
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.status), (0, "sold"))

    def test_sale_with_stock_left_stays_published(self):
        Product.objects.filter(pk=self.product.pk).update(stock=2)
        self.client.post(self.url, {"buyer": self.buyer.pk})
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.status), (1, "published"))

    def test_buyer_must_have_chatted(self):
        stranger = _make_user("stranger@test.com")
        self.client.post(self.url, {"buyer": stranger.pk})
        self.client.post(self.url, {"buyer": ""})
        self.assertFalse(Sale.objects.exists())

    def test_same_buyer_cannot_buy_twice(self):
        Product.objects.filter(pk=self.product.pk).update(stock=2)
        self.client.post(self.url, {"buyer": self.buyer.pk})
        response = self.client.get(self.url)
        self.assertEqual(list(response.context["candidates"]), [])
        self.client.post(self.url, {"buyer": self.buyer.pk})
        self.assertEqual(Sale.objects.count(), 1)

    def test_sold_product_redirects(self):
        Product.objects.filter(pk=self.product.pk).update(status="sold")
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("seller_products_list"))

    def test_draft_and_archived_cannot_be_sold(self):
        for status in ("draft", "archived"):
            Product.objects.filter(pk=self.product.pk).update(status=status)
            response = self.client.post(self.url, {"buyer": self.buyer.pk})
            self.assertRedirects(response, reverse("seller_products_list"))
        self.assertFalse(Sale.objects.exists())

    def test_expired_listing_sale_keeps_listing_period(self):
        expired = timezone.now() - timedelta(days=1)
        Product.objects.filter(pk=self.product.pk).update(
            status="expired", stock=2, expires_at=expired
        )
        self.client.post(self.url, {"buyer": self.buyer.pk})
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.status), (1, "expired"))
        self.assertEqual(self.product.expires_at, expired)

    def test_published_listing_period_not_restarted(self):
        expired = timezone.now() - timedelta(days=1)
        Product.objects.filter(pk=self.product.pk).update(stock=2, expires_at=expired)
        self.client.post(self.url, {"buyer": self.buyer.pk})
        self.product.refresh_from_db()
        self.assertEqual(self.product.expires_at, expired)

    def test_resubmit_after_last_item_sold_is_rejected(self):
        other = _make_user("other@test.com")
        Conversation.objects.create(
            buyer=other, seller=self.seller, product=self.product
        )
        self.client.post(self.url, {"buyer": self.buyer.pk})
        self.client.post(self.url, {"buyer": other.pk})
        self.assertEqual(Sale.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def test_non_numeric_buyer_is_a_form_error(self):
        response = self.client.post(self.url, {"buyer": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Sale.objects.exists())

    def test_chat_hides_mark_sold_once_buyer_bought(self):
        Product.objects.filter(pk=self.product.pk).update(stock=2)
        self.client.post(self.url, {"buyer": self.buyer.pk})
        conversation = Conversation.objects.get()
        response = self.client.get(reverse("chat_detail", args=[conversation.pk]))
        self.assertNotContains(response, "Prodato ovom kupcu")

    def test_buyer_preselected_from_chat(self):
        response = self.client.get(self.url, {"buyer": self.buyer.pk})
        self.assertContains(response, f'value="{self.buyer.pk}" checked')

    def test_chat_shows_mark_sold_link_to_seller_only(self):
        conversation = Conversation.objects.get()
        chat_url = reverse("chat_detail", args=[conversation.pk])
        self.assertContains(self.client.get(chat_url), "Prodato ovom kupcu")
        self.client.force_login(self.buyer)
        self.assertNotContains(self.client.get(chat_url), "Prodato ovom kupcu")
