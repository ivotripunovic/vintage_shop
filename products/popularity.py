"""
Product popularity: unique view counting and recent viewers.
"""

import re
import time

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import F

from .models import Product, ProductView

# How long a visit counts towards "viewed in the last N minutes"
RECENT_VIEWER_WINDOW = 15 * 60

BOT_UA_RE = re.compile(r"bot|crawl|spider|slurp|preview", re.IGNORECASE)


def _recent_viewers_key(product_id):
    return f"product_recent_viewers:{product_id}"


def visitor_id(request):
    """Identify the visitor: the user if logged in, otherwise the session."""
    if request.user.is_authenticated:
        return f"u{request.user.pk}"
    if request.session.session_key is None:
        request.session.save()
    return f"s{request.session.session_key}"


def record_view(request, product):
    """
    Count a unique view of the product and mark the visitor as a recent viewer.
    Owners and bots are ignored. Returns the visitor id, or None if ignored.
    """
    user = request.user
    if user.is_authenticated and product.seller.user_id == user.pk:
        return None
    if BOT_UA_RE.search(request.META.get("HTTP_USER_AGENT", "")):
        return None

    vid = visitor_id(request)
    if user.is_authenticated:
        lookup = {"user": user}
    else:
        lookup = {"user": None, "session_key": request.session.session_key}

    try:
        with transaction.atomic():
            _, created = ProductView.objects.get_or_create(product=product, **lookup)
    except IntegrityError:
        # A parallel request created the same view first
        created = False
    if created:
        Product.objects.filter(pk=product.pk).update(view_count=F("view_count") + 1)
        product.view_count += 1

    touch_recent_viewer(product.pk, vid)
    return vid


def touch_recent_viewer(product_id, vid):
    """Mark the visitor as having viewed the product just now."""
    key = _recent_viewers_key(product_id)
    now = time.time()
    viewers = {
        v: seen
        for v, seen in cache.get(key, {}).items()
        if now - seen < RECENT_VIEWER_WINDOW
    }
    viewers[vid] = now
    cache.set(key, viewers, RECENT_VIEWER_WINDOW)


def recent_viewer_count(product_id, exclude=None):
    """Count visitors in the recent window, not counting `exclude`."""
    now = time.time()
    return sum(
        1
        for v, seen in cache.get(_recent_viewers_key(product_id), {}).items()
        if v != exclude and now - seen < RECENT_VIEWER_WINDOW
    )
