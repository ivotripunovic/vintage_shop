"""
Who can rate which sale, and rating summaries for profiles.
"""

from django.db.models import Avg, Count, Q
from django.utils import timezone

from orders.models import Sale

from .models import RATING_WINDOW, Rating


def rating_direction(sale, user):
    """The direction `user` rates in for this sale, or None if not a party."""
    if user.pk == sale.buyer_id:
        return Rating.BUYER_TO_SELLER
    if user.pk == sale.seller.user_id:
        return Rating.SELLER_TO_BUYER
    return None


def can_rate(sale, user):
    """Check the user is a party, hasn't rated yet, and the window is open."""
    direction = rating_direction(sale, user)
    return (
        direction is not None
        and sale.created_at > timezone.now() - RATING_WINDOW
        and not sale.ratings.filter(direction=direction).exists()
    )


def pending_sales(user):
    """Sales the user can still rate, newest first."""
    cutoff = timezone.now() - RATING_WINDOW
    return (
        Sale.objects.filter(created_at__gt=cutoff)
        .filter(
            Q(buyer=user) & ~Q(ratings__direction=Rating.BUYER_TO_SELLER)
            | Q(seller__user=user) & ~Q(ratings__direction=Rating.SELLER_TO_BUYER)
        )
        .select_related("seller", "buyer")
        .distinct()
    )


def rating_summary(user, direction):
    """Average score, count and aspect averages of a user's visible ratings."""
    aspects = Rating.ASPECTS[direction]
    ratings = Rating.objects.visible().filter(subject=user, direction=direction)
    totals = ratings.aggregate(
        average=Avg("score"),
        count=Count("id"),
        **{field: Avg(field) for field, _ in aspects},
    )
    return {
        "average": totals["average"],
        "count": totals["count"],
        "aspects": [
            (label, totals[field])
            for field, label in aspects
            if totals[field] is not None
        ],
    }


def buyer_averages(users):
    """{user id: (average, count)} of the buyers' visible ratings from sellers."""
    rows = (
        Rating.objects.visible()
        .filter(subject__in=users, direction=Rating.SELLER_TO_BUYER)
        .values("subject")
        .annotate(average=Avg("score"), count=Count("id"))
    )
    return {row["subject"]: (row["average"], row["count"]) for row in rows}
