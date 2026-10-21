from django.contrib import admin

from .models import FavouriteSeller, WishlistItem


@admin.register(FavouriteSeller)
class FavouriteSellerAdmin(admin.ModelAdmin):
    list_display = ("user", "seller", "created_at")
    search_fields = ("user__email", "seller__shop_name")
    raw_id_fields = ("user", "seller")


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
    search_fields = ("user__email", "product__title")
    raw_id_fields = ("user", "product")
