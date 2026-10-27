"""Admin configuration for products app."""

from django.contrib import admin, messages
from django.db.models import F
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.html import format_html

from chat.models import Conversation

from .models import (
    NewAd,
    Product,
    ProductCategory,
    ProductCondition,
    ProductImage,
    ProductView,
)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "slug"]
    list_filter = ["parent"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProductCondition)
class ProductConditionAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]
    list_editable = ["order"]


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ["image", "alt_text", "order"]


class ReviewImageInline(ProductImageInline):
    """Images shown read-only in the review queue."""

    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "seller",
        "price",
        "status",
        "stock",
        "is_picked",
        "is_deleted",
    ]
    list_editable = ["is_picked"]
    list_filter = [
        "status",
        "is_picked",
        "category",
        "condition",
        "created_at",
        "is_deleted",
    ]
    search_fields = ["title", "seller__shop_name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ProductImageInline]
    fieldsets = (
        (
            "Product Information",
            {"fields": ("seller", "title", "description", "price")},
        ),
        ("Classification", {"fields": ("category", "condition")}),
        ("Inventory", {"fields": ("stock",)}),
        ("Status", {"fields": ("status", "is_picked")}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at", "is_deleted", "deleted_at")},
        ),
    )

    def get_queryset(self, request):
        """Include soft-deleted products in admin."""
        return super().get_queryset(request).all()


class ReviewedFilter(admin.SimpleListFilter):
    title = "reviewed"
    parameter_name = "reviewed"

    def lookups(self, request, model_admin):
        return (("no", "Not reviewed"), ("yes", "Reviewed"))

    def queryset(self, request, queryset):
        if self.value() == "no":
            return queryset.filter(reviewed_at__isnull=True)
        if self.value() == "yes":
            return queryset.filter(reviewed_at__isnull=False)
        return queryset


@admin.register(NewAd)
class NewAdAdmin(admin.ModelAdmin):
    """Review queue: published ads, unreviewed first, newest first."""

    list_display = [
        "thumbnail",
        "title",
        "seller",
        "seller_tier",
        "price",
        "status",
        "listed_at",
        "is_reviewed",
        "is_picked",
    ]
    list_display_links = ["thumbnail", "title"]
    list_filter = [ReviewedFilter, "seller__tier", "is_picked", "status", "listed_at"]
    search_fields = ["title", "seller__shop_name"]
    ordering = [F("reviewed_at").asc(nulls_first=True), "-listed_at"]
    actions = ["mark_reviewed", "mark_picked", "unmark_picked", "message_seller"]
    inlines = [ReviewImageInline]
    fields = [
        "seller",
        "title",
        "description",
        "price",
        "category",
        "condition",
        "stock",
        "status",
        "listed_at",
        "expires_at",
        "reviewed_at",
        "reviewed_by",
        "is_picked",
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(listed_at__isnull=False, is_deleted=False)
            .select_related("seller")
            .prefetch_related("images")
        )

    # Read-only queue; ads are edited in the regular Products admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Image")
    def thumbnail(self, obj):
        images = obj.images.all()
        if not images:
            return "—"
        return format_html(
            '<img src="{}" style="width:48px;height:48px;object-fit:cover">',
            images[0].image.url,
        )

    @admin.display(description="Tier", ordering="seller__tier")
    def seller_tier(self, obj):
        return obj.seller.get_tier_display()

    @admin.display(description="Reviewed", boolean=True)
    def is_reviewed(self, obj):
        return obj.reviewed_at is not None

    @admin.action(description="Mark selected ads as reviewed")
    def mark_reviewed(self, request, queryset):
        count = queryset.filter(reviewed_at__isnull=True).update(
            reviewed_at=timezone.now(), reviewed_by=request.user
        )
        self.message_user(request, f"{count} ad(s) marked as reviewed.")

    @admin.action(description="Pick selected ads for the home page")
    def mark_picked(self, request, queryset):
        count = queryset.update(is_picked=True)
        self.message_user(request, f"{count} ad(s) picked for the home page.")

    @admin.action(description="Remove selected ads from the home page picks")
    def unmark_picked(self, request, queryset):
        count = queryset.update(is_picked=False)
        self.message_user(request, f"{count} ad(s) removed from the home page picks.")

    @admin.action(description="Message the seller about this ad")
    def message_seller(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Select exactly one ad to message its seller.",
                messages.WARNING,
            )
            return None
        product = queryset.get()
        if product.seller.user == request.user:
            self.message_user(request, "This is your own ad.", messages.WARNING)
            return None
        conversation, _ = Conversation.objects.get_or_create(
            buyer=request.user,
            seller=product.seller,
            product=product,
            defaults={"is_team": True},
        )
        return redirect("chat_detail", pk=conversation.pk)


@admin.register(ProductView)
class ProductViewAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "session_key", "created_at"]
    readonly_fields = ["product", "user", "session_key", "created_at"]
    search_fields = ["product__title", "user__email"]
