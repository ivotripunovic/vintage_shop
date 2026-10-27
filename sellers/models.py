"""
Seller profiles and subscription models.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel

TIER_CHOICES = (
    ("premijum", "Premijum"),
    ("odrzivo", "Održivo"),
    ("garazna", "Garažna"),
)

# Fallback when a tier has no SellerTier row; admins edit the real values.
# None means unlimited listings, or listings that never expire.
DEFAULT_TIER_SETTINGS = {
    "premijum": {
        "monthly_listing_limit": None,
        "monthly_price": Decimal("9000"),
        "listing_expiry_days": None,
    },
    "odrzivo": {
        "monthly_listing_limit": 50,
        "monthly_price": Decimal("6500"),
        "listing_expiry_days": None,
    },
    "garazna": {
        "monthly_listing_limit": 10,
        "monthly_price": Decimal("0"),
        "listing_expiry_days": 30,
    },
}


# Draft wording, pending confirmation by the legal side
TRADER_STATEMENT = (
    "Potvrđujem da sam trgovac u smislu Zakona o trgovini Republike Srbije."
)


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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    is_verified = models.BooleanField(default=False)
    # Set by admins only; decides the monthly listing limit and price
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default="garazna")
    # When the seller confirmed TRADER_STATEMENT; None means not confirmed
    trader_confirmed_at = models.DateTimeField(null=True, blank=True)
    # The exact statement text the seller agreed to, kept if the wording changes
    trader_statement = models.TextField(blank=True)

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
    def is_active_shop(self):
        """Check if the shop is open to buyers."""
        return self.status == "active"

    @property
    @admin.display(boolean=True, description="Trader", ordering="trader_confirmed_at")
    def is_trader(self):
        """Check if the seller has confirmed they are a trader."""
        return self.trader_confirmed_at is not None

    @property
    def trader_statement_outdated(self):
        """Check if the seller confirmed an earlier wording of the statement."""
        return self.is_trader and self.trader_statement != TRADER_STATEMENT

    def confirm_trader(self):
        """Record that the seller agreed to the current trader statement."""
        self.trader_confirmed_at = timezone.now()
        self.trader_statement = TRADER_STATEMENT

    def clear_trader(self):
        """Remove the seller's trader confirmation."""
        self.trader_confirmed_at = None
        self.trader_statement = ""

    @property
    def active_subscription(self):
        """Get the active subscription for this seller."""
        return self.subscriptions.filter(status="active").first()

    @property
    def tier_settings(self):
        """Listing limit and price for this seller's tier."""
        tier = SellerTier.objects.filter(tier=self.tier).first()
        if tier is None:
            return DEFAULT_TIER_SETTINGS[self.tier]
        return {
            "monthly_listing_limit": tier.monthly_listing_limit,
            "monthly_price": tier.monthly_price,
            "listing_expiry_days": tier.listing_expiry_days,
        }

    @property
    def monthly_listing_limit(self):
        """New listings allowed per month; None means unlimited."""
        return self.tier_settings["monthly_listing_limit"]

    def listings_used_this_month(self):
        """Count listing periods started since the start of this month."""
        month_start = timezone.localtime().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        # Soft-deleted products still count, so deleting doesn't free a slot
        return self.products.filter(listed_at__gte=month_start).count()

    def listings_left_this_month(self):
        """Remaining new listings this month; None means unlimited."""
        limit = self.monthly_listing_limit
        if limit is None:
            return None
        return max(limit - self.listings_used_this_month(), 0)

    def can_publish(self, product):
        """Check if publishing the product fits the monthly listing limit."""
        # Republishing within the current listing period doesn't use a slot
        if not product.needs_new_listing_period:
            return True
        left = self.listings_left_this_month()
        return left is None or left > 0

    def listing_limit_message(self):
        """Message shown when the monthly listing limit is reached."""
        return (
            f"Dostigli ste mesečni limit od {self.monthly_listing_limit} "
            f"novih oglasa za paket {self.get_tier_display()}."
        )

    def create_initial_subscription(self):
        """Start the seller's monthly subscription at their tier's price."""
        start_date = timezone.now().date()
        return self.subscriptions.create(
            plan_type="monthly",
            start_date=start_date,
            renewal_date=start_date + timedelta(days=30),
            status="active",
            amount=self.tier_settings["monthly_price"],
        )

    def suspend(self):
        """Suspend the seller's shop."""
        self.status = "suspended"
        self.save()

    def activate(self):
        """Reactivate the seller's shop."""
        self.status = "active"
        self.save()


class SellerTier(TimeStampedModel):
    """Admin-editable listing limit and price for a seller tier."""

    tier = models.CharField(max_length=20, choices=TIER_CHOICES, unique=True)
    monthly_listing_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="New listings a seller may publish per month. "
        "Leave empty for unlimited.",
    )
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Monthly price in RSD.",
    )
    listing_expiry_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days a listing stays up before the seller must re-enter it. "
        "Leave empty to never expire.",
    )

    class Meta:
        ordering = ["tier"]
        verbose_name = "Seller Tier"
        verbose_name_plural = "Seller Tiers"

    def __str__(self):
        return self.get_tier_display()


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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
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
