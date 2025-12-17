"""
Billing, invoicing, and payment models.
"""

from django.db import models
from django.utils import timezone
from core.models import TimeStampedModel


class BillingPlan(models.Model):
    """
    Flexible billing plan configuration.
    Allows switching between subscription, commission, hybrid, etc.
    """

    PLAN_TYPE_CHOICES = (
        ("subscription", "Monthly Subscription"),
        ("commission", "Per-Transaction Commission"),
        ("hybrid", "Subscription + Commission"),
        ("per_listing", "Per Listing Fee"),
        ("freemium", "Freemium"),
    )

    name = models.CharField(max_length=255)
    plan_type = models.CharField(max_length=50, choices=PLAN_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    
    # Flexible configuration stored as JSON
    config = models.JSONField(
        default=dict,
        help_text="Plan-specific configuration (e.g., amount, percentage, limits)",
    )

    class Meta:
        verbose_name = "Billing Plan"
        verbose_name_plural = "Billing Plans"

    def __str__(self):
        return f"{self.name} ({self.plan_type})"


class Invoice(TimeStampedModel):
    """Monthly invoices for seller subscriptions."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    )

    seller = models.ForeignKey(
        "sellers.Seller",
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    billing_plan = models.ForeignKey(
        BillingPlan,
        on_delete=models.SET_NULL,
        null=True,
        related_name="invoices",
    )

    # Invoice metadata
    period_start = models.DateField()
    period_end = models.DateField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["seller", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"

    def __str__(self):
        return f"{self.invoice_number} - {self.seller.shop_name}"

    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        return (
            self.status == "pending"
            and timezone.now().date() > self.due_date
        )

    @property
    def days_until_due(self):
        """Calculate days until due date."""
        delta = self.due_date - timezone.now().date()
        return delta.days

    @property
    def is_verified(self):
        """Check if invoice is verified/paid."""
        return self.status == "verified"

    def mark_verified(self):
        """Mark invoice as verified/paid."""
        self.status = "verified"
        self.save()
        # Reactivate seller if suspended due to overdue payment
        if self.seller.is_suspended:
            self.seller.activate()

    def mark_overdue(self):
        """Mark invoice as overdue."""
        if self.status == "pending":
            self.status = "overdue"
            self.save()
            # Suspend seller if payment overdue
            if not self.seller.is_suspended:
                self.seller.suspend()


class Payment(TimeStampedModel):
    """Payment records for invoices (manual verification)."""

    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payment",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_payments",
    )
    bank_reference = models.CharField(
        max_length=100, blank=True, help_text="Bank transaction reference"
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"Payment for {self.invoice.invoice_number}"

    def verify(self, verified_by, notes=""):
        """Mark payment as verified."""
        self.verified_at = timezone.now()
        self.verified_by = verified_by
        self.notes = notes
        self.save()
        self.invoice.mark_verified()
