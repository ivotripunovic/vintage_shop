"""
Add and remove favourite sellers and wishlist items.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from products.models import Product
from sellers.models import Seller

from .models import FavouriteSeller, WishlistItem

# Buttons send the change they show, so a double-click or a stale page is
# harmless; get_or_create also copes with two adds racing each other
ACTIONS = ("add", "remove")


def _redirect_back(request):
    """Go back to the page the button was on, or to the account settings page."""
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("account-settings")


@login_required(login_url="login")
@require_POST
def favourite_seller_update(request, seller_id):
    """Add the seller to the user's favourites, or remove them."""
    action = request.POST.get("action")
    if action not in ACTIONS:
        return HttpResponseBadRequest("Unknown action.")
    seller = get_object_or_404(Seller, pk=seller_id)

    if action == "remove":
        FavouriteSeller.objects.filter(user=request.user, seller=seller).delete()
        messages.success(request, f"{seller.shop_name} je uklonjena iz omiljenih.")
    elif seller.user_id == request.user.id:
        messages.error(request, "Ne možete dodati svoju prodavnicu u omiljene.")
    elif not seller.is_active_shop:
        messages.error(request, "Ova prodavnica trenutno nije aktivna.")
    else:
        FavouriteSeller.objects.get_or_create(user=request.user, seller=seller)
        messages.success(request, f"{seller.shop_name} je dodata u omiljene.")
    return _redirect_back(request)


@login_required(login_url="login")
@require_POST
def wishlist_update(request, product_id):
    """Add the product to the user's wishlist, or remove it."""
    action = request.POST.get("action")
    if action not in ACTIONS:
        return HttpResponseBadRequest("Unknown action.")
    product = get_object_or_404(Product.objects.select_related("seller"), pk=product_id)

    if action == "remove":
        WishlistItem.objects.filter(user=request.user, product=product).delete()
        messages.success(request, "Artikal je uklonjen sa liste želja.")
    elif product.seller.user_id == request.user.id:
        messages.error(request, "Ne možete sačuvati svoj artikal.")
    elif not product.is_listed:
        messages.error(request, "Ovaj artikal više nije u ponudi.")
    else:
        WishlistItem.objects.get_or_create(user=request.user, product=product)
        messages.success(request, "Artikal je sačuvan na listi želja.")
    return _redirect_back(request)
