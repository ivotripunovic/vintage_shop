"""Admin configuration for users app.

Email verification is allauth's: edit it under Accounts › Email addresses.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "email",
        "first_name",
        "last_name",
        "is_seller",
        "is_buyer",
        "email_is_verified",
        "date_joined",
    ]
    list_filter = ["is_seller", "is_buyer", "date_joined"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Custom Fields", {"fields": ("is_seller", "is_buyer")}),
    )

    @admin.display(boolean=True, description="Email verified")
    def email_is_verified(self, user):
        return user.email_verified
