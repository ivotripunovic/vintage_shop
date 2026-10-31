"""Admin configuration for orders app."""

from django.contrib import admin

from .models import Sale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ["product_title", "seller", "buyer", "created_at"]
    search_fields = ["product_title", "seller__shop_name", "buyer__email"]
    list_select_related = ["seller", "buyer"]
    raw_id_fields = ["product", "seller", "buyer"]
