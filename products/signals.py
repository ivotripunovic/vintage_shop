"""Signal handlers for the products app."""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import PhotoUpload, ProductImage, delete_unreferenced_files


@receiver(post_delete, sender=ProductImage)
@receiver(post_delete, sender=PhotoUpload)
def delete_photo_files(sender, instance, **kwargs):
    """
    Remove the photo and its thumbnail once the row is gone, unless another
    row now uses them (a pending upload attached to a listing keeps its
    files). Covers cascades too, such as a deleted seller.
    """
    delete_unreferenced_files(
        instance.image.storage, [instance.image.name, instance.thumbnail.name]
    )
