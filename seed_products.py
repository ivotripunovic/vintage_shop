"""
Django management command to seed products for presentation.
Run with: python manage.py shell < seed_products.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from django.utils.text import slugify
from users.models import User
from sellers.models import Seller, SellerSubscription
from products.models import Product, ProductCategory, ProductCondition
from django.utils import timezone
from datetime import timedelta
import random

# Sample data
SHOP_NAMES = [
    "Vintage Treasures Co", "Retro Revival Shop", "Classics & More",
    "Timeless Collectibles", "Nostalgia Lane", "Estate Find Emporium",
    "Antique Alley", "Retro Rents", "Vintage Vault", "Secondhand Stories",
    "Time Warp Collectibles", "Heirloom House", "Bygone Boutique",
    "Vintage & Co", "Old School Market"
]

PRODUCT_TEMPLATES = {
    "Clothing": [
        {"title": "Vintage Leather Jacket", "description": "Classic brown leather jacket from the 1980s, excellent condition", "price_range": (45, 120)},
        {"title": "Retro Denim Jacket", "description": "Blue denim jacket with original tags, perfect vintage piece", "price_range": (25, 65)},
        {"title": "Wool Sweater", "description": "Hand-knitted wool sweater in neutral tones", "price_range": (15, 40)},
        {"title": "Floral Dress", "description": "1950s-style floral print cotton dress", "price_range": (30, 75)},
        {"title": "Silk Blouse", "description": "Vintage silk blouse with pearl buttons", "price_range": (20, 55)},
        {"title": "High-Waisted Jeans", "description": "Classic high-waisted denim, as per vintage photos", "price_range": (35, 85)},
        {"title": "Cardigan Sweater", "description": "Soft cardigan from the 1970s era", "price_range": (18, 50)},
        {"title": "Polo Shirt", "description": "Vintage polo shirt with logo embroidery", "price_range": (12, 40)},
        {"title": "Tweed Jacket", "description": "Professional tweed jacket, perfect for offices", "price_range": (40, 95)},
        {"title": "Corduroy Pants", "description": "Brown corduroy pants, retro style", "price_range": (20, 50)},
    ],
    "Furniture": [
        {"title": "Mid-Century Chair", "description": "Wooden chair with fabric seat, classic design", "price_range": (60, 200)},
        {"title": "Vintage Coffee Table", "description": "Teak wood coffee table from the 1960s", "price_range": (80, 250)},
        {"title": "Bookshelf Unit", "description": "Wooden bookshelf with multiple shelves", "price_range": (100, 300)},
        {"title": "Desk Lamp", "description": "Brass desk lamp with original shade", "price_range": (30, 100)},
        {"title": "Side Table", "description": "Small wooden side table for living room", "price_range": (40, 120)},
        {"title": "Dining Chair", "description": "Set of 4 vintage dining chairs", "price_range": (150, 400)},
        {"title": "Bar Stool", "description": "Chrome and vinyl bar stool, retro design", "price_range": (35, 85)},
        {"title": "Cabinet Console", "description": "Wooden storage cabinet with doors", "price_range": (120, 350)},
        {"title": "Plant Stand", "description": "Wooden plant stand for indoor plants", "price_range": (25, 70)},
        {"title": "Wall Shelf", "description": "Wooden floating shelf with brackets", "price_range": (20, 60)},
    ],
    "Collectibles": [
        {"title": "Vintage Vinyl Record", "description": "Original pressing from the 1970s, near mint condition", "price_range": (15, 50)},
        {"title": "Antique Watch", "description": "Mechanical watch from the 1950s, working condition", "price_range": (80, 300)},
        {"title": "Comic Book Collection", "description": "Rare comic books from the Golden Age", "price_range": (100, 500)},
        {"title": "Porcelain Figurine", "description": "Hand-painted porcelain collectible figurine", "price_range": (20, 75)},
        {"title": "Old Coin", "description": "Rare vintage coin from 1800s", "price_range": (50, 200)},
        {"title": "Vintage Game", "description": "Classic board game from the 1980s, complete set", "price_range": (25, 80)},
        {"title": "Trading Card", "description": "Rare vintage trading card, mint condition", "price_range": (150, 1000)},
        {"title": "Model Car", "description": "Die-cast model car from 1960s collection", "price_range": (30, 120)},
        {"title": "Stamp Collection", "description": "International stamps from vintage albums", "price_range": (40, 150)},
        {"title": "Vintage Photo", "description": "Black and white vintage photograph in frame", "price_range": (15, 60)},
    ],
    "Electronics": [
        {"title": "Vintage Camera", "description": "Film camera from the 1970s, fully functional", "price_range": (50, 150)},
        {"title": "Retro Television", "description": "Vintage television set, working condition", "price_range": (100, 400)},
        {"title": "Record Player", "description": "Vinyl record player with turntable and speakers", "price_range": (80, 250)},
        {"title": "Portable Radio", "description": "Transistor radio from the 1960s", "price_range": (30, 100)},
        {"title": "Vintage Phone", "description": "Rotary telephone, classic black design", "price_range": (20, 70)},
        {"title": "Slide Projector", "description": "Vintage slide projector with carousel", "price_range": (40, 120)},
        {"title": "Typewriter", "description": "Mechanical typewriter in working order", "price_range": (60, 180)},
        {"title": "Pocket Watch", "description": "Gold-plated pocket watch with chain", "price_range": (70, 200)},
        {"title": "Vintage Calculator", "description": "Mechanical calculator from 1950s", "price_range": (25, 80)},
        {"title": "Cassette Player", "description": "Portable cassette player with headphones", "price_range": (15, 50)},
    ],
    "Home Décor": [
        {"title": "Vintage Mirror", "description": "Ornate wooden-framed mirror", "price_range": (30, 100)},
        {"title": "Wall Clock", "description": "Retro wall clock with working mechanism", "price_range": (25, 80)},
        {"title": "Picture Frame", "description": "Wooden picture frame with glass", "price_range": (10, 40)},
        {"title": "Vintage Vase", "description": "Ceramic vase with decorative patterns", "price_range": (20, 70)},
        {"title": "Tapestry Wall Hanging", "description": "Vintage textile wall decoration", "price_range": (30, 90)},
        {"title": "Candle Holder", "description": "Brass candle holder set", "price_range": (15, 50)},
        {"title": "Throw Pillow", "description": "Vintage fabric throw pillow cover", "price_range": (12, 40)},
        {"title": "Door Wreath", "description": "Decorative door wreath with dried flowers", "price_range": (20, 60)},
        {"title": "Wall Sconce", "description": "Vintage wall-mounted light fixture", "price_range": (40, 120)},
        {"title": "Decorative Box", "description": "Wooden or metal decorative storage box", "price_range": (15, 50)},
    ],
}

CONDITIONS = ["New", "Like New", "Good", "Fair"]

def create_test_users_and_sellers():
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

def create_categories():
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

def create_conditions():
    """Create product conditions."""
    conditions = {}
    for idx, condition_name in enumerate(CONDITIONS):
        cond, created = ProductCondition.objects.get_or_create(
            name=condition_name,
            defaults={'order': idx, 'description': f'{condition_name} condition items'}
        )
        conditions[condition_name] = cond
    return conditions

def seed_products():
    """Create 20 products for each category from different sellers."""
    print("Starting product seeding...")
    
    # Create users and sellers
    print(f"Creating {len(SHOP_NAMES)} sellers...")
    sellers = create_test_users_and_sellers()
    print(f"✓ Created/verified {len(sellers)} sellers")
    
    # Create categories
    print("Creating product categories...")
    categories = create_categories()
    print(f"✓ Created {len(categories)} categories")
    
    # Create conditions
    print("Creating product conditions...")
    conditions = create_conditions()
    print(f"✓ Created {len(conditions)} conditions")
    
    # Seed products
    total_products = 0
    for category_name, templates in PRODUCT_TEMPLATES.items():
        category = categories[category_name]
        print(f"\n📦 Seeding {category_name}...")
        
        products_created = 0
        for i in range(20):  # 20 products per category
            template = random.choice(templates)
            seller = sellers[i % len(sellers)]  # Distribute across sellers
            condition = random.choice(list(conditions.values()))
            
            # Generate unique title
            title = f"{template['title']} #{i+1}" if i > 0 else template['title']
            
            # Generate price within range
            min_price, max_price = template['price_range']
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
        
        print(f"   ✓ {products_created} products created for {category_name}")
    
    print(f"\n✅ Seeding complete!")
    print(f"   Total products created: {total_products}")
    print(f"   Total sellers: {len(sellers)}")
    print(f"   Total categories: {len(categories)}")
    print(f"   Products per category: ~20")

if __name__ == '__main__':
    seed_products()
