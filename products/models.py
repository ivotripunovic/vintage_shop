"""
Product listings and related models.
"""

from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from core.models import SoftDeleteModel, TimeStampedModel


class ProductCategory(models.Model):
    """Product categories/classifications. parent=None means top-level category."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"
        unique_together = [("name", "parent")]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} › {self.name}"
        return self.name

    @property
    def is_top_level(self):
        return self.parent_id is None

    def get_all_ids(self):
        """Return this category's id plus all descendant ids."""
        # One query per tree level rather than one per category
        ids = [self.id]
        level = [self.id]
        while level:
            level = [
                pk
                for pk in ProductCategory.objects.filter(
                    parent_id__in=level
                ).values_list("id", flat=True)
                if pk not in ids  # guards against a parent cycle
            ]
            ids.extend(level)
        return ids


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
        ("draft", "Nacrt"),
        ("published", "Objavljeno"),
        ("sold", "Prodato"),
        ("archived", "Arhivirano"),
        ("expired", "Isteklo"),
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    # Start and end of the current listing period; each period uses one of the
    # seller's monthly listing slots. expires_at is empty when it never expires.
    listed_at = models.DateTimeField(null=True, blank=True, editable=False)
    expires_at = models.DateTimeField(null=True, blank=True, editable=False)
    # Set by admins only; picked products are shown on the home page
    is_picked = models.BooleanField(default=False, db_index=True)
    # Set when an admin checks the ad in the "New ads for review" queue
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_products",
    )
    # Unique viewers, kept in step with ProductView rows by products.popularity
    view_count = models.PositiveIntegerField(default=0, editable=False)

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

    def save(self, *args, **kwargs):
        """Start a new listing period when the product is published."""
        if self.status == "published" and self.needs_new_listing_period:
            self.listed_at = timezone.now()
            expiry_days = self.seller.tier_settings["listing_expiry_days"]
            self.expires_at = (
                self.listed_at + timedelta(days=expiry_days)
                if expiry_days is not None
                else None
            )
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "listed_at", "expires_at"}
        super().save(*args, **kwargs)

    @property
    def needs_new_listing_period(self):
        """Check if publishing would start a new period: first time, or expired."""
        if self.listed_at is None:
            return True
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_available(self):
        """Check if product is available for purchase."""
        return self.status == "published" and self.stock > 0

    @property
    def is_published(self):
        """Check if product is published."""
        return self.status == "published"

    @property
    def is_listed(self):
        """Check if buyers can see the product: published, not deleted, shop active."""
        return (
            self.status == "published"
            and not self.is_deleted
            and self.seller.is_active_shop
        )

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


class NewAd(Product):
    """Published products, as shown in the admin review queue."""

    class Meta:
        proxy = True
        verbose_name = "New ad"
        verbose_name_plural = "New ads for review"


class ProductView(TimeStampedModel):
    """One unique viewer of a product: a user, or an anonymous session."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="views",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="product_views",
    )
    session_key = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_product_view_user",
            ),
            models.UniqueConstraint(
                fields=["product", "session_key"],
                condition=models.Q(user__isnull=True),
                name="unique_product_view_session",
            ),
        ]

    def __str__(self):
        return f"{self.user or self.session_key} → {self.product}"


class ProcessedPhoto(models.Model):
    """
    A photo processed on save (products.images): upright, stripped of
    metadata, capped in size, with a thumbnail and quality measurements.
    """

    image = models.ImageField(upload_to="products/%Y/%m/%d/")
    # Grid-sized copy made on save (products.images); empty if processing failed
    thumbnail = models.ImageField(
        upload_to="products/thumbs/%Y/%m/%d/", blank=True, editable=False
    )
    # Measured on save, for the photo tips in products.quality
    width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    brightness = models.FloatField(null=True, blank=True, editable=False)
    sharpness = models.FloatField(null=True, blank=True, editable=False)

    PHOTO_FIELDS = ("image", "thumbnail", "width", "height", "brightness", "sharpness")

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Only a newly assigned file is processed; reorders and alt text
        # changes save without touching the photo
        processed = self.__dict__.pop("_processed", False)
        if self.image and not self.image._committed and not processed:
            if self.pk:
                # Replacing the photo of an existing row: its old files go
                old = (
                    type(self)
                    .objects.filter(pk=self.pk)
                    .values_list("image", "thumbnail")
                )
                for name in old.first() or ():
                    self._mark_stale(name)
                self.thumbnail = ""
                self.width = self.height = self.brightness = self.sharpness = None
            self.process(keep_original=False)
            self.__dict__.pop("_processed", None)
        super().save(*args, **kwargs)
        self._delete_stale_files()

    def process(self, keep_original=False):
        """
        Rotate, strip, resize and thumbnail the photo; measure its quality.

        Replaced files are only deleted once the row is saved and committed,
        so a failed save never leaves the row pointing at missing files.
        """
        from .images import process_photo

        result = process_photo(self.image, self.image.name, keep_original)
        if result is None:
            return False
        if result.image is not None:
            if self.image._committed:
                self._mark_stale(self.image.name)
            self.image.save(result.image.name, result.image, save=False)
        self._mark_stale(self.thumbnail.name)
        self.thumbnail.save(result.thumbnail.name, result.thumbnail, save=False)
        self.width, self.height = result.width, result.height
        self.brightness, self.sharpness = result.brightness, result.sharpness
        self.__dict__["_processed"] = True  # save() won't process it again
        return True

    def _mark_stale(self, name):
        if name:
            self.__dict__.setdefault("_stale_files", set()).add(name)

    def _delete_stale_files(self):
        stale = self.__dict__.pop("_stale_files", set())
        stale -= {self.image.name, self.thumbnail.name}
        delete_unreferenced_files(self.image.storage, stale)

    def discard_unsaved(self):
        """
        Remove the files processing stored for a photo whose row was never
        saved. An upload kept as it is was never written, so only files
        actually in storage are considered.
        """
        names = [f.name for f in (self.image, self.thumbnail) if f and f._committed]
        delete_unreferenced_files(self.image.storage, names)

    @property
    def thumb_url(self):
        """Thumbnail for grids and lists, or the full photo if there is none."""
        return (self.thumbnail or self.image).url


class ProductImage(ProcessedPhoto, TimeStampedModel):
    """Images for products (multiple per product)."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"

    def __str__(self):
        return f"{self.product.title} - Image {self.order}"


class PhotoUpload(ProcessedPhoto, TimeStampedModel):
    """
    A photo uploaded on the listing form before its product exists.

    The file is processed and stored where product photos live, so saving
    the listing only turns the row into a ProductImage (attach_to). Rows
    left behind by abandoned forms are removed by purge_photo_uploads.
    """

    seller = models.ForeignKey(
        "sellers.Seller",
        on_delete=models.CASCADE,
        related_name="photo_uploads",
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Upload {self.pk} by {self.seller_id}"

    def attach_to(self, product, order):
        """Move this photo onto product as a ProductImage, keeping its files."""
        fields = {name: getattr(self, name) for name in self.PHOTO_FIELDS}
        image = ProductImage.objects.create(
            product=product,
            order=order,
            alt_text=f"{product.title} – fotografija {order + 1}",
            **{name: getattr(value, "name", value) for name, value in fields.items()},
        )
        # A plain row delete: the files now belong to the ProductImage
        PhotoUpload.objects.filter(pk=self.pk).delete()
        return image


def photo_file_in_use(name):
    """Whether any photo row (attached or pending) still points at name."""
    uses = models.Q(image=name) | models.Q(thumbnail=name)
    return (
        ProductImage.objects.filter(uses).exists()
        or PhotoUpload.objects.filter(uses).exists()
    )


def delete_unreferenced_files(storage, names):
    """
    Once the transaction commits, delete each file no photo row uses.

    The single rule for removing photo files: attaching a pending upload
    hands its files to a ProductImage, so a racing purge or a double submit
    must never delete files another row has taken over.
    """
    names = {name for name in names if name}
    if not names:
        return

    def delete():
        for name in names:
            if not photo_file_in_use(name):
                storage.delete(name)

    transaction.on_commit(delete)
