"""
Core views for Vintage Shop.
"""

from django.shortcuts import render

from products.models import Product, ProductCategory

HOME_SECTION_SIZE = 6


def home_view(request):
    """Home page view."""
    published = (
        Product.objects.filter(status="published")
        .select_related("category")
        .prefetch_related("images")
        .order_by("-listed_at")
    )

    # Products picked by admins
    picked_products = list(published.filter(is_picked=True)[:HOME_SECTION_SIZE])

    # Newest products from Premijum sellers, without the ones already shown above
    premijum_products = published.filter(seller__tier="premijum").exclude(
        pk__in=[product.pk for product in picked_products]
    )[:HOME_SECTION_SIZE]

    # Get top-level categories with their subcategories
    categories = ProductCategory.objects.filter(parent=None).prefetch_related(
        "children"
    )

    context = {
        "page_title": "Home",
        "picked_products": picked_products,
        "premijum_products": premijum_products,
        "categories": categories,
    }
    return render(request, "core/home.html", context)
