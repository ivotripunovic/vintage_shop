"""
Django management command to update seller names with funky real names.
Run with: python manage.py update_seller_names
"""

from django.core.management.base import BaseCommand
from sellers.models import Seller


FUNKY_SELLER_NAMES = [
    "Barnaby's Bygone Bazaar",
    "Margot's Mysterious Attic",
    "Cornelius & Co Vintage",
    "Fiona's Forgotten Finds",
    "Theodor's Time Capsule",
    "Beatrice's Bounty",
    "Percival's Peculiar Things",
    "Gertrude's Golden Goodies",
    "Archibald's Antique Emporium",
    "Penelope's Past Perfect",
    "Mortimer's Memory Lane",
    "Isabella's Inherited Items",
    "Ezekiel's Estate Exchange",
    "Rosemary's Retro Realm",
    "Winston's Wonderland Warehouse",
]


class Command(BaseCommand):
    help = "Update seller names with funky, unique real names"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Updating seller names..."))
        
        sellers = Seller.objects.all().order_by('id')
        total = sellers.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING("No sellers found."))
            return
        
        self.stdout.write(f"Found {total} sellers")
        
        updated = 0
        for idx, seller in enumerate(sellers):
            if idx < len(FUNKY_SELLER_NAMES):
                new_name = FUNKY_SELLER_NAMES[idx]
                old_name = seller.shop_name
                seller.shop_name = new_name
                seller.save()
                self.stdout.write(f"   {old_name} → {new_name}")
                updated += 1
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Updated {updated} seller names"))
