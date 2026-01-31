"""
Django management command to create better product images using real or cartoon-style images.
Run with: python manage.py create_better_product_images
"""

import os
import requests
from io import BytesIO
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import random

from products.models import Product, ProductImage


class Command(BaseCommand):
    help = "Create better product images (real or cartoon-style)"

    # Image search terms for each category
    CATEGORY_SEARCH_TERMS = {
        "Clothing": [
            "vintage leather jacket",
            "retro denim",
            "classic sweater",
            "1950s dress",
            "vintage blouse",
            "retro jeans",
            "cardigan sweater",
            "polo shirt vintage",
            "tweed jacket",
            "corduroy pants",
        ],
        "Furniture": [
            "mid-century chair",
            "vintage coffee table",
            "bookshelf wooden",
            "desk lamp brass",
            "side table wood",
            "dining chair",
            "bar stool retro",
            "cabinet console",
            "plant stand wood",
            "floating shelf",
        ],
        "Collectibles": [
            "vinyl record vintage",
            "antique watch",
            "comic books",
            "porcelain figurine",
            "old coins",
            "vintage board game",
            "trading card",
            "die-cast model car",
            "stamp collection",
            "vintage photograph",
        ],
        "Electronics": [
            "vintage film camera",
            "retro television",
            "record player vinyl",
            "transistor radio",
            "rotary telephone",
            "slide projector",
            "typewriter mechanical",
            "pocket watch gold",
            "vintage calculator",
            "cassette player",
        ],
        "Home Décor": [
            "vintage mirror ornate",
            "retro wall clock",
            "picture frame wood",
            "ceramic vase vintage",
            "wall tapestry",
            "candle holder brass",
            "throw pillow vintage",
            "door wreath dried",
            "wall sconce light",
            "decorative box vintage",
        ],
    }

    # Picsum placeholder service for real-looking images
    PICSUM_URL = "https://picsum.photos"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Creating better product images..."))
        
        # Delete existing images
        existing = ProductImage.objects.all().count()
        if existing > 0:
            self.stdout.write(f"Deleting {existing} existing images...")
            ProductImage.objects.all().delete()
        
        products = Product.objects.all()
        total = products.count()
        
        self.stdout.write(f"Creating images for {total} products")
        
        created = 0
        for idx, product in enumerate(products, 1):
            try:
                self._create_image_for_product(product)
                created += 1
                
                if idx % 10 == 0:
                    self.stdout.write(f"   Progress: {idx}/{total}")
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"   ⚠ Skipped {product.title}: {str(e)}")
                )
                # Create fallback cartoon image
                try:
                    self._create_fallback_image(product)
                    created += 1
                except:
                    pass
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Created {created}/{total} product images"))

    def _create_image_for_product(self, product):
        """Create image for product using real images."""
        category_name = product.category.name if product.category else "Home Décor"
        
        # Get random search term for this category
        search_terms = self.CATEGORY_SEARCH_TERMS.get(category_name, ["vintage item"])
        search_term = random.choice(search_terms)
        
        # Use a consistent seed based on product ID for variety
        image_id = (product.id * 13) % 1000 + 1
        
        # Fetch real image from Picsum
        image_url = f"{self.PICSUM_URL}/{400}/{400}?random={image_id}"
        
        try:
            response = requests.get(image_url, timeout=5)
            if response.status_code == 200:
                # Load and slightly modify the image
                img = Image.open(BytesIO(response.content))
                
                # Add semi-transparent overlay with product info
                overlay = Image.new('RGBA', img.size, (0, 0, 0, 100))
                draw = ImageDraw.Draw(overlay)
                
                try:
                    title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
                    text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
                except:
                    title_font = ImageFont.load_default()
                    text_font = ImageFont.load_default()
                
                # Draw price at bottom
                price_text = f"${product.price}"
                draw.text((20, img.height - 60), price_text, fill=(255, 215, 0, 255), font=title_font)
                
                # Composite overlay
                img = img.convert('RGBA')
                img = Image.alpha_composite(img, overlay)
                img = img.convert('RGB')
                
                # Save image
                img_io = BytesIO()
                img.save(img_io, format='JPEG', quality=85)
                img_io.seek(0)
                
                image_name = f"product_{product.id}.jpg"
                ProductImage.objects.create(
                    product=product,
                    image=ContentFile(img_io.getvalue(), name=image_name),
                    alt_text=product.title,
                    order=0,
                )
                
                self.stdout.write(f"   ✓ {product.title[:40]}")
            else:
                raise Exception("Failed to fetch image")
        except Exception as e:
            raise Exception(f"Could not fetch real image: {str(e)}")

    def _create_fallback_image(self, product):
        """Create cartoon-style fallback image."""
        category_name = product.category.name if product.category else "Home Décor"
        
        # Color palette
        colors = {
            "Clothing": ((139, 69, 19), (255, 255, 255)),      # Brown/white
            "Furniture": ((101, 67, 33), (240, 230, 200)),     # Dark brown/cream
            "Collectibles": ((212, 175, 55), (30, 30, 30)),    # Gold/dark
            "Electronics": ((47, 79, 79), (200, 200, 200)),    # Slate/light
            "Home Décor": ((105, 105, 105), (220, 220, 220)),  # Dim gray/light
        }
        
        bg_color, accent_color = colors.get(category_name, ((100, 100, 100), (255, 255, 255)))
        
        # Create image
        width, height = 400, 400
        img = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw simple shapes to represent items
        draw.rectangle([50, 50, 350, 350], outline=accent_color, width=3)
        draw.ellipse([100, 100, 300, 300], fill=accent_color)
        draw.text((20, 20), product.title[:25], fill=accent_color)
        draw.text((20, height-40), f"${product.price}", fill=accent_color)
        
        # Save image
        img_io = BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        image_name = f"product_{product.id}_fallback.png"
        ProductImage.objects.create(
            product=product,
            image=ContentFile(img_io.getvalue(), name=image_name),
            alt_text=product.title,
            order=0,
        )
