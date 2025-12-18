"""
Management command to seed product categories and conditions.
Usage: python manage.py seed_categories_conditions
"""

from django.core.management.base import BaseCommand
from products.models import ProductCategory, ProductCondition


class Command(BaseCommand):
    help = 'Seed product categories and conditions'

    def handle(self, *args, **options):
        # Define categories
        categories_data = [
            {'name': 'Electronics', 'slug': 'electronics', 'description': 'Phones, laptops, tablets, and other electronics'},
            {'name': 'Clothing', 'slug': 'clothing', 'description': 'Men\'s, women\'s, and kids clothing'},
            {'name': 'Furniture', 'slug': 'furniture', 'description': 'Chairs, tables, cabinets, and home furniture'},
            {'name': 'Books', 'slug': 'books', 'description': 'Novels, textbooks, and other books'},
            {'name': 'Sporting Goods', 'slug': 'sporting-goods', 'description': 'Fitness equipment, sports gear, and outdoor items'},
            {'name': 'Home & Garden', 'slug': 'home-garden', 'description': 'Kitchenware, home decor, and garden supplies'},
            {'name': 'Beauty & Personal Care', 'slug': 'beauty-personal-care', 'description': 'Skincare, makeup, and personal care products'},
            {'name': 'Toys & Games', 'slug': 'toys-games', 'description': 'Toys, board games, and collectibles'},
            {'name': 'Jewelry & Watches', 'slug': 'jewelry-watches', 'description': 'Necklaces, rings, bracelets, and watches'},
            {'name': 'Art & Collectibles', 'slug': 'art-collectibles', 'description': 'Art pieces, antiques, and collectible items'},
        ]

        # Define conditions
        conditions_data = [
            {'name': 'New', 'description': 'Brand new, never used', 'order': 1},
            {'name': 'Like New', 'description': 'Appears unused, barely worn', 'order': 2},
            {'name': 'Good', 'description': 'Minor wear, fully functional', 'order': 3},
            {'name': 'Fair', 'description': 'Heavy wear, some damage, but works', 'order': 4},
        ]

        # Add categories
        created_categories = 0
        for cat_data in categories_data:
            category, created = ProductCategory.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                }
            )
            if created:
                created_categories += 1
                self.stdout.write(self.style.SUCCESS(f'Created category: {category.name}'))
            else:
                self.stdout.write(f'Category already exists: {category.name}')

        # Add conditions
        created_conditions = 0
        for cond_data in conditions_data:
            condition, created = ProductCondition.objects.get_or_create(
                name=cond_data['name'],
                defaults={
                    'description': cond_data['description'],
                    'order': cond_data['order'],
                }
            )
            if created:
                created_conditions += 1
                self.stdout.write(self.style.SUCCESS(f'Created condition: {condition.name}'))
            else:
                self.stdout.write(f'Condition already exists: {condition.name}')

        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n✓ Completed!'))
        self.stdout.write(f'Created {created_categories} categories')
        self.stdout.write(f'Created {created_conditions} conditions')
