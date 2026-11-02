"""Signal handlers for the products app."""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import ProductImage


@receiver(post_delete, sender=ProductImage)
def delete_photo_files(sender, instance, **kwargs):
    """Remove the photo and its thumbnail from storage once the row is gone."""
    files = [f for f in (instance.image, instance.thumbnail) if f]

    def delete():
        for file in files:
            file.storage.delete(file.name)

    # After commit, so a rolled-back delete keeps its files
    transaction.on_commit(delete)
