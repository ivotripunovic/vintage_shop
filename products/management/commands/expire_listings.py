"""
Take down published products whose listing period has ended.

Only tiers with a listing expiry (Garazna by default) get an expires_at, so
paid sellers' products are never touched. Safe to run as often as needed.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from products.models import Product


class Command(BaseCommand):
    help = "Mark published products past their expiry date as expired."

    def handle(self, *args, **options):
        current_time = timezone.now()
        count = Product.objects.filter(
            status="published", expires_at__lte=current_time
        ).update(status="expired", updated_at=current_time)
        self.stdout.write(f"Expired {count} listing(s).")
