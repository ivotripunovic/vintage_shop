"""
Favourite sellers and wishlist (issue #7).
"""

from django.test import TestCase
from django.urls import reverse

from favourites.models import FavouriteSeller, WishlistItem
from products.models import Product
from users.models import User


def _make_user(email, is_seller=False):
    return User.objects.create_user(
        email=email, username=email, password="testpass123", is_seller=is_seller
    )


class FavouritesTestCase(TestCase):
    def setUp(self):
        self.seller_user = _make_user("seller@test.com", is_seller=True)
        self.seller = self.seller_user.seller_profile
        self.buyer = _make_user("buyer@test.com")
        self.product = self._make_product("Lampa")
        self.client.force_login(self.buyer)

    def _make_product(self, title, status="published"):
        return Product.objects.create(
            seller=self.seller,
            title=title,
            description="Opis",
            price=1000,
            status=status,
        )

    def _toggle_product(self, product, next_url=None):
        data = {"next": next_url} if next_url else {}
        return self.client.post(reverse("wishlist_toggle", args=[product.id]), data)

    def _toggle_seller(self, seller):
        return self.client.post(reverse("favourite_seller_toggle", args=[seller.id]))


class WishlistToggleTests(FavouritesTestCase):
    def test_requires_login(self):
        self.client.logout()
        response = self._toggle_product(self.product)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertFalse(WishlistItem.objects.exists())

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse("wishlist_toggle", args=[self.product.id]))
        self.assertEqual(response.status_code, 405)

    def test_add_and_remove(self):
        self._toggle_product(self.product)
        self.assertTrue(
            WishlistItem.objects.filter(user=self.buyer, product=self.product).exists()
        )
        self._toggle_product(self.product)
        self.assertFalse(WishlistItem.objects.exists())

    def test_redirects_back_to_next(self):
        url = reverse("product_detail", args=[self.product.id])
        response = self._toggle_product(self.product, next_url=url)
        self.assertRedirects(response, url)

    def test_ignores_next_on_other_site(self):
        response = self._toggle_product(self.product, next_url="https://evil.test/")
        self.assertRedirects(response, reverse("account-settings"))

    def test_cannot_save_own_product(self):
        self.client.force_login(self.seller_user)
        self._toggle_product(self.product)
        self.assertFalse(WishlistItem.objects.exists())

    def test_cannot_save_unpublished_product(self):
        draft = self._make_product("Nacrt", status="draft")
        self._toggle_product(draft)
        self.assertFalse(WishlistItem.objects.exists())

    def test_can_remove_product_that_is_no_longer_published(self):
        self._toggle_product(self.product)
        Product.objects.filter(pk=self.product.pk).update(status="sold")
        self._toggle_product(self.product)
        self.assertFalse(WishlistItem.objects.exists())


class FavouriteSellerToggleTests(FavouritesTestCase):
    def test_add_and_remove(self):
        self._toggle_seller(self.seller)
        self.assertTrue(
            FavouriteSeller.objects.filter(user=self.buyer, seller=self.seller).exists()
        )
        self._toggle_seller(self.seller)
        self.assertFalse(FavouriteSeller.objects.exists())

    def test_cannot_favourite_own_shop(self):
        self.client.force_login(self.seller_user)
        self._toggle_seller(self.seller)
        self.assertFalse(FavouriteSeller.objects.exists())

    def test_cannot_favourite_inactive_shop(self):
        self.seller.status = "suspended"
        self.seller.save()
        self._toggle_seller(self.seller)
        self.assertFalse(FavouriteSeller.objects.exists())

    def test_can_remove_shop_that_became_inactive(self):
        self._toggle_seller(self.seller)
        self.seller.status = "suspended"
        self.seller.save()
        self._toggle_seller(self.seller)
        self.assertFalse(FavouriteSeller.objects.exists())


class ButtonTests(FavouritesTestCase):
    def test_product_page_shows_saved_state(self):
        url = reverse("product_detail", args=[self.product.id])
        self.assertContains(self.client.get(url), "♡ Sačuvaj")
        self._toggle_product(self.product)
        self.assertContains(self.client.get(url), "♥ Sačuvano")

    def test_product_page_hides_button_from_owner(self):
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse("product_detail", args=[self.product.id]))
        self.assertTrue(response.context["is_owner"])
        self.assertNotContains(
            response, reverse("wishlist_toggle", args=[self.product.id])
        )

    def test_product_page_sends_anonymous_users_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("product_detail", args=[self.product.id]))
        self.assertContains(response, f"{reverse('login')}?next=")

    def test_shop_page_shows_favourite_state(self):
        url = reverse("shop_detail", args=[self.seller.shop_slug])
        self.assertContains(self.client.get(url), "Dodaj u omiljene")
        self._toggle_seller(self.seller)
        self.assertContains(self.client.get(url), "♥ Omiljena prodavnica")

    def test_shop_page_hides_button_from_owner(self):
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse("shop_detail", args=[self.seller.shop_slug]))
        self.assertNotContains(
            response, reverse("favourite_seller_toggle", args=[self.seller.id])
        )


class ProfileListTests(FavouritesTestCase):
    def test_profile_lists_favourites_and_wishlist(self):
        self._toggle_seller(self.seller)
        self._toggle_product(self.product)
        response = self.client.get(reverse("account-settings"))
        self.assertContains(
            response, reverse("shop_detail", args=[self.seller.shop_slug])
        )
        self.assertContains(response, reverse("product_detail", args=[self.product.id]))

    def test_profile_marks_sold_items_and_hides_deleted_ones(self):
        sold = self._make_product("Prodata stolica")
        deleted = self._make_product("Obrisan sto")
        self._toggle_product(sold)
        self._toggle_product(deleted)
        Product.objects.filter(pk=sold.pk).update(status="sold")
        deleted.soft_delete()

        response = self.client.get(reverse("account-settings"))
        self.assertContains(response, "Prodata stolica")
        self.assertContains(response, "Više nije u ponudi")
        self.assertNotContains(response, "Obrisan sto")

    def test_empty_lists_show_hints(self):
        response = self.client.get(reverse("account-settings"))
        self.assertContains(response, "Još nemate omiljene prodavce")
        self.assertContains(response, "Lista želja je prazna")
