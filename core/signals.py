from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from products.models import ProductCategory

# Fragment names of the {% cache %} blocks in templates/base.html
NAV_FRAGMENTS = ["nav_desktop", "nav_mobile", "nav_subcategories"]


@receiver([post_save, post_delete], sender=ProductCategory)
def clear_nav_cache(sender, **kwargs):
    """Rebuild the category navigation as soon as a category changes."""
    cache.delete_many([make_template_fragment_key(name) for name in NAV_FRAGMENTS])
