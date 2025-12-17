"""Admin configuration for orders app."""

from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "quantity", "price_at_purchase", "created_at"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["pk", "buyer", "total_price", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["buyer__email", "tracking_number"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [OrderItemInline]
    fieldsets = (
        ("Order Information", {
            "fields": ("buyer", "status", "total_price")
        }),
        ("Shipping", {
            "fields": ("shipping_name", "shipping_address", "shipping_phone", "tracking_number")
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at")
        }),
    )
