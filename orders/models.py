"""
Orders and order items models.
"""

from django.db import models
from django.core.validators import MinValueValidator
from core.models import TimeStampedModel


class Order(TimeStampedModel):
    """Buyer orders."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    )

    buyer = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Shipping information
    shipping_name = models.CharField(max_length=255)
    shipping_address = models.TextField()
    shipping_phone = models.CharField(max_length=20, blank=True)

    # Tracking
    tracking_number = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["buyer", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return f"Order #{self.pk} - {self.buyer.email}"

    @property
    def item_count(self):
        """Total number of items in order."""
        return self.items.aggregate(
            total=models.Sum("quantity")
        )["total"] or 0

    def calculate_total(self):
        """Recalculate order total from items."""
        total = self.items.aggregate(
            total=models.Sum(models.F("quantity") * models.F("price_at_purchase"))
        )["total"] or 0
        self.total_price = total
        self.save()

    def mark_shipped(self, tracking_number=""):
        """Mark order as shipped."""
        self.status = "shipped"
        if tracking_number:
            self.tracking_number = tracking_number
        self.save()

    def mark_delivered(self):
        """Mark order as delivered."""
        self.status = "delivered"
        self.save()


class OrderItem(TimeStampedModel):
    """Individual items in an order."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
    )
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        return f"{self.order} - {self.product.title}"

    @property
    def subtotal(self):
        """Subtotal for this item."""
        return self.quantity * self.price_at_purchase
