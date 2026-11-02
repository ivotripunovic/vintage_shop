"""
View tests for product view counting, wishlist counts and recent viewers.
"""

from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from favourites.models import WishlistItem
from products.forms import MAX_UPLOAD_MB, MB
from products.models import (
    Product,
    ProductCategory,
    ProductCondition,
    ProductImage,
    ProductView,
)
from products.popularity import (
    RECENT_VIEWER_WINDOW,
    recent_viewer_count,
    touch_recent_viewer,
)
from sellers.models import Seller
from users.models import User

BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) Firefox/130.0"


def browser():
    return Client(HTTP_USER_AGENT=BROWSER_UA)


class ProductPopularityTests(TestCase):
    """Unique views, wishlist count and recent viewers on product pages."""

    def setUp(self):
        cache.clear()
        self.seller_user = User.objects.create_user(
            email="seller@test.com",
            username="seller@test.com",
            password="testpass123",
            is_seller=True,
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=self.seller_user,
            defaults={"shop_name": "Test Shop", "shop_slug": "test-shop"},
        )
        self.product = Product.objects.create(
            seller=self.seller,
            title="Old Lamp",
            description="A lamp",
            price=10,
            status="published",
        )
        self.url = reverse("product_detail", args=[self.product.id])

    def _buyer(self, n):
        user = User.objects.create_user(
            email=f"buyer{n}@test.com",
            username=f"buyer{n}@test.com",
            password="testpass123",
        )
        client = browser()
        client.force_login(user)
        return user, client

    def _view_count(self):
        self.product.refresh_from_db()
        return self.product.view_count

    def test_logged_in_user_counts_once(self):
        _, client = self._buyer(1)
        client.get(self.url)
        client.get(self.url)
        self.assertEqual(self._view_count(), 1)

    def test_different_users_count_separately(self):
        self._buyer(1)[1].get(self.url)
        self._buyer(2)[1].get(self.url)
        self.assertEqual(self._view_count(), 2)

    def test_anonymous_session_counts_once(self):
        client = browser()
        client.get(self.url)
        client.get(self.url)
        self.assertEqual(self._view_count(), 1)
        browser().get(self.url)
        self.assertEqual(self._view_count(), 2)
        self.assertEqual(ProductView.objects.filter(user=None).count(), 2)

    def test_owner_view_not_counted(self):
        client = browser()
        client.force_login(self.seller_user)
        client.get(self.url)
        self.assertEqual(self._view_count(), 0)
        self.assertEqual(recent_viewer_count(self.product.pk), 0)

    def test_bot_view_not_counted(self):
        Client(HTTP_USER_AGENT="Mozilla/5.0 (compatible; Googlebot/2.1)").get(self.url)
        self.assertEqual(self._view_count(), 0)

    def test_request_without_user_agent_not_counted(self):
        Client().get(self.url)
        self.assertEqual(self._view_count(), 0)

    def test_head_request_not_counted(self):
        browser().head(self.url)
        self.assertEqual(self._view_count(), 0)

    def test_prefetch_not_counted(self):
        browser().get(self.url, HTTP_SEC_PURPOSE="prefetch;prerender")
        browser().get(self.url, HTTP_PURPOSE="prefetch")
        self.assertEqual(self._view_count(), 0)

    def test_page_shows_view_and_wishlist_counts(self):
        buyer, client = self._buyer(1)
        WishlistItem.objects.create(user=buyer, product=self.product)
        WishlistItem.objects.create(user=self._buyer(2)[0], product=self.product)
        response = client.get(self.url)
        self.assertEqual(response.context["product"].view_count, 1)
        self.assertEqual(response.context["product"].wishlist_count, 2)
        self.assertContains(response, "Pregledi")

    def test_recent_viewers_excludes_current_visitor(self):
        _, first = self._buyer(1)
        response = first.get(self.url)
        self.assertEqual(response.context["recent_viewers"], 0)
        self.assertNotContains(response, "Gledalo nedavno")

        _, second = self._buyer(2)
        response = second.get(self.url)
        self.assertEqual(response.context["recent_viewers"], 1)
        self.assertContains(response, "Gledalo nedavno")

    def test_recent_viewers_expire_after_window(self):
        with mock.patch("products.popularity.time.time", return_value=1000.0):
            touch_recent_viewer(self.product.pk, "u1")
        later = 1000.0 + RECENT_VIEWER_WINDOW + 1
        with mock.patch("products.popularity.time.time", return_value=later):
            self.assertEqual(recent_viewer_count(self.product.pk), 0)
            touch_recent_viewer(self.product.pk, "u2")
            key = f"product_recent_viewers:{self.product.pk}"
            self.assertEqual(list(cache.get(key)), ["u2"])

    def test_seller_list_shows_counts(self):
        self._buyer(1)[1].get(self.url)
        WishlistItem.objects.create(user=self._buyer(2)[0], product=self.product)
        client = browser()
        client.force_login(self.seller_user)
        response = client.get(reverse("seller_products_list"))
        listed = response.context["products"][0]
        self.assertEqual(listed.view_count, 1)
        self.assertEqual(listed.wishlist_count, 1)
        self.assertContains(response, "1 pregleda")


class SellerListingFlowTests(TestCase):
    """Seller-side create, edit, photo and publish flow."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="flow@test.com",
            username="flow@test.com",
            password="testpass123",
            is_seller=True,
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user,
            defaults={"shop_name": "Flow Shop", "shop_slug": "flow-shop"},
        )
        self.client.force_login(self.user)
        self.draft = Product.objects.create(
            seller=self.seller,
            title="Old Chair",
            description="A chair",
            price=100,
            status="draft",
        )

    def _form_data(self, **overrides):
        parent = ProductCategory.objects.get_or_create(name="Kuća", slug="kuca")[0]
        category = ProductCategory.objects.get_or_create(
            name="Nameštaj", slug="namestaj", parent=parent
        )[0]
        condition = ProductCondition.objects.get_or_create(name="Dobro")[0]
        data = {
            "title": "Old Chair",
            "description": "A chair",
            "price": "100",
            "stock": "1",
            "category": category.id,
            "condition": condition.id,
        }
        data.update(overrides)
        return data

    def test_editing_draft_returns_to_seller_page(self):
        url = reverse("product_edit", args=[self.draft.id])
        response = self.client.post(url, self._form_data(title="Wooden Chair"))
        self.assertRedirects(
            response, reverse("product_seller_detail", args=[self.draft.id])
        )
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.title, "Wooden Chair")

    def _edit(self, **data):
        url = reverse("product_edit", args=[self.draft.id])
        response = self.client.post(url, self._form_data(**data))
        self.draft.refresh_from_db()
        return response

    def test_create_always_saves_draft_and_goes_to_photos(self):
        response = self.client.post(
            reverse("product_create"), self._form_data(title="Lamp", status="sold")
        )
        product = Product.objects.get(title="Lamp")
        self.assertEqual(product.status, "draft")
        self.assertRedirects(response, reverse("product_images", args=[product.id]))

    def test_publish_without_photo_keeps_draft_and_asks_for_photos(self):
        response = self._edit(title="Wooden Chair", action="publish")
        self.assertEqual(self.draft.status, "draft")
        self.assertEqual(self.draft.title, "Wooden Chair")
        self.assertRedirects(response, reverse("product_images", args=[self.draft.id]))

    def test_publish_with_photo(self):
        ProductImage.objects.create(product=self.draft, image="products/test.jpg")
        self._edit(action="publish")
        self.assertEqual(self.draft.status, "published")
        self.assertIsNotNone(self.draft.listed_at)

    def test_archive(self):
        self._edit(action="archive")
        self.assertEqual(self.draft.status, "archived")

    def test_posted_status_is_ignored(self):
        self._edit(status="sold")
        self.assertEqual(self.draft.status, "draft")

    def test_sold_product_cannot_be_published_from_form(self):
        ProductImage.objects.create(product=self.draft, image="products/test.jpg")
        self.draft.status = "sold"
        self.draft.save()
        self._edit(action="publish")
        self.assertEqual(self.draft.status, "sold")

    def test_form_pages_show_matching_actions(self):
        create = self.client.get(reverse("product_create"))
        self.assertContains(create, "Dalje: fotografije")
        self.assertNotContains(create, 'name="status"')
        edit = self.client.get(reverse("product_edit", args=[self.draft.id]))
        self.assertContains(edit, 'value="publish"')
        self.assertContains(edit, 'value="archive"')
        self.draft.status = "sold"
        self.draft.save()
        edit = self.client.get(reverse("product_edit", args=[self.draft.id]))
        self.assertNotContains(edit, 'value="publish"')
        self.assertNotContains(edit, 'value="archive"')


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class SellerPhotoPageTests(TestCase):
    """Photo upload page and the publish step after it."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="photos@test.com",
            username="photos@test.com",
            password="testpass123",
            is_seller=True,
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user,
            defaults={"shop_name": "Photo Shop", "shop_slug": "photo-shop"},
        )
        self.client.force_login(self.user)
        self.product = Product.objects.create(
            seller=self.seller,
            title="Old Radio",
            description="A radio",
            price=100,
        )
        self.url = reverse("product_images", args=[self.product.id])

    def _photo(self, name="a.jpg", size=10):
        return SimpleUploadedFile(name, b"x" * size, content_type="image/jpeg")

    def test_upload_goes_to_product_page(self):
        response = self.client.post(
            self.url, {"images": [self._photo("a.jpg"), self._photo("b.jpg")]}
        )
        self.assertRedirects(
            response, reverse("product_seller_detail", args=[self.product.id])
        )
        alt_texts = list(self.product.images.values_list("alt_text", flat=True))
        self.assertEqual(
            alt_texts, ["Old Radio – fotografija 1", "Old Radio – fotografija 2"]
        )
        self.assertEqual(
            list(self.product.images.values_list("order", flat=True)), [1, 2]
        )

    def test_upload_over_total_limit_is_rejected(self):
        half = (MAX_UPLOAD_MB * MB) // 2 + 1
        response = self.client.post(
            self.url,
            {"images": [self._photo("a.jpg", half), self._photo("b.jpg", half)]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Otpremite ih u više navrata")
        self.assertFalse(self.product.images.exists())

    def test_page_shows_real_limits(self):
        response = self.client.get(self.url)
        self.assertContains(response, f"ukupno do {MAX_UPLOAD_MB} MB")
        self.assertNotContains(response, "5MB")
        self.assertRegex(
            response.content.decode(), r"<title>Slike proizvoda — [^<]*</title>"
        )

    def test_product_page_explains_missing_photo(self):
        detail = reverse("product_seller_detail", args=[self.product.id])
        response = self.client.get(detail)
        self.assertContains(response, "Dodajte bar jednu fotografiju")
        self.assertNotContains(response, "Objavi proizvod")

    def test_product_page_shows_publish_and_quota(self):
        ProductImage.objects.create(product=self.product, image="products/t.jpg")
        detail = reverse("product_seller_detail", args=[self.product.id])
        response = self.client.get(detail)
        self.assertContains(response, "Objavi proizvod")
        left = self.seller.listings_left_this_month()
        if left is not None:
            self.assertContains(response, f"preostalih {left} novih oglasa")

    def _three_photos(self):
        return [
            ProductImage.objects.create(
                product=self.product, image=f"products/{n}.jpg", order=n + 1
            )
            for n in range(3)
        ]

    def _move(self, image, to):
        url = reverse("product_image_move", args=[image.id])
        return self.client.post(url, {"to": to})

    def _order(self):
        return list(self.product.images.values_list("id", flat=True))

    def test_make_cover_moves_photo_first(self):
        a, b, c = self._three_photos()
        response = self._move(c, "first")
        self.assertRedirects(response, f"{self.url}#image-{c.id}")
        self.assertEqual(self._order(), [c.id, a.id, b.id])
        self.assertEqual(
            list(self.product.images.values_list("order", flat=True)), [0, 1, 2]
        )

    def test_move_up_and_down(self):
        a, b, c = self._three_photos()
        self._move(b, "up")
        self.assertEqual(self._order(), [b.id, a.id, c.id])
        self._move(b, "down")
        self._move(b, "down")
        self.assertEqual(self._order(), [a.id, c.id, b.id])

    def test_move_past_the_ends_is_a_no_op(self):
        a, b, c = self._three_photos()
        self._move(a, "up")
        self._move(c, "down")
        self.assertEqual(self._order(), [a.id, b.id, c.id])

    def test_cover_is_used_everywhere(self):
        a, b, c = self._three_photos()
        self._move(c, "first")
        self.product.status = "published"
        self.product.save()
        public = self.client.get(reverse("product_detail", args=[self.product.id]))
        self.assertEqual(public.context["images"][0].id, c.id)
        self.assertEqual(self.product.images.first().id, c.id)

    def test_unknown_direction_is_rejected(self):
        a, *_ = self._three_photos()
        self.assertEqual(self._move(a, "sideways").status_code, 400)

    def test_cannot_move_another_sellers_photo(self):
        a, *_ = self._three_photos()
        other = User.objects.create_user(
            email="other@test.com",
            username="other@test.com",
            password="testpass123",
            is_seller=True,
        )
        Seller.objects.get_or_create(
            user=other, defaults={"shop_name": "Other", "shop_slug": "other"}
        )
        self.client.force_login(other)
        self.assertEqual(self._move(a, "down").status_code, 404)

    def test_photo_page_shows_cover_and_controls(self):
        a, b, c = self._three_photos()
        response = self.client.get(self.url)
        self.assertContains(response, "Naslovna", count=2)  # badge + footer hint
        self.assertContains(response, 'value="first"', count=2)
        self.assertContains(response, 'value="up"', count=2)
        self.assertContains(response, 'value="down"', count=2)


class ProductFormPageTests(TestCase):
    """How the product form renders the defaults from #45."""

    def setUp(self):
        user = User.objects.create_user(
            email="form@test.com",
            username="form@test.com",
            password="testpass123",
            is_seller=True,
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=user, defaults={"shop_name": "Form Shop", "shop_slug": "form-shop"}
        )
        self.client.force_login(user)
        self.condition = ProductCondition.objects.create(
            name="Kao novo", description="Korišćeno jednom ili dvaput"
        )

    def test_create_page_shows_condition_cards_and_collapsed_stock(self):
        response = self.client.get(reverse("product_create"))
        self.assertContains(response, 'type="radio"')
        self.assertContains(response, "Korišćeno jednom ili dvaput")
        self.assertContains(response, "Izaberite kategoriju")
        self.assertContains(response, '<details class="group">')
        self.assertRegex(
            response.content.decode(), r"<title>Dodaj proizvod — [^<]*</title>"
        )

    def test_edit_page_opens_stock_when_several_items(self):
        product = Product.objects.create(
            seller=self.seller,
            title="Čaše",
            description="Set",
            price=Decimal("12500"),
            stock=6,
            condition=self.condition,
        )
        response = self.client.get(reverse("product_edit", args=[product.id]))
        self.assertContains(response, '<details class="group" open>')
        self.assertContains(response, 'value="12.500"')
        self.assertContains(response, "checked")


class DuplicateAndDefaultsTests(TestCase):
    """Copying a listing and remembering the last category/condition (#46)."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="copy@test.com",
            username="copy@test.com",
            password="testpass123",
            is_seller=True,
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user, defaults={"shop_name": "Copy", "shop_slug": "copy"}
        )
        self.client.force_login(self.user)
        self.category = ProductCategory.objects.create(name="Lampe", slug="lampe")
        self.condition = ProductCondition.objects.create(name="Dobro")
        self.original = Product.objects.create(
            seller=self.seller,
            title="Stona lampa",
            description="Mesing, ispravna.",
            price=Decimal("4500"),
            category=self.category,
            condition=self.condition,
            stock=0,
            status="sold",
        )
        ProductImage.objects.create(product=self.original, image="products/l.jpg")

    def _duplicate(self, product):
        return self.client.post(reverse("product_duplicate", args=[product.id]))

    def test_duplicate_copies_details_as_draft_without_photos(self):
        response = self._duplicate(self.original)
        copy = Product.objects.exclude(id=self.original.id).get()
        self.assertRedirects(response, reverse("product_edit", args=[copy.id]))
        for field in ["title", "description", "price", "category", "condition"]:
            self.assertEqual(getattr(copy, field), getattr(self.original, field))
        self.assertEqual(copy.status, "draft")
        self.assertEqual(copy.stock, 1)  # the original was sold out
        self.assertIsNone(copy.listed_at)
        self.assertFalse(copy.images.exists())

    def test_cannot_duplicate_another_sellers_or_deleted_listing(self):
        self.original.soft_delete()
        self.assertEqual(self._duplicate(self.original).status_code, 404)
        other = User.objects.create_user(
            email="x@test.com", username="x@test.com", password="p", is_seller=True
        )
        Seller.objects.get_or_create(
            user=other, defaults={"shop_name": "X", "shop_slug": "x"}
        )
        theirs = Product.objects.create(
            seller=other.seller_profile, title="T", description="D", price=1
        )
        self.assertEqual(self._duplicate(theirs).status_code, 404)

    def test_duplicate_requires_post(self):
        url = reverse("product_duplicate", args=[self.original.id])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_create_form_remembers_last_category_and_condition(self):
        response = self.client.get(reverse("product_create"))
        form = response.context["form"]
        self.assertEqual(form["category"].value(), self.category.id)
        self.assertEqual(form["condition"].value(), self.condition.id)

    def test_create_form_ignores_deleted_listings(self):
        self.original.soft_delete()
        form = self.client.get(reverse("product_create")).context["form"]
        self.assertIsNone(form["category"].value())

    def test_form_pages_have_separate_autosave_keys(self):
        create = self.client.get(reverse("product_create"))
        edit = self.client.get(reverse("product_edit", args=[self.original.id]))
        self.assertContains(
            create, f'data-autosave-key="product-form:{self.seller.id}:new"'
        )
        self.assertContains(
            edit,
            f'data-autosave-key="product-form:{self.seller.id}:{self.original.id}"',
        )

    def test_copy_buttons_on_seller_pages(self):
        url = reverse("product_duplicate", args=[self.original.id])
        detail = self.client.get(
            reverse("product_seller_detail", args=[self.original.id])
        )
        self.assertContains(detail, f'action="{url}"')
        listing = self.client.get(reverse("seller_products_list"))
        self.assertContains(listing, f'action="{url}"')
