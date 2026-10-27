"""Admin configuration for sellers app."""

from django.contrib import admin

from .models import Seller, SellerSubscription, SellerTier


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = [
        "shop_name",
        "user",
        "tier",
        "status",
        "is_verified",
        "is_trader",
        "created_at",
    ]
    list_filter = [
        "tier",
        "status",
        "is_verified",
        ("trader_confirmed_at", admin.EmptyFieldListFilter),
        "created_at",
    ]
    search_fields = ["shop_name", "user__email"]
    readonly_fields = ["created_at", "updated_at", "shop_slug"]
    fieldsets = (
        ("User", {"fields": ("user",)}),
        (
            "Shop Information",
            {
                "fields": (
                    "shop_name",
                    "shop_slug",
                    "shop_description",
                    "shop_image",
                    "location",
                )
            },
        ),
        (
            "Status",
            {"fields": ("tier", "status", "is_verified", "trader_confirmed_at")},
        ),
        (
            "Bank Details",
            {
                "fields": ("bank_account_holder", "bank_name", "bank_account_number"),
                "classes": ("collapse",),
            },
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(boolean=True, description="Trader")
    def is_trader(self, obj):
        return obj.is_trader


@admin.register(SellerTier)
class SellerTierAdmin(admin.ModelAdmin):
    list_display = [
        "tier",
        "monthly_listing_limit",
        "monthly_price",
        "listing_expiry_days",
    ]
    list_editable = ["monthly_listing_limit", "monthly_price", "listing_expiry_days"]

    # The three tiers are fixed in code; admins only edit their settings
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SellerSubscription)
class SellerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["seller", "plan_type", "amount", "status", "renewal_date"]
    list_filter = ["status", "plan_type", "created_at"]
    search_fields = ["seller__shop_name", "seller__user__email"]
    readonly_fields = ["created_at", "updated_at"]
