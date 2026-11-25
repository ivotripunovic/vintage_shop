"""
Review of #89 (PR #90).
"""

from unittest import mock

import pytest
from django.contrib import admin
from django.db import IntegrityError
from django.test import RequestFactory
from django.urls import reverse

from conftest import migrate_scratch
from products.models import Product
from users.models import User

from .admin import SellerAdmin
from .forms import ShopSetupForm
from .models import Seller
from .testing import make_seller


@pytest.mark.django_db
class TestTypedSlug:
    def test_the_slug_checked_is_the_slug_saved(self):
        """ "my_shop_" is saved as "my_shop"; if that is taken, say so instead
        of silently saving "my_shop-2"."""
        make_seller("a@example.com", shop_name="X", shop_slug="my_shop")
        form = ShopSetupForm({"shop_name": "Y", "shop_slug": "my_shop_"})
        assert not form.is_valid()
        assert form.errors["shop_slug"] == ["Ova adresa prodavnice je zauzeta."]

    def test_typed_slug_is_saved_as_validated(self, client):
        user = make_seller("b@example.com", shop_name="B", tier="odrzivo").user
        client.force_login(user)
        client.post(
            reverse("seller_shop_setup"), {"shop_name": "Y", "shop_slug": "My-Shop-"}
        )
        assert Seller.objects.get(user=user).shop_slug == "my-shop"


@pytest.mark.django_db
class TestOpenForErrors:
    def test_other_integrity_errors_are_not_retried_or_renamed(self):
        user = User.objects.create_user(email="a@example.com", username="a")
        error = IntegrityError("CHECK constraint failed: something else")
        with mock.patch.object(Seller, "save", side_effect=error) as save:
            with pytest.raises(IntegrityError) as raised:
                Seller.open_for(user, shop_name="R")
        assert raised.value is error
        assert save.call_count == 1
        assert not user.is_seller  # no unsaved Seller left in the cache


@pytest.mark.django_db
def test_product_page_of_a_user_without_a_shop_is_404(client):
    product = Product.objects.create(
        seller=make_seller("s@example.com"), title="Lampa", price=100
    )
    client.force_login(User.objects.create_user(email="b@example.com", username="b"))
    response = client.get(reverse("product_seller_detail", args=[product.id]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_shops_added_in_the_admin_get_a_slug_and_a_subscription():
    model_admin = SellerAdmin(Seller, admin.site)
    request = RequestFactory().post("/")
    shops = []
    for i, name in enumerate(["Dashboard", "Dashboard"]):
        user = User.objects.create_user(email=f"u{i}@example.com", username=f"u{i}")
        seller = Seller(user=user, shop_name=name)
        model_admin.save_model(request, seller, form=None, change=False)
        shops.append(seller)
    assert [s.shop_slug for s in shops] == ["dashboard-2", "dashboard-3"]
    assert all(s.active_subscription for s in shops)


def test_backfill_starts_a_subscription_for_shops_without_one(scratch_db, capsys):
    before = [("sellers", "0005_seller_trader_confirmation")]
    after = [("sellers", "0006_backfill_missing_subscriptions")]
    apps = migrate_scratch(scratch_db, before, before)
    User = apps.get_model("users", "User")
    Seller = apps.get_model("sellers", "Seller")
    Subscription = apps.get_model("sellers", "SellerSubscription")
    bare = Seller.objects.create(
        user=User.objects.create(email="a@example.com", username="a"),
        shop_name="A",
        shop_slug="a",
        tier="odrzivo",
    )
    paying = Seller.objects.create(
        user=User.objects.create(email="b@example.com", username="b"),
        shop_name="B",
        shop_slug="b",
    )
    Subscription.objects.create(
        seller=paying,
        start_date="2026-11-01",
        renewal_date="2026-12-01",
        status="active",
        amount=0,
    )
    capsys.readouterr()

    apps = migrate_scratch(scratch_db, after, after)
    Subscription = apps.get_model("sellers", "SellerSubscription")
    [started] = Subscription.objects.filter(seller_id=bare.pk)
    assert started.status == "active"
    assert started.amount == 6500  # Održivo's price (SellerTier seed)
    assert Subscription.objects.filter(seller_id=paying.pk).count() == 1
    assert f"shop {bare.pk}" in capsys.readouterr().out
