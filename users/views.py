"""
User views that allauth does not cover: account settings. Sign-up, login,
logout, verification, password reset and change are allauth's (#77).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import UserProfileForm


@login_required
@require_http_methods(["GET", "POST"])
def account_settings_view(request):
    """User account settings page; buyers also edit their picture and bio here."""
    # Sellers edit their shop image and description in seller settings instead
    profile_form = None
    if not request.user.is_seller:
        if request.method == "POST":
            profile_form = UserProfileForm(
                request.POST, request.FILES, instance=request.user
            )
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Vaš profil je sačuvan.")
                return redirect("account-settings")
        else:
            profile_form = UserProfileForm(instance=request.user)

    favourite_sellers = request.user.favourite_sellers.select_related("seller")
    wishlist_items = (
        request.user.wishlist_items.filter(product__is_deleted=False)
        .select_related("product__seller")
        .prefetch_related("product__images")
    )

    context = {
        "page_title": "Account Settings",
        "profile_form": profile_form,
        "email_verified": request.user.email_verified,  # one query
        "favourite_sellers": favourite_sellers,
        "wishlist_items": wishlist_items,
    }
    return render(request, "users/account_settings.html", context)
