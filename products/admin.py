"""Admin configuration for products app."""

from django.contrib import admin
from .models import Product, ProductImage, ProductCategory, ProductCondition


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProductCondition)
class ProductConditionAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]
    list_editable = ["order"]


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ["image", "alt_text", "order"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["title", "seller", "price", "status", "stock", "is_deleted"]
    list_filter = ["status", "category", "condition", "created_at", "is_deleted"]
    search_fields = ["title", "seller__shop_name"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ProductImageInline]
    fieldsets = (
        ("Product Information", {
            "fields": ("seller", "title", "description", "price")
        }),
        ("Classification", {
            "fields": ("category", "condition")
        }),
        ("Inventory", {
            "fields": ("stock",)
        }),
        ("Status", {
            "fields": ("status",)
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at", "is_deleted", "deleted_at")
        }),
    )

    def get_queryset(self, request):
        """Include soft-deleted products in admin."""
        return super().get_queryset(request).all()
