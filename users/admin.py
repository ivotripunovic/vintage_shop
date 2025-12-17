"""Admin configuration for users app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


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
