"""
Ratings between buyers and sellers after a sale (issue #9).
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chat.models import Conversation
from orders.models import Sale
from products.models import Product
from ratings.models import RATING_WINDOW, Rating, RatingReport
from ratings.services import pending_sales, rating_summary
from users.models import User


def _make_user(email, is_seller=False):
    return User.objects.create_user(
        email=email, username=email, password="testpass123", is_seller=is_seller
    )


class RatingTestCase(TestCase):
    def setUp(self):
        self.seller_user = _make_user("seller@test.com", is_seller=True)
        self.seller = self.seller_user.seller_profile
        self.buyer = _make_user("buyer@test.com")
        self.product = Product.objects.create(
            seller=self.seller,
            title="Lampa",
            description="Opis",
            price=1000,
            status="sold",
            stock=0,
        )
        self.sale = Sale.objects.create(
            product=self.product,
            product_title="Lampa",
            seller=self.seller,
            buyer=self.buyer,
        )
        self.url = reverse("rate_sale", args=[self.sale.pk])

    def _rate(self, user, score=5, text="Sve super", **aspects):
        self.client.force_login(user)
        return self.client.post(self.url, {"score": score, "text": text, **aspects})

    def _age_sale(self, days):
        Sale.objects.filter(pk=self.sale.pk).update(
            created_at=timezone.now() - RATING_WINDOW - timedelta(days=days)
        )


class RateSaleTests(RatingTestCase):
    def test_buyer_rates_seller_with_aspects(self):
        response = self._rate(self.buyer, score=4, accuracy=5, communication="")
        self.assertRedirects(response, reverse("my_ratings"))
        rating = Rating.objects.get()
        self.assertEqual(rating.direction, Rating.BUYER_TO_SELLER)
        self.assertEqual(
            (rating.author, rating.subject), (self.buyer, self.seller_user)
        )
        self.assertEqual((rating.score, rating.accuracy), (4, 5))
        self.assertIsNone(rating.communication)
        self.assertIsNone(rating.payment)

    def test_seller_rates_buyer(self):
        self._rate(self.seller_user, score=3, payment=2)
        rating = Rating.objects.get()
        self.assertEqual(rating.direction, Rating.SELLER_TO_BUYER)
        self.assertEqual((rating.subject, rating.payment), (self.buyer, 2))

    def test_form_shows_direction_aspects(self):
        self.client.force_login(self.seller_user)
        response = self.client.get(self.url)
        self.assertContains(response, "Plaćanje")
        self.assertNotContains(response, "Artikal kao u opisu")

    def test_outsider_forbidden(self):
        response = self._rate(_make_user("other@test.com"))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Rating.objects.exists())

    def test_one_rating_per_side(self):
        self._rate(self.buyer, score=5)
        self._rate(self.buyer, score=1)
        self.assertEqual(Rating.objects.get().score, 5)

    def test_score_required_and_bounded(self):
        self._rate(self.buyer, score="")
        self._rate(self.buyer, score=6)
        self._rate(self.buyer, score=5, accuracy=9)
        self.assertFalse(Rating.objects.exists())

    def test_window_closes(self):
        self._age_sale(1)
        response = self._rate(self.buyer)
        self.assertRedirects(response, reverse("my_ratings"))
        self.assertFalse(Rating.objects.exists())


class BlindReleaseTests(RatingTestCase):
    def test_hidden_until_both_rate(self):
        self._rate(self.buyer)
        self.assertFalse(Rating.objects.visible().exists())
        self._rate(self.seller_user)
        self.assertEqual(Rating.objects.visible().count(), 2)
        self.assertTrue(all(r.released_at for r in Rating.objects.all()))

    def test_released_when_window_closes(self):
        self._rate(self.buyer)
        self._age_sale(1)
        self.assertEqual(Rating.objects.visible().count(), 1)

    def test_shop_page_shows_only_released(self):
        self._rate(self.buyer, score=4, text="Brza isporuka")
        shop_url = reverse("shop_detail", args=[self.seller.shop_slug])
        self.assertNotContains(self.client.get(shop_url), "Brza isporuka")
        self._rate(self.seller_user)
        response = self.client.get(shop_url)
        self.assertContains(response, "Brza isporuka")
        self.assertEqual(response.context["seller_rating"]["count"], 1)

    def test_hidden_by_staff_not_shown(self):
        self._rate(self.buyer)
        self._rate(self.seller_user)
        Rating.objects.update(is_hidden=True)
        self.assertEqual(rating_summary(self.buyer, Rating.SELLER_TO_BUYER)["count"], 0)


class SummaryAndPendingTests(RatingTestCase):
    def test_summary_averages(self):
        self._rate(self.buyer, score=4, accuracy=5, handover=3)
        self._rate(self.seller_user)
        summary = rating_summary(self.seller_user, Rating.BUYER_TO_SELLER)
        self.assertEqual((summary["average"], summary["count"]), (4, 1))
        self.assertEqual(
            summary["aspects"],
            [("Artikal kao u opisu", 5), ("Isporuka / predaja", 3)],
        )

    def test_pending_sales_per_side(self):
        self.assertEqual(list(pending_sales(self.buyer)), [self.sale])
        self.assertEqual(list(pending_sales(self.seller_user)), [self.sale])
        self._rate(self.buyer)
        self.assertEqual(list(pending_sales(self.buyer)), [])
        self.assertEqual(list(pending_sales(self.seller_user)), [self.sale])
        self._age_sale(1)
        self.assertEqual(list(pending_sales(self.seller_user)), [])

    def test_my_ratings_prompts_and_lists_received(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("my_ratings"))
        self.assertContains(response, reverse("rate_sale", args=[self.sale.pk]))
        self._rate(self.buyer)
        self._rate(self.seller_user, text="Odličan kupac")
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("my_ratings"))
        self.assertNotContains(response, reverse("rate_sale", args=[self.sale.pk]))
        self.assertContains(response, "Odličan kupac")
        self.assertEqual(response.context["as_buyer"]["count"], 1)

    def test_my_ratings_shows_given_rating_waiting(self):
        self._rate(self.buyer, text="Sve super")
        response = self.client.get(reverse("my_ratings"))
        self.assertContains(response, "Vaša ocena za seller")
        self.assertContains(response, "Čeka ocenu druge strane")
        self.assertEqual(list(response.context["received"]), [])

    def test_my_ratings_seller_summary(self):
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse("my_ratings"))
        self.assertIsNotNone(response.context["as_seller"])
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("my_ratings"))
        self.assertIsNone(response.context["as_seller"])

    def test_my_ratings_requires_login(self):
        response = self.client.get(reverse("my_ratings"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_menu_links_and_pending_badge(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("account-settings"))
        self.assertEqual(response.context["pending_ratings_count"], 1)
        self.assertContains(response, f'href="{reverse("my_ratings")}"')
        self.assertContains(response, "chat-badge-menu")
        self._rate(self.buyer)
        response = self.client.get(reverse("account-settings"))
        self.assertEqual(response.context["pending_ratings_count"], 0)

    def test_no_pending_count_for_anonymous(self):
        response = self.client.get(reverse("home"))
        self.assertNotIn("pending_ratings_count", response.context)

    def test_chat_shows_buyer_rating_and_prompt(self):
        conversation = Conversation.objects.create(
            buyer=self.buyer, seller=self.seller, product=self.product
        )
        chat_url = reverse("chat_detail", args=[conversation.pk])
        self.client.force_login(self.seller_user)
        response = self.client.get(chat_url)
        self.assertContains(response, "Ocena kupca")
        self.assertEqual(response.context["sale_to_rate"], self.sale)
        self.client.force_login(self.buyer)
        response = self.client.get(chat_url)
        self.assertNotContains(response, "Ocena kupca")
        self.assertEqual(response.context["sale_to_rate"], self.sale)


class ReplyAndReportTests(RatingTestCase):
    def setUp(self):
        super().setUp()
        self._rate(self.buyer, score=2)
        self._rate(self.seller_user)
        self.rating = Rating.objects.get(direction=Rating.BUYER_TO_SELLER)
        self.client.force_login(self.seller_user)

    def test_subject_replies_once(self):
        url = reverse("rating_reply", args=[self.rating.pk])
        self.client.post(url, {"reply": "Žao nam je"})
        self.client.post(url, {"reply": "Drugi odgovor"})
        self.rating.refresh_from_db()
        self.assertEqual(self.rating.reply, "Žao nam je")
        self.assertIsNotNone(self.rating.replied_at)

    def test_only_subject_can_reply_or_report(self):
        self.client.force_login(self.buyer)
        reply = self.client.post(
            reverse("rating_reply", args=[self.rating.pk]), {"reply": "x"}
        )
        report = self.client.post(
            reverse("rating_report", args=[self.rating.pk]), {"reason": "x"}
        )
        self.assertEqual((reply.status_code, report.status_code), (403, 403))

    def test_unreleased_rating_cannot_be_replied(self):
        Rating.objects.update(released_at=None)
        response = self.client.post(
            reverse("rating_reply", args=[self.rating.pk]), {"reply": "x"}
        )
        self.assertEqual(response.status_code, 404)

    def test_report_once(self):
        url = reverse("rating_report", args=[self.rating.pk])
        self.client.post(url, {"reason": "Netačno"})
        self.client.post(url, {"reason": "Ponovo"})
        report = RatingReport.objects.get()
        self.assertEqual(
            (report.reporter, report.reason), (self.seller_user, "Netačno")
        )
        self.assertFalse(report.is_resolved)

    def test_report_redirects_back(self):
        shop_url = reverse("shop_detail", args=[self.seller.shop_slug])
        response = self.client.post(
            reverse("rating_report", args=[self.rating.pk]),
            {"reason": "Netačno", "next": shop_url},
        )
        self.assertRedirects(response, shop_url)
