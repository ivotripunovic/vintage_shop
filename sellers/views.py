"""
Views for seller onboarding, dashboard, and account management.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.decorators.http import require_http_methods

from orders.models import SELLABLE_STATUSES
from products.models import Product, ProductCondition
from ratings.models import Rating
from ratings.services import rating_summary

from .forms import (
    BankDetailsForm,
    SellerAccountSettingsForm,
    ShopSetupForm,
)
from .models import STORE_TIERS, Seller

STORE_TIERS_MESSAGE = "Naziv i stranica prodavnice dolaze uz pakete Održivo i Premijum."


def _safe_next(request):
    """The ``next`` parameter if it points to this site, else None."""
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return None


def _shop_or_setup(request):
    """(seller, None) for a seller, else (None, redirect to a first listing).

    A seller profile is opened quietly on the first listing
    (products.views._seller_for); pages that need one never make one up.
    """
    if request.user.is_seller:
        return request.user.seller_profile, None
    messages.info(request, "Dodajte svoj prvi oglas.")
    return None, redirect("product_create")


def seller_register_view(request):
    """
    "Start selling" links land here.

    Every account can sell (#89): visitors sign up and go on to their first
    listing, which opens their shop; signed-in users go there directly.
    """
    if not request.user.is_authenticated:
        query = urlencode({"next": reverse("product_create")})
        return redirect(f"{reverse('account_signup')}?{query}")
    if request.user.is_seller:
        return redirect("seller_dashboard")
    return redirect("product_create")


@login_required
@require_http_methods(["GET", "POST"])
def seller_shop_setup_view(request):
    """
    Set up the store: name, URL, description, location, image.

    Only the paid tiers come with a store (Seller.has_store); free sellers
    list under their own name and are sent to the dashboard.
    """
    seller, setup = _shop_or_setup(request)
    if setup:
        return setup
    if not seller.has_store:
        messages.info(request, STORE_TIERS_MESSAGE)
        return redirect("seller_dashboard")

    if request.method == "POST":
        form = ShopSetupForm(request.POST, request.FILES, instance=seller)
        if form.is_valid():
            form.save()
            messages.success(request, "Prodavnica je sačuvana.")
            return redirect(_safe_next(request) or "seller_bank_details")
    else:
        form = ShopSetupForm(instance=seller)

    return render(
        request,
        "sellers/shop_setup.html",
        {"form": form, "next": _safe_next(request)},
    )


@login_required
@require_http_methods(["GET", "POST"])
def seller_bank_details_view(request):
    """
    Seller bank details.
    Collects bank account information for payments.
    """
    seller, setup = _shop_or_setup(request)
    if setup:
        return setup

    if request.method == "POST":
        form = BankDetailsForm(request.POST, instance=seller)
        if form.is_valid():
            form.save()
            messages.success(
                request, "Bank details saved! Your seller account is ready."
            )
            return redirect("seller_dashboard")
    else:
        form = BankDetailsForm(instance=seller)

    return render(
        request, "sellers/bank_details.html", {"form": form, "seller": seller}
    )


@login_required
@require_http_methods(["GET"])
def seller_dashboard_view(request):
    """
    Seller dashboard showing overview and key metrics.
    """
    seller, setup = _shop_or_setup(request)
    if setup:
        return setup

    # Get seller statistics
    total_products = seller.products.count()
    published_products = seller.products.filter(status="published").count()
    draft_products = seller.products.filter(status="draft").count()

    # Get active subscription
    subscription = seller.active_subscription

    # Get recent products
    recent_products = seller.products.all()[:5]

    context = {
        "seller": seller,
        "total_products": total_products,
        "published_products": published_products,
        "draft_products": draft_products,
        "subscription": subscription,
        "recent_products": recent_products,
        "listing_limit": seller.monthly_listing_limit,
        "listings_left": seller.listings_left_this_month(),
    }

    return render(request, "sellers/dashboard.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def seller_settings_view(request):
    """
    Seller account settings page.
    Allows editing of shop details and email.
    """
    seller, setup = _shop_or_setup(request)
    if setup:
        return setup

    if request.method == "POST":
        form = SellerAccountSettingsForm(
            request.POST, request.FILES, instance=seller, user=request.user
        )
        if form.is_valid():
            seller = form.save()
            messages.success(request, "Account settings updated successfully.")
            return redirect("seller_settings")
    else:
        form = SellerAccountSettingsForm(instance=seller, user=request.user)

    # Get subscription info for display
    subscription = seller.active_subscription

    context = {
        "form": form,
        "seller": seller,
        "subscription": subscription,
    }

    return render(request, "sellers/settings.html", context)


@login_required
@require_http_methods(["GET"])
def seller_products_list_view(request):
    """
    List all products for the logged-in seller.
    """
    seller, setup = _shop_or_setup(request)
    if setup:
        return setup

    # Get filter parameters
    status_filter = request.GET.get("status")

    products = seller.products.annotate(wishlist_count=Count("wishlisted_by"))

    if status_filter and status_filter in [
        "draft",
        "published",
        "sold",
        "archived",
        "expired",
    ]:
        products = products.filter(status=status_filter)

    # Count by status
    status_counts = {
        "all": seller.products.count(),
        "published": seller.products.filter(status="published").count(),
        "draft": seller.products.filter(status="draft").count(),
        "sold": seller.products.filter(status="sold").count(),
        "archived": seller.products.filter(status="archived").count(),
        "expired": seller.products.filter(status="expired").count(),
    }

    context = {
        "products": products,
        "status_counts": status_counts,
        "current_status": status_filter or "all",
        "sellable_statuses": SELLABLE_STATUSES,
    }

    return render(request, "sellers/products_list.html", context)


@require_http_methods(["GET"])
def shops_browse_view(request):
    """
    Browse all active shops with published products (public view).
    """
    # Get search parameter
    search_query = request.GET.get("q", "")
    sort_by = request.GET.get("sort", "-created_at")

    # Get sellers with at least one published product
    sellers = (
        Seller.objects.filter(
            status="active",
            tier__in=STORE_TIERS,
            products__status="published",
            products__is_deleted=False,
        )
        .distinct()
        .annotate(
            published_count=Count(
                "products",
                filter=models.Q(
                    products__status="published", products__is_deleted=False
                ),
            )
        )
    )

    # Apply search
    if search_query:
        sellers = sellers.filter(
            Q(shop_name__icontains=search_query)
            | Q(shop_description__icontains=search_query)
            | Q(location__icontains=search_query)
        )

    # Apply sorting
    if sort_by == "name":
        sellers = sellers.order_by("shop_name")
    elif sort_by == "-products":
        sellers = sellers.order_by("-published_count")
    else:
        sellers = sellers.order_by("-created_at")

    # Pagination
    paginator = Paginator(sellers, 12)  # 12 shops per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "sellers": page_obj.object_list,
        "search_query": search_query,
        "sort_by": sort_by,
        "page_title": "Browse Shops",
    }

    return render(request, "sellers/browse.html", context)


@require_http_methods(["GET"])
def shop_detail_view(request, shop_slug):
    """
    View a specific shop with all its published products.
    """
    seller = get_object_or_404(
        Seller.objects.annotate(
            published_count=Count(
                "products",
                filter=models.Q(
                    products__status="published", products__is_deleted=False
                ),
            )
        ),
        shop_slug=shop_slug,
        status="active",
        tier__in=STORE_TIERS,
    )

    # Get published products for this shop
    products = seller.products.filter(status="published").order_by("-created_at")

    # Pagination
    paginator = Paginator(products, 12)  # 12 products per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    is_favourite = (
        request.user.is_authenticated
        and seller.favourited_by.filter(user=request.user).exists()
    )

    context = {
        "seller": seller,
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "page_title": seller.shop_name,
        "is_own_shop": seller.user_id == request.user.id,
        "is_favourite": is_favourite,
        "seller_rating": rating_summary(seller.user, Rating.BUYER_TO_SELLER),
        "recent_ratings": Rating.objects.visible()
        .filter(subject=seller.user, direction=Rating.BUYER_TO_SELLER)
        .select_related("sale")[:5],
    }

    return render(request, "sellers/shop_detail.html", context)
