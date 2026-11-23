"""
Seller.open_for, the only way a shop is opened (#89).
"""

from unittest import mock

import pytest
from django.db import IntegrityError

from users.models import User

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
        """If another request opens the same user's shop between the check
        and the insert, the IntegrityError resolves to that shop."""
        user = _user()
        winner = {}
        real_create = Seller.objects.create

        def create_after_race(**kwargs):
            if not winner:
                winner["seller"] = real_create(
                    user=User.objects.get(pk=user.pk),
                    shop_name="Prvi",
                    shop_slug="prvi",
                )
                raise IntegrityError("duplicate user_id")
            return real_create(**kwargs)

        with mock.patch.object(Seller.objects, "create", side_effect=create_after_race):
            seller = Seller.open_for(user, shop_name="Drugi")
        assert seller.pk == winner["seller"].pk
        assert Seller.objects.count() == 1
