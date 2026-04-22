from django.conf import settings
from products.models import ProductCategory


def site_settings(request):
    nav_categories = ProductCategory.objects.filter(
        parent=None
    ).prefetch_related("children")
    return {
        "SITE_NAME": settings.SITE_NAME,
        "nav_categories": nav_categories,
    }
