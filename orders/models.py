"""
Sales: products a seller marked as sold to a buyer from chat.
"""

from django.db import models

from core.models import TimeStampedModel

# Products a seller can record a sale for: live, or live until recently
SELLABLE_STATUSES = ("published", "expired")


def can_be_sold(product):
    """Check the product is live (or recently expired) and has stock left."""
    return (
        product.status in SELLABLE_STATUSES
        and product.stock > 0
        and not product.is_deleted
    )


class Sale(TimeStampedModel):
    """A product the seller marked as sold to a buyer they talked to in chat."""

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        related_name="sales",
    )
    # Kept so the sale still reads well if the product is deleted
    product_title = models.CharField(max_length=255)
    seller = models.ForeignKey(
        "sellers.Seller",
        on_delete=models.CASCADE,
        related_name="sales",
    )
    buyer = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="purchases",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "buyer"], name="unique_sale_product_buyer"
            )
        ]

    def __str__(self):
        return f"{self.product_title} → {self.buyer.email}"
