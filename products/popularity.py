"""
Product popularity: unique view counting and recent viewers.
"""

import re
import time

from django.core.cache import cache
from django.db.models import F

from .models import Product, ProductView

# How long a visit counts towards "viewed in the last N minutes"
RECENT_VIEWER_WINDOW = 15 * 60

BOT_UA_RE = re.compile(
    r"bot|crawl|spider|slurp|preview|headless|curl|wget|python-requests|httpx"
    r"|go-http-client|okhttp|facebookexternalhit|whatsapp|telegram",
    re.IGNORECASE,
)
PREFETCH_HEADERS = ("HTTP_SEC_PURPOSE", "HTTP_PURPOSE", "HTTP_X_MOZ")


def _recent_viewers_key(product_id):
    return f"product_recent_viewers:{product_id}"


def visitor_id(request):
    """Identify the visitor: the user if logged in, otherwise the session."""
    if request.user.is_authenticated:
        return f"u{request.user.pk}"
    if request.session.session_key is None:
        request.session.save()
    return f"s{request.session.session_key}"


def is_countable_request(request):
    """Check the request is a real page view: a GET from a browser, not a prefetch."""
    if request.method != "GET":
        return False
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    if not user_agent or BOT_UA_RE.search(user_agent):
        return False
    return not any(
        "prefetch" in request.META.get(header, "").lower()
        for header in PREFETCH_HEADERS
    )


def record_view(request, product):
    """
    Count a unique view of the product and mark the visitor as a recent viewer.
    The caller skips the product's owner. Bots and prefetches are ignored.
    Returns the visitor id, or None if ignored.
    """
    if not is_countable_request(request):
        return None

    user = request.user
    vid = visitor_id(request)
    if user.is_authenticated:
        lookup = {"user": user}
    else:
        lookup = {"user": None, "session_key": request.session.session_key}

    _, created = ProductView.objects.get_or_create(product=product, **lookup)
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
