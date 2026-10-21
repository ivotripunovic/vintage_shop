"""
Add and remove favourite sellers and wishlist items.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from products.models import Product
from sellers.models import Seller

from .models import FavouriteSeller, WishlistItem


def _redirect_back(request, fallback):
    """Go back to the page the button was on, or to the fallback."""
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(fallback)


@login_required(login_url="login")
@require_POST
def favourite_seller_toggle(request, seller_id):
    """Add the seller to the user's favourites, or remove them if already there."""
    seller = get_object_or_404(Seller, pk=seller_id)
    fallback = "account-settings"

    deleted, _ = FavouriteSeller.objects.filter(
        user=request.user, seller=seller
    ).delete()
    if deleted:
        messages.success(request, f"{seller.shop_name} je uklonjena iz omiljenih.")
    elif seller.user_id == request.user.id:
        messages.error(request, "Ne možete dodati svoju prodavnicu u omiljene.")
    elif seller.status != "active":
        messages.error(request, "Ova prodavnica trenutno nije aktivna.")
    else:
        FavouriteSeller.objects.create(user=request.user, seller=seller)
        messages.success(request, f"{seller.shop_name} je dodata u omiljene.")
    return _redirect_back(request, fallback)


@login_required(login_url="login")
@require_POST
def wishlist_toggle(request, product_id):
    """Add the product to the user's wishlist, or remove it if already there."""
    product = get_object_or_404(Product, pk=product_id)
    fallback = "account-settings"

    deleted, _ = WishlistItem.objects.filter(
        user=request.user, product=product
    ).delete()
    if deleted:
        messages.success(request, "Artikal je uklonjen sa liste želja.")
    elif product.seller.user_id == request.user.id:
        messages.error(request, "Ne možete sačuvati svoj artikal.")
    elif product.status != "published" or product.is_deleted:
        messages.error(request, "Ovaj artikal više nije u ponudi.")
    else:
        WishlistItem.objects.create(user=request.user, product=product)
        messages.success(request, "Artikal je sačuvan na listi želja.")
    return _redirect_back(request, fallback)
