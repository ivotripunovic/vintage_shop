"""
User views that allauth does not cover: account settings, the welcome page
after signing up, and becoming a seller. Sign-up, login, logout,
verification, password reset and change are allauth's (#77).
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


@login_required
def social_signup_complete_view(request):
    """Welcome page after signing up (email or social): shop or open a shop."""
    context = {
        "page_title": "Dobrodošli",
    }
    return render(request, "users/social_signup_complete.html", context)


@login_required
@require_http_methods(["POST"])
def social_become_seller_view(request):
    """Upgrade a social-registered user to seller and redirect to shop setup."""
    from sellers.models import Seller

    user = request.user
    if not user.is_seller:
        user.is_seller = True
        user.save(update_fields=["is_seller"])

        if not hasattr(user, "seller_profile"):
            base_slug = user.email.split("@")[0].replace(".", "-")
            seller = Seller.objects.create(
                user=user,
                shop_name=user.get_full_name() or base_slug,
                shop_slug=base_slug,
            )
            seller.create_initial_subscription()

    return redirect("seller_shop_setup")
