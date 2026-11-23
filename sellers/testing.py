"""Test helpers for shops. Shops are opened only through Seller.open_for."""

from users.models import User

from .models import Seller


def make_seller(
    email="seller@example.com", shop_name=None, password="testpass123", **fields
):
    """A new user with an open shop; returns the Seller (``.user`` is the user).

    ``fields`` go to Seller.open_for (shop_slug, location, ...), except
    User fields, which are passed as ``user_fields={...}``.
    """
    user_fields = fields.pop("user_fields", {})
    user = User.objects.create_user(
        email=email, username=email, password=password, **user_fields
    )
    return Seller.open_for(user, shop_name=shop_name or "Test Shop", **fields)
