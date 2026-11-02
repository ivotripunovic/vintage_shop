"""
Base abstract models for the Vintage Shop project.
"""

from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base model that provides self-updating
    ``created_at`` and ``updated_at`` fields.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class NotDeletedManager(models.Manager):
    """Default manager: leaves soft-deleted rows out."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(TimeStampedModel):
    """
    Abstract base model that provides soft delete functionality.
    Records are marked as deleted but not removed from database.

    `objects` (and reverse relations such as seller.products) hide deleted
    rows; `all_objects` includes them. Foreign keys still load a deleted row
    (Django uses a plain base manager for that), so history keeps its links.
    Joins across a relation (products__status=...) are not filtered by the
    manager and need products__is_deleted=False.
    """

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = NotDeletedManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        """Soft delete the record."""
        from django.utils import timezone

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class WaitlistSubscriber(TimeStampedModel):
    """Email left on the coming-soon page for the launch mailing list."""

    email = models.EmailField(unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    # Set when the subscriber clicks the link in the confirmation email
    confirmed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    # Set when the launch announcement was sent, so it's never sent twice
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def is_confirmed(self):
        return self.confirmed_at is not None
