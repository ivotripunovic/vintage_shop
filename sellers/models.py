"""
Seller profiles and subscription models.
"""

from django.db import models
from django.utils import timezone
from core.models import TimeStampedModel


class Seller(TimeStampedModel):
    """Seller profile linked to User."""

    STATUS_CHOICES = (
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("banned", "Banned"),
    )

    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="seller_profile",
    )
    shop_name = models.CharField(max_length=255)
    shop_slug = models.SlugField(unique=True)
    shop_description = models.TextField(blank=True)
    shop_image = models.ImageField(upload_to="shop_images/", blank=True, null=True)
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active"
    )
    is_verified = models.BooleanField(default=False)

    # Bank details (stored securely - consider encryption in production)
    bank_account_holder = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=255)
    bank_account_number = models.CharField(max_length=50)  # IBAN or account number

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Seller"
        verbose_name_plural = "Sellers"

    def __str__(self):
        return self.shop_name

    @property
    def is_suspended(self):
        """Check if seller is currently suspended."""
        return self.status == "suspended"

    @property
    def active_subscription(self):
        """Get the active subscription for this seller."""
        return self.subscriptions.filter(status="active").first()

    def suspend(self):
        """Suspend the seller's shop."""
        self.status = "suspended"
        self.save()

    def activate(self):
        """Reactivate the seller's shop."""
        self.status = "active"
        self.save()


class SellerSubscription(TimeStampedModel):
    """Monthly subscription for sellers."""

    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("cancelled", "Cancelled"),
    )

    seller = models.ForeignKey(
        Seller,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan_type = models.CharField(max_length=50, default="monthly")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=9.99)
    renewal_date = models.DateField()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Seller Subscription"
        verbose_name_plural = "Seller Subscriptions"

    def __str__(self):
        return f"{self.seller.shop_name} - {self.plan_type} (${self.amount})"

    @property
    def is_active(self):
        """Check if subscription is currently active."""
        return self.status == "active" and self.end_date is None

    @property
    def days_until_renewal(self):
        """Calculate days until subscription renewal."""
        from datetime import datetime

        if self.renewal_date:
            return (self.renewal_date - datetime.now().date()).days
        return None

    def cancel(self):
        """Cancel the subscription."""
        self.status = "cancelled"
        self.end_date = timezone.now().date()
        self.save()
