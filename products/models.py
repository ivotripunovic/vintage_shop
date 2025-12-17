"""
Product listings and related models.
"""

from django.db import models
from django.core.validators import MinValueValidator
from core.models import TimeStampedModel, SoftDeleteModel


class ProductCategory(models.Model):
    """Product categories/classifications."""

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"

    def __str__(self):
        return self.name


class ProductCondition(models.Model):
    """Condition levels for products (New, Like New, Good, Fair)."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "Product Condition"
        verbose_name_plural = "Product Conditions"

    def __str__(self):
        return self.name


class Product(SoftDeleteModel):
    """Product listings by sellers."""

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("published", "Published"),
        ("sold", "Sold"),
        ("archived", "Archived"),
    )

    seller = models.ForeignKey(
        "sellers.Seller",
        on_delete=models.CASCADE,
        related_name="products",
    )
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    condition = models.ForeignKey(
        ProductCondition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    stock = models.IntegerField(default=1, validators=[MinValueValidator(0)])
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="draft"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["seller", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["-created_at"]),
        ]
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return self.title

    @property
    def is_available(self):
        """Check if product is available for purchase."""
        return self.status == "published" and self.stock > 0

    @property
    def is_published(self):
        """Check if product is published."""
        return self.status == "published"

    def publish(self):
        """Publish the product."""
        self.status = "published"
        self.save()

    def unpublish(self):
        """Unpublish the product."""
        self.status = "draft"
        self.save()

    def mark_sold(self):
        """Mark product as sold."""
        self.status = "sold"
        self.save()


class ProductImage(TimeStampedModel):
    """Images for products (multiple per product)."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="products/%Y/%m/%d/")
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"

    def __str__(self):
        return f"{self.product.title} - Image {self.order}"
