"""
Seller.open_for, the only way a shop is opened (#89).
"""

from unittest import mock

import pytest

from users.models import User

from . import models
from .models import Seller, free_shop_slug, shop_slug_from_name


def _user(email="ana.petrovic@example.com", **extra):
    return User.objects.create_user(email=email, username=email, **extra)


@pytest.mark.django_db
class TestOpenFor:
    def test_opens_a_shop_with_a_free_subscription(self):
        user = _user()
        seller = Seller.open_for(user, shop_name="Ana Vintage")
        assert seller.user == user
        assert seller.shop_name == "Ana Vintage"
        assert seller.shop_slug == "ana-vintage"
        assert seller.tier == "garazna"
        [subscription] = seller.subscriptions.all()
        assert subscription.status == "active"
        assert subscription.amount == 0
        assert user.is_seller

    def test_is_idempotent(self):
        user = _user()
        first = Seller.open_for(user, shop_name="Prva")
        again = Seller.open_for(user, shop_name="Druga")
        assert again.pk == first.pk
        assert again.shop_name == "Prva"
        assert Seller.objects.count() == 1
        assert first.subscriptions.count() == 1

    def test_slug_never_uses_the_email(self):
        user = _user(first_name="Ana", last_name="Petrović")
        seller = Seller.open_for(user)
        assert seller.shop_name == "Prodavnica"
        assert seller.shop_slug == "prodavnica"
        assert "ana" not in seller.shop_slug
        assert "petrovic" not in seller.shop_slug

    def test_taken_slug_gets_a_numeric_suffix(self):
        slugs = [
            Seller.open_for(_user(f"u{i}@example.com"), shop_name="Radnja").shop_slug
            for i in range(3)
        ]
        assert slugs == ["radnja", "radnja-2", "radnja-3"]

    def test_explicit_slug_is_used_and_suffixed_if_taken(self):
        Seller.open_for(_user("a@example.com"), shop_name="X", shop_slug="moja")
        seller = Seller.open_for(
            _user("b@example.com"), shop_name="Y", shop_slug="moja"
        )
        assert seller.shop_slug == "moja-2"

    def test_reserved_paths_are_never_slugs(self):
        seller = Seller.open_for(_user(), shop_name="Dashboard")
        assert seller.shop_slug == "dashboard-2"

    def test_serbian_letters_and_long_names(self):
        assert shop_slug_from_name("Đurđevak & Žuta kuća") == "djurdjevak-zuta-kuca"
        assert shop_slug_from_name("!!!") == ""
        long_name = "a" * 80
        Seller.open_for(_user("a@example.com"), shop_name=long_name)
        seller = Seller.open_for(_user("b@example.com"), shop_name=long_name)
        assert seller.shop_slug == "a" * 48 + "-2"
        assert free_shop_slug("") == "prodavnica"

    def test_extra_fields_are_saved(self):
        seller = Seller.open_for(_user(), shop_name="R", location="Niš")
        assert Seller.objects.get(pk=seller.pk).location == "Niš"

    def test_failed_subscription_leaves_no_shop(self):
        user = _user()
        with mock.patch.object(
            Seller, "create_initial_subscription", side_effect=RuntimeError
        ):
            with pytest.raises(RuntimeError):
                Seller.open_for(user, shop_name="R")
        assert not Seller.objects.exists()

    def test_concurrent_open_returns_the_shop_that_won(self):
        """Another request opened this user's shop after open_for checked:
        the insert fails and the shop that won is returned."""
        user = _user()
        winner = Seller.objects.bulk_create(
            [
                Seller(
                    user=User.objects.get(pk=user.pk),
                    shop_name="Prvi",
                    shop_slug="prvi",
                )
            ]
        )[0]
        real_filter = Seller.objects.filter
        checks = []

        def stale_first_check(*args, **kwargs):
            checks.append(kwargs)
            if len(checks) == 1:
                return Seller.objects.none()  # checked before the winner committed
            return real_filter(*args, **kwargs)

        with mock.patch.object(Seller.objects, "filter", stale_first_check):
            seller = Seller.open_for(user, shop_name="Drugi")
        assert seller.pk == winner.pk
        assert seller.shop_name == "Prvi"
        assert user.seller_profile.pk == winner.pk  # not the unsaved one
        assert Seller.objects.count() == 1

    def test_slug_taken_by_a_concurrent_request_is_retried(self):
        """The free slug was taken between the check and the insert."""
        Seller.objects.bulk_create(
            [Seller(user=_user("other@example.com"), shop_name="R", shop_slug="radnja")]
        )
        real_free = models.free_shop_slug
        picked = []

        def stale_then_real(base):
            picked.append(real_free(base) if picked else "radnja")
            return picked[-1]

        with mock.patch.object(models, "free_shop_slug", stale_then_real):
            seller = Seller.open_for(_user(), shop_name="Radnja")
        assert picked == ["radnja", "radnja-2"]
        assert seller.shop_slug == "radnja-2"
        assert seller.subscriptions.count() == 1
