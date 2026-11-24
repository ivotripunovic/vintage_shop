"""
Seller profiles and subscription models.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.text import slugify

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


# Days a seller has to pay the invoice for a paid tier
INVOICE_DUE_DAYS = 8


# Draft wording, pending confirmation by the legal side
TRADER_STATEMENT = (
    "Potvrđujem da sam trgovac u smislu Zakona o trgovini Republike Srbije."
)


# Used when a shop is opened without a name
DEFAULT_SHOP_NAME = "Prodavnica"

# Tiers that come with a store: a shop name, a public page and a place in the
# shops list. Garazna sellers just list, under their own name.
STORE_TIERS = frozenset({"odrzivo", "premijum"})

# Shown for a seller without a store whose user has no name
ANONYMOUS_SELLER_NAME = "Prodavac"

# Paths under /seller/ that a shop slug would shadow (sellers/urls.py)
RESERVED_SHOP_SLUGS = frozenset(
    {"register", "shop-setup", "bank-details", "dashboard", "settings", "products"}
)

# Serbian Latin letters that slugify would drop instead of transliterating
_SLUG_TRANSLITERATION = str.maketrans({"đ": "dj", "Đ": "Dj"})


def shop_slug_from_name(name):
    """A URL slug for a shop name; empty if the name has no usable letters."""
    slug = slugify((name or "").translate(_SLUG_TRANSLITERATION))
    max_length = Seller._meta.get_field("shop_slug").max_length
    return slug[:max_length].strip("-")


def is_shop_slug_free(slug, exclude_pk=None):
    """The slug is not reserved and no other shop uses it."""
    if slug in RESERVED_SHOP_SLUGS:
        return False
    taken = Seller.objects.filter(shop_slug=slug)
    if exclude_pk is not None:
        taken = taken.exclude(pk=exclude_pk)
    return not taken.exists()


def free_shop_slug(base, exclude_pk=None):
    """``base``, or ``base-2``, ``base-3``... whichever is free first.

    One query, however many are taken: every default-named shop starts
    from "prodavnica".
    """
    base = base or slugify(DEFAULT_SHOP_NAME)
    max_length = Seller._meta.get_field("shop_slug").max_length
    # Suffixed candidates may cut base short, so match on a shorter stem
    stem = base[: max_length - 8].rstrip("-")
    taken = Seller.objects.filter(shop_slug__startswith=stem)
    if exclude_pk is not None:
        taken = taken.exclude(pk=exclude_pk)
    taken = set(taken.values_list("shop_slug", flat=True)) | RESERVED_SHOP_SLUGS
    candidate, n = base, 1
    while candidate in taken:
        n += 1
        suffix = f"-{n}"
        candidate = base[: max_length - len(suffix)].rstrip("-") + suffix
    return candidate


class Seller(TimeStampedModel):
    """A user's shop. A user with a Seller row is a seller (User.is_seller)."""

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
    def has_store(self):
        """The seller's tier comes with a store (STORE_TIERS)."""
        return self.tier in STORE_TIERS

    @property
    def display_name(self):
        """What buyers see: the shop name, or the user's name without a store."""
        if self.has_store:
            return self.shop_name
        return self.user.get_full_name() or ANONYMOUS_SELLER_NAME

    @property
    def needs_store_setup(self):
        """Moved up to a store tier but the store has no name yet."""
        return self.has_store and self.shop_name == DEFAULT_SHOP_NAME

    @classmethod
    def open_for(cls, user, shop_name=None, shop_slug=None, **fields):
        """Open ``user``'s shop with its free starting subscription.

        The only way a shop is created. Idempotent: a user who already has a
        shop gets it back unchanged. The slug comes from ``shop_slug`` or the
        shop name, with a numeric suffix if taken, never from the email.
        """
        existing = cls.objects.filter(user=user).first()
        if existing is not None:
            existing.user = user  # caches user.seller_profile
            return existing
        name = (shop_name or "").strip() or DEFAULT_SHOP_NAME
        base = shop_slug_from_name(shop_slug or name)
        attempts = 5
        for attempt in range(attempts):
            slug = free_shop_slug(base)
            try:
                with transaction.atomic():
                    seller = cls(user=user, shop_name=name, shop_slug=slug, **fields)
                    seller.save()
                    seller.create_initial_subscription()
                return seller
            except IntegrityError:
                # Building the Seller cached it on user.seller_profile
                user._state.fields_cache.pop("seller_profile", None)
                existing = cls.objects.filter(user=user).first()
                if existing is not None:
                    # A concurrent request opened this user's shop first
                    existing.user = user
                    return existing
                slug_lost = cls.objects.filter(shop_slug=slug).exists()
                if not slug_lost or attempt == attempts - 1:
                    raise

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
        return self.products.model.all_objects.filter(
            seller=self, listed_at__gte=month_start
        ).count()

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

    @transaction.atomic
    def change_tier(self, new_tier):
        """Move the seller to a tier, restarting the subscription at its price.

        Returns the new pending invoice, or None for a free or unchanged tier.
        """
        if new_tier == self.tier:
            return None
        self.tier = new_tier
        self.save()

        for subscription in self.subscriptions.filter(status="active"):
            subscription.cancel()
        subscription = self.create_initial_subscription()

        # Pending invoices were for the old tier
        for invoice in self.invoices.filter(status="pending"):
            invoice.cancel()

        if not subscription.amount:
            return None
        return self.invoices.create(
            amount=subscription.amount,
            due_date=subscription.start_date + timedelta(days=INVOICE_DUE_DAYS),
            period_start=subscription.start_date,
            period_end=subscription.renewal_date,
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
