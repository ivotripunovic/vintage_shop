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

    def _update_product(self, product, action="add", next_url=None):
        data = {"action": action}
        if next_url:
            data["next"] = next_url
        return self.client.post(reverse("wishlist_update", args=[product.id]), data)

    def _update_seller(self, seller, action="add"):
        return self.client.post(
            reverse("favourite_seller_update", args=[seller.id]), {"action": action}
        )


class WishlistUpdateTests(FavouritesTestCase):
    def test_requires_login(self):
        self.client.logout()
        response = self._update_product(self.product)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertFalse(WishlistItem.objects.exists())

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse("wishlist_update", args=[self.product.id]))
        self.assertEqual(response.status_code, 405)

    def test_add_and_remove(self):
        self._update_product(self.product)
        self.assertTrue(
            WishlistItem.objects.filter(user=self.buyer, product=self.product).exists()
        )
        self._update_product(self.product, action="remove")
        self.assertFalse(WishlistItem.objects.exists())

    def test_redirects_back_to_next(self):
        url = reverse("product_detail", args=[self.product.id])
        response = self._update_product(self.product, next_url=url)
        self.assertRedirects(response, url)

    def test_ignores_next_on_other_site(self):
        response = self._update_product(self.product, next_url="https://evil.test/")
        self.assertRedirects(response, reverse("account-settings"))

    def test_cannot_save_own_product(self):
        self.client.force_login(self.seller_user)
        self._update_product(self.product)
        self.assertFalse(WishlistItem.objects.exists())

    def test_cannot_save_unpublished_product(self):
        draft = self._make_product("Nacrt", status="draft")
        self._update_product(draft)
        self.assertFalse(WishlistItem.objects.exists())

    def test_can_remove_product_that_is_no_longer_published(self):
        self._update_product(self.product)
        Product.objects.filter(pk=self.product.pk).update(status="sold")
        self._update_product(self.product, action="remove")
        self.assertFalse(WishlistItem.objects.exists())


class RepeatAndStaleRequestTests(FavouritesTestCase):
    """Double-clicks and stale pages must not flip the state or crash."""

    def test_adding_twice_keeps_one_entry(self):
        self._update_product(self.product)
        response = self._update_product(self.product)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WishlistItem.objects.count(), 1)

    def test_stale_add_does_not_remove(self):
        self._update_product(self.product)
        # A second tab still shows "Sačuvaj" and sends add again
        self._update_product(self.product, action="add")
        self.assertTrue(WishlistItem.objects.exists())

    def test_removing_when_nothing_is_saved(self):
        response = self._update_product(self.product, action="remove")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(WishlistItem.objects.exists())

    def test_favouriting_twice_keeps_one_entry(self):
        self._update_seller(self.seller)
        self._update_seller(self.seller)
        self.assertEqual(FavouriteSeller.objects.count(), 1)

    def test_unknown_action_is_rejected(self):
        response = self._update_product(self.product, action="toggle")
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            reverse("favourite_seller_update", args=[self.seller.id])
        )
        self.assertEqual(response.status_code, 400)


class InactiveShopTests(FavouritesTestCase):
    def _suspend_shop(self):
        self.seller.status = "suspended"
        self.seller.save()

    def test_cannot_save_item_from_suspended_shop(self):
        self._suspend_shop()
        self._update_product(self.product)
        self.assertFalse(WishlistItem.objects.exists())

    def test_profile_shows_suspended_shop_without_link(self):
        self._update_seller(self.seller)
        self._update_product(self.product)
        self._suspend_shop()
        response = self.client.get(reverse("account-settings"))
        self.assertContains(response, "Prodavnica trenutno nije aktivna")
        self.assertContains(response, "Više nije u ponudi")
        self.assertNotContains(
            response, reverse("shop_detail", args=[self.seller.shop_slug])
        )

    def test_product_page_of_suspended_shop_is_not_found(self):
        self._suspend_shop()
        response = self.client.get(reverse("product_detail", args=[self.product.id]))
        self.assertEqual(response.status_code, 404)

    def test_soft_deleted_product_page_is_not_found(self):
        self.product.soft_delete()
        response = self.client.get(reverse("product_detail", args=[self.product.id]))
        self.assertEqual(response.status_code, 404)


class FavouriteSellerUpdateTests(FavouritesTestCase):
    def test_add_and_remove(self):
        self._update_seller(self.seller)
        self.assertTrue(
            FavouriteSeller.objects.filter(user=self.buyer, seller=self.seller).exists()
        )
        self._update_seller(self.seller, action="remove")
        self.assertFalse(FavouriteSeller.objects.exists())

    def test_cannot_favourite_own_shop(self):
        self.client.force_login(self.seller_user)
        self._update_seller(self.seller)
        self.assertFalse(FavouriteSeller.objects.exists())

    def test_cannot_favourite_inactive_shop(self):
        self.seller.status = "suspended"
        self.seller.save()
        self._update_seller(self.seller)
        self.assertFalse(FavouriteSeller.objects.exists())

    def test_can_remove_shop_that_became_inactive(self):
        self._update_seller(self.seller)
        self.seller.status = "suspended"
        self.seller.save()
        self._update_seller(self.seller, action="remove")
        self.assertFalse(FavouriteSeller.objects.exists())


class ButtonTests(FavouritesTestCase):
    def test_product_page_shows_saved_state(self):
        url = reverse("product_detail", args=[self.product.id])
        self.assertContains(self.client.get(url), "♡ Sačuvaj")
        self._update_product(self.product)
        self.assertContains(self.client.get(url), "♥ Sačuvano")

    def test_product_page_hides_button_from_owner(self):
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse("product_detail", args=[self.product.id]))
        self.assertTrue(response.context["is_owner"])
        self.assertNotContains(
            response, reverse("wishlist_update", args=[self.product.id])
        )

    def test_product_page_sends_anonymous_users_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("product_detail", args=[self.product.id]))
        self.assertContains(response, f"{reverse('login')}?next=")

    def test_shop_page_shows_favourite_state(self):
        url = reverse("shop_detail", args=[self.seller.shop_slug])
        self.assertContains(self.client.get(url), "Dodaj u omiljene")
        self._update_seller(self.seller)
        self.assertContains(self.client.get(url), "♥ Omiljena prodavnica")

    def test_shop_page_hides_button_from_owner(self):
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse("shop_detail", args=[self.seller.shop_slug]))
        self.assertNotContains(
            response, reverse("favourite_seller_update", args=[self.seller.id])
        )


class ProfileListTests(FavouritesTestCase):
    def test_profile_lists_favourites_and_wishlist(self):
        self._update_seller(self.seller)
        self._update_product(self.product)
        response = self.client.get(reverse("account-settings"))
        self.assertContains(
            response, reverse("shop_detail", args=[self.seller.shop_slug])
        )
        self.assertContains(response, reverse("product_detail", args=[self.product.id]))

    def test_profile_marks_sold_items_and_hides_deleted_ones(self):
        sold = self._make_product("Prodata stolica")
        deleted = self._make_product("Obrisan sto")
        self._update_product(sold)
        self._update_product(deleted)
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
