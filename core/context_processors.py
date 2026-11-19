from django.conf import settings

from products.models import ProductCategory


def site_settings(request):
    nav_categories = ProductCategory.objects.filter(parent=None).prefetch_related(
        "children"
    )
    return {
        "SITE_NAME": settings.SITE_NAME,
        "CURRENCY_SYMBOL": settings.CURRENCY_SYMBOL,
        "INSTAGRAM_URL": settings.INSTAGRAM_URL,
        "FACEBOOK_URL": settings.FACEBOOK_URL,
        "nav_categories": nav_categories,
        # Layout for error pages (templates/errors/_error.html). Visitors held
        # by the pre-launch gate on a path it lets through get the standalone
        # shell, so the unreleased site's navigation is not shown.
        "ERROR_PAGE_BASE": (
            "errors/_standalone.html"
            if getattr(request, "coming_soon_gated", False)
            else "base.html"
        ),
    }
