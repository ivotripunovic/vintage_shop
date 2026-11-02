"""
Delete photos uploaded on listing forms that were never saved.

Uploads live as PhotoUpload rows until the listing is saved; a closed tab
leaves them behind. Anything older than --hours (default 24) goes, files
included. Safe to run as often as needed.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from products.models import PhotoUpload


class Command(BaseCommand):
    help = "Delete pending listing-form photo uploads older than --hours."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=options["hours"])
        count = 0
        for upload in PhotoUpload.objects.filter(created_at__lt=cutoff).iterator():
            # One row at a time. Files go with the row (products.signals),
            # but only if no listing took them over meanwhile: a seller
            # saving a day-old form while this runs keeps the photos.
            deleted, _ = PhotoUpload.objects.filter(pk=upload.pk).delete()
            count += bool(deleted)
        self.stdout.write(f"Deleted {count} unused upload(s).")
