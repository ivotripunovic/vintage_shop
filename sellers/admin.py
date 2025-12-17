"""Admin configuration for sellers app."""

from django.contrib import admin
from .models import Seller, SellerSubscription


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ["shop_name", "user", "status", "is_verified", "created_at"]
    list_filter = ["status", "is_verified", "created_at"]
    search_fields = ["shop_name", "user__email"]
    readonly_fields = ["created_at", "updated_at", "shop_slug"]
    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Shop Information", {
            "fields": ("shop_name", "shop_slug", "shop_description", "shop_image", "location")
        }),
        ("Status", {"fields": ("status", "is_verified")}),
        ("Bank Details", {
            "fields": ("bank_account_holder", "bank_name", "bank_account_number"),
            "classes": ("collapse",),
        }),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(SellerSubscription)
class SellerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["seller", "plan_type", "amount", "status", "renewal_date"]
    list_filter = ["status", "plan_type", "created_at"]
    search_fields = ["seller__shop_name", "seller__user__email"]
    readonly_fields = ["created_at", "updated_at"]
