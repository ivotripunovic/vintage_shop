from django.conf import settings
from products.models import ProductCategory


def site_settings(request):
    nav_categories = ProductCategory.objects.filter(
        parent=None
    ).prefetch_related("children")
    return {
        "SITE_NAME": settings.SITE_NAME,
        "CURRENCY_SYMBOL": settings.CURRENCY_SYMBOL,
        "INSTAGRAM_URL": settings.INSTAGRAM_URL,
        "FACEBOOK_URL": settings.FACEBOOK_URL,
        "nav_categories": nav_categories,
    }
