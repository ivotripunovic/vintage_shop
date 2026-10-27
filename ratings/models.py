"""
Ratings buyers and sellers give each other after a sale.
"""

from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel

# Both sides can rate for this long after the sale; ratings stay hidden until
# both have rated or the window closes, so nobody rates in reply to the other
RATING_WINDOW = timedelta(days=14)

SCORE_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]


class RatingQuerySet(models.QuerySet):
    def visible(self):
        """Ratings that are released and not hidden by staff."""
        cutoff = timezone.now() - RATING_WINDOW
        return self.filter(is_hidden=False).filter(
            models.Q(released_at__isnull=False) | models.Q(sale__created_at__lte=cutoff)
        )


class Rating(TimeStampedModel):
    """One side's rating of the other for a sale."""

    BUYER_TO_SELLER = "buyer_to_seller"
    SELLER_TO_BUYER = "seller_to_buyer"
    DIRECTION_CHOICES = (
        (BUYER_TO_SELLER, "Kupac ocenjuje prodavca"),
        (SELLER_TO_BUYER, "Prodavac ocenjuje kupca"),
    )
    # Optional aspect scores asked for in each direction, with their labels
    ASPECTS = {
        BUYER_TO_SELLER: (
            ("accuracy", "Artikal kao u opisu"),
            ("communication", "Komunikacija"),
            ("handover", "Isporuka / predaja"),
        ),
        SELLER_TO_BUYER: (
            ("payment", "Plaćanje"),
            ("communication", "Komunikacija"),
            ("reliability", "Pouzdanost"),
        ),
    }

    sale = models.ForeignKey(
        "orders.Sale",
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings_given",
    )
    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings_received",
    )
    score = models.PositiveSmallIntegerField(validators=SCORE_VALIDATORS)
    accuracy = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=SCORE_VALIDATORS
    )
    communication = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=SCORE_VALIDATORS
    )
    handover = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=SCORE_VALIDATORS
    )
    payment = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=SCORE_VALIDATORS
    )
    reliability = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=SCORE_VALIDATORS
    )
    text = models.TextField(max_length=1000)
    # Set when the second side rates; until then, the window decides
    released_at = models.DateTimeField(null=True, blank=True)
    is_hidden = models.BooleanField(default=False, db_index=True)
    reply = models.TextField(max_length=500, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    objects = RatingQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["sale", "direction"], name="unique_rating_per_side"
            )
        ]

    def __str__(self):
        return f"{self.author} → {self.subject}: {self.score}"

    @property
    def is_released(self):
        return (
            self.released_at is not None
            or self.sale.created_at <= timezone.now() - RATING_WINDOW
        )

    @property
    def aspect_scores(self):
        """(label, score) for the aspects the author filled in."""
        return [
            (label, getattr(self, field))
            for field, label in self.ASPECTS[self.direction]
            if getattr(self, field) is not None
        ]


class RatingReport(TimeStampedModel):
    """The rated person asks staff to look at a rating."""

    rating = models.ForeignKey(
        Rating,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rating_reports",
    )
    reason = models.TextField(max_length=500)
    is_resolved = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["rating", "reporter"], name="unique_rating_report"
            )
        ]

    def __str__(self):
        return f"Prijava: {self.rating}"
