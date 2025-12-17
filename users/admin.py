"""Admin configuration for users app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, VerificationToken


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "first_name", "last_name", "is_seller", "is_buyer", "email_verified", "date_joined"]
    list_filter = ["is_seller", "is_buyer", "email_verified", "date_joined"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Custom Fields", {
            "fields": ("is_seller", "is_buyer", "email_verified", "email_verified_at")
        }),
    )


@admin.register(VerificationToken)
class VerificationTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "token_type", "is_used", "created_at", "expires_at"]
    list_filter = ["token_type", "is_used", "created_at"]
    search_fields = ["user__email", "token"]
    readonly_fields = ["token", "created_at", "used_at"]
    fieldsets = (
        ("Token Info", {
            "fields": ("user", "token", "token_type")
        }),
        ("Expiration", {
            "fields": ("created_at", "expires_at")
        }),
        ("Status", {
            "fields": ("is_used", "used_at")
        }),
    )
