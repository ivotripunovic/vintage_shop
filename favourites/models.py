"""
Favourite sellers and wishlist items saved by users.
"""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class FavouriteSeller(TimeStampedModel):
    """A seller a user marked as favourite."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favourite_sellers",
    )
    seller = models.ForeignKey(
        "sellers.Seller",
        on_delete=models.CASCADE,
        related_name="favourited_by",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "seller"], name="unique_favourite_seller"
            )
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.seller}"


class WishlistItem(TimeStampedModel):
    """A product a user saved to their wishlist."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="wishlisted_by",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_wishlist_item"
            )
        ]

    def __str__(self):
        return f"{self.user} → {self.product}"
