"""
Delete photos uploaded on listing forms that were never saved.

Uploads live as PhotoUpload rows until the listing is saved; a closed tab
leaves them behind. Anything older than --hours (default 24) goes, files
included. Safe to run as often as needed.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
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
            with transaction.atomic():
                upload.delete_files()  # runs once the row delete commits
                upload.delete()
            count += 1
        self.stdout.write(f"Deleted {count} unused upload(s).")
