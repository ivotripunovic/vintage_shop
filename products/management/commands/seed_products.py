"""
Django management command to seed products for presentation.
Run with: python manage.py seed_products
"""

import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta

from users.models import User
from sellers.models import Seller, SellerSubscription
from products.models import Product, ProductCategory, ProductCondition


SHOP_NAMES = [
    "Vintage Treasures Co", "Retro Revival Shop", "Classics & More",
    "Timeless Collectibles", "Nostalgia Lane", "Estate Find Emporium",
    "Antique Alley", "Retro Rents", "Vintage Vault", "Secondhand Stories",
    "Time Warp Collectibles", "Heirloom House", "Bygone Boutique",
    "Vintage & Co", "Old School Market"
]

PRODUCT_TEMPLATES = {
    "Clothing": [
        {"title": "Vintage Leather Jacket", "description": "Classic brown leather jacket from the 1980s, excellent condition"},
        {"title": "Retro Denim Jacket", "description": "Blue denim jacket with original tags, perfect vintage piece"},
        {"title": "Wool Sweater", "description": "Hand-knitted wool sweater in neutral tones"},
        {"title": "Floral Dress", "description": "1950s-style floral print cotton dress"},
        {"title": "Silk Blouse", "description": "Vintage silk blouse with pearl buttons"},
        {"title": "High-Waisted Jeans", "description": "Classic high-waisted denim from the golden era"},
        {"title": "Cardigan Sweater", "description": "Soft cardigan from the 1970s era"},
        {"title": "Polo Shirt", "description": "Vintage polo shirt with logo embroidery"},
        {"title": "Tweed Jacket", "description": "Professional tweed jacket, perfect for offices"},
        {"title": "Corduroy Pants", "description": "Brown corduroy pants, retro style"},
    ],
    "Furniture": [
        {"title": "Mid-Century Chair", "description": "Wooden chair with fabric seat, classic design"},
        {"title": "Vintage Coffee Table", "description": "Teak wood coffee table from the 1960s"},
        {"title": "Bookshelf Unit", "description": "Wooden bookshelf with multiple shelves"},
        {"title": "Desk Lamp", "description": "Brass desk lamp with original shade"},
        {"title": "Side Table", "description": "Small wooden side table for living room"},
        {"title": "Dining Chair Set", "description": "Set of 4 vintage dining chairs"},
        {"title": "Bar Stool", "description": "Chrome and vinyl bar stool, retro design"},
        {"title": "Cabinet Console", "description": "Wooden storage cabinet with doors"},
        {"title": "Plant Stand", "description": "Wooden plant stand for indoor plants"},
        {"title": "Wall Shelf", "description": "Wooden floating shelf with brackets"},
    ],
    "Collectibles": [
        {"title": "Vintage Vinyl Record", "description": "Original pressing from the 1970s, near mint condition"},
        {"title": "Antique Watch", "description": "Mechanical watch from the 1950s, working condition"},
        {"title": "Comic Book Collection", "description": "Rare comic books from the Golden Age"},
        {"title": "Porcelain Figurine", "description": "Hand-painted porcelain collectible figurine"},
        {"title": "Old Coin", "description": "Rare vintage coin from 1800s"},
        {"title": "Vintage Game", "description": "Classic board game from the 1980s, complete set"},
        {"title": "Trading Card", "description": "Rare vintage trading card, mint condition"},
        {"title": "Model Car", "description": "Die-cast model car from 1960s collection"},
        {"title": "Stamp Collection", "description": "International stamps from vintage albums"},
        {"title": "Vintage Photo", "description": "Black and white vintage photograph in frame"},
    ],
    "Electronics": [
        {"title": "Vintage Camera", "description": "Film camera from the 1970s, fully functional"},
        {"title": "Retro Television", "description": "Vintage television set, working condition"},
        {"title": "Record Player", "description": "Vinyl record player with turntable and speakers"},
        {"title": "Portable Radio", "description": "Transistor radio from the 1960s"},
        {"title": "Vintage Phone", "description": "Rotary telephone, classic black design"},
        {"title": "Slide Projector", "description": "Vintage slide projector with carousel"},
        {"title": "Typewriter", "description": "Mechanical typewriter in working order"},
        {"title": "Pocket Watch", "description": "Gold-plated pocket watch with chain"},
        {"title": "Vintage Calculator", "description": "Mechanical calculator from 1950s"},
        {"title": "Cassette Player", "description": "Portable cassette player with headphones"},
    ],
    "Home Décor": [
        {"title": "Vintage Mirror", "description": "Ornate wooden-framed mirror"},
        {"title": "Wall Clock", "description": "Retro wall clock with working mechanism"},
        {"title": "Picture Frame", "description": "Wooden picture frame with glass"},
        {"title": "Vintage Vase", "description": "Ceramic vase with decorative patterns"},
        {"title": "Tapestry Wall Hanging", "description": "Vintage textile wall decoration"},
        {"title": "Candle Holder", "description": "Brass candle holder set"},
        {"title": "Throw Pillow", "description": "Vintage fabric throw pillow cover"},
        {"title": "Door Wreath", "description": "Decorative door wreath with dried flowers"},
        {"title": "Wall Sconce", "description": "Vintage wall-mounted light fixture"},
        {"title": "Decorative Box", "description": "Wooden or metal decorative storage box"},
    ],
}

PRICE_RANGES = {
    "Clothing": (15, 120),
    "Furniture": (25, 400),
    "Collectibles": (15, 1000),
    "Electronics": (15, 400),
    "Home Décor": (10, 120),
}

CONDITIONS = ["New", "Like New", "Good", "Fair"]


class Command(BaseCommand):
    help = "Seed products for presentation with 20 items per category from different shops"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting product seeding..."))
        
        # Create users and sellers
        self.stdout.write(f"Creating {len(SHOP_NAMES)} sellers...")
        sellers = self._create_sellers()
        self.stdout.write(self.style.SUCCESS(f"✓ Created/verified {len(sellers)} sellers"))
        
        # Create categories
        self.stdout.write("Creating product categories...")
        categories = self._create_categories()
        self.stdout.write(self.style.SUCCESS(f"✓ Created {len(categories)} categories"))
        
        # Create conditions
        self.stdout.write("Creating product conditions...")
        conditions = self._create_conditions()
        self.stdout.write(self.style.SUCCESS(f"✓ Created {len(conditions)} conditions"))
        
        # Seed products
        total_products = 0
        for category_name, templates in PRODUCT_TEMPLATES.items():
            category = categories[category_name]
            self.stdout.write(f"\n📦 Seeding {category_name}...")
            
            products_created = 0
            for i in range(20):  # 20 products per category
                template = random.choice(templates)
                seller = sellers[i % len(sellers)]  # Distribute across sellers
                condition = random.choice(list(conditions.values()))
                
                # Generate unique title
                title = f"{template['title']} #{i+1}"
                
                # Generate price within range
                min_price, max_price = PRICE_RANGES[category_name]
                price = Decimal(str(random.uniform(min_price, max_price))).quantize(Decimal('0.01'))
                
                product, created = Product.objects.get_or_create(
                    seller=seller,
                    title=title,
                    defaults={
                        'description': template['description'],
                        'price': price,
                        'category': category,
                        'condition': condition,
                        'stock': random.randint(1, 5),
                        'status': 'published',
                    }
                )
                
                if created:
                    products_created += 1
                    total_products += 1
            
            self.stdout.write(f"   ✓ {products_created} products created for {category_name}")
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Seeding complete!"))
        self.stdout.write(f"   Total products created: {total_products}")
        self.stdout.write(f"   Total sellers: {len(sellers)}")
        self.stdout.write(f"   Total categories: {len(categories)}")
        self.stdout.write(f"   Products per category: 20")

    def _create_sellers(self):
        """Create test sellers if they don't exist."""
        sellers = []
        
        for i, shop_name in enumerate(SHOP_NAMES):
            email = f"seller{i+1}@example.com"
            
            # Check if user already exists
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': f'seller{i+1}',
                    'first_name': 'Test',
                    'last_name': f'Seller {i+1}',
                    'is_seller': True,
                    'email_verified': True,
                }
            )
            
            # Create seller profile if it doesn't exist
            seller, created = Seller.objects.get_or_create(
                user=user,
                defaults={
                    'shop_name': shop_name,
                    'shop_slug': slugify(shop_name),
                    'shop_description': f'Welcome to {shop_name}. We specialize in vintage and antique items.',
                    'location': f'City {i+1}',
                    'status': 'active',
                    'is_verified': True,
                    'bank_account_holder': f'Bank Owner {i+1}',
                    'bank_name': 'Test Bank',
                    'bank_account_number': f'IBAN{i+1:03d}',
                }
            )
            
            # Create subscription if it doesn't exist
            SellerSubscription.objects.get_or_create(
                seller=seller,
                defaults={
                    'plan_type': 'monthly',
                    'start_date': timezone.now().date(),
                    'status': 'active',
                    'amount': Decimal('9.99'),
                    'renewal_date': (timezone.now() + timedelta(days=30)).date(),
                }
            )
            
            sellers.append(seller)
        
        return sellers

    def _create_categories(self):
        """Create product categories."""
        categories = {}
        for category_name in PRODUCT_TEMPLATES.keys():
            cat, created = ProductCategory.objects.get_or_create(
                name=category_name,
                defaults={
                    'slug': slugify(category_name),
                    'description': f'{category_name} category for vintage and antique items'
                }
            )
            categories[category_name] = cat
        return categories

    def _create_conditions(self):
        """Create product conditions."""
        conditions = {}
        for idx, condition_name in enumerate(CONDITIONS):
            cond, created = ProductCondition.objects.get_or_create(
                name=condition_name,
                defaults={'order': idx, 'description': f'{condition_name} condition items'}
            )
            conditions[condition_name] = cond
        return conditions
