"""Admin configuration for sellers app."""

from django.contrib import admin

from .models import TIER_CHOICES, Seller, SellerSubscription, SellerTier


def _move_to_tier_action(tier, label):
    """Build an admin action that moves the selected sellers to a tier."""

    def action(modeladmin, request, queryset):
        moved = invoiced = 0
        for seller in queryset:
            if seller.tier == tier:
                continue
            if seller.change_tier(tier):
                invoiced += 1
            moved += 1
        modeladmin.message_user(
            request,
            f"{moved} seller(s) moved to {label}, {invoiced} invoice(s) created.",
        )

    action.__name__ = f"move_to_{tier}"
    return admin.action(description=f"Move to {label}")(action)


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
    # Trader fields are the seller's own statement; staff can only clear them.
    # Tier changes go through the move_to_* actions so billing follows.
    readonly_fields = [
        "created_at",
        "updated_at",
        "shop_slug",
        "tier",
        "trader_confirmed_at",
        "trader_statement",
    ]
    actions = ["clear_trader_confirmation"] + [
        _move_to_tier_action(tier, label) for tier, label in TIER_CHOICES
    ]
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
            {"fields": ("tier", "status", "is_verified")},
        ),
        ("Trader", {"fields": ("trader_confirmed_at", "trader_statement")}),
        (
            "Bank Details",
            {
                "fields": ("bank_account_holder", "bank_name", "bank_account_number"),
                "classes": ("collapse",),
            },
        ),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    @admin.action(description="Clear trader confirmation")
    def clear_trader_confirmation(self, request, queryset):
        for seller in queryset:
            seller.clear_trader()
            seller.save()


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
