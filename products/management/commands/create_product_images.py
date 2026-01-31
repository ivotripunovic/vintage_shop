"""
Django management command to create placeholder images for products.
Run with: python manage.py create_product_images
"""

import os
from io import BytesIO
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import random

from products.models import Product, ProductImage


class Command(BaseCommand):
    help = "Create placeholder images for all products"

    # Color palette for different categories
    CATEGORY_COLORS = {
        "Clothing": "#8B4513",  # Saddle brown
        "Furniture": "#654321",  # Dark brown
        "Collectibles": "#D4AF37",  # Gold
        "Electronics": "#2F4F4F",  # Dark slate gray
        "Home Décor": "#696969",  # Dim gray
    }

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Creating product images..."))
        
        products = Product.objects.filter(images__isnull=True)
        total = products.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING("All products already have images."))
            return
        
        self.stdout.write(f"Found {total} products without images")
        
        created = 0
        for idx, product in enumerate(products, 1):
            try:
                self._create_image_for_product(product)
                created += 1
                
                if idx % 10 == 0:
                    self.stdout.write(f"   Progress: {idx}/{total}")
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"   Error creating image for {product.title}: {str(e)}")
                )
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Created {created}/{total} product images"))

    def _create_image_for_product(self, product):
        """Create a placeholder image for a product."""
        # Get color based on category
        category_name = product.category.name if product.category else "Home Décor"
        bg_color = self.CATEGORY_COLORS.get(category_name, "#696969")
        
        # Convert hex to RGB
        hex_color = bg_color.lstrip('#')
        rgb_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        # Create image
        width, height = 400, 400
        img = Image.new('RGB', (width, height), color=rgb_color)
        draw = ImageDraw.Draw(img)
        
        # Try to use a nice font, fall back to default if not available
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
        
        # Add product title (wrapped)
        title_text = product.title
        max_chars_per_line = 20
        title_lines = []
        words = title_text.split()
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= max_chars_per_line:
                current_line += word + " "
            else:
                if current_line:
                    title_lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            title_lines.append(current_line.strip())
        
        # Draw title
        y_position = 50
        for line in title_lines:
            draw.text((20, y_position), line, fill="white", font=title_font)
            y_position += 40
        
        # Add category
        y_position += 20
        draw.text((20, y_position), f"Category: {category_name}", fill="white", font=text_font)
        
        # Add price
        y_position += 30
        draw.text((20, y_position), f"${product.price}", fill="#FFD700", font=title_font)
        
        # Add condition
        y_position += 40
        condition_text = product.condition.name if product.condition else "Unknown"
        draw.text((20, y_position), f"Condition: {condition_text}", fill="white", font=text_font)
        
        # Add stock
        y_position += 30
        draw.text((20, y_position), f"Stock: {product.stock}", fill="white", font=text_font)
        
        # Add seller
        y_position += 40
        draw.text((20, y_position), f"Seller: {product.seller.shop_name}", fill="white", font=text_font)
        
        # Save image
        img_io = BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        # Create ProductImage
        image_name = f"{product.seller.shop_slug}_{product.id}.png"
        ProductImage.objects.create(
            product=product,
            image=ContentFile(img_io.getvalue(), name=image_name),
            alt_text=product.title,
            order=0,
        )
        
        self.stdout.write(f"   ✓ Created image for: {product.title}")
