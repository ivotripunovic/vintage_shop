"""Admin configuration for users app.

Email verification is allauth's: edit it under Accounts › Email addresses.
Changing a user's email here replaces their allauth address with a new,
unverified one (see UserAdmin.save_model).
"""

from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import transaction
from django.db.models import Exists, OuterRef

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

    def get_queryset(self, request):
        verified = EmailAddress.objects.filter(
            user=OuterRef("pk"), email__iexact=OuterRef("email"), verified=True
        )
        return super().get_queryset(request).annotate(_email_verified=Exists(verified))

    @admin.display(
        boolean=True, description="Email verified", ordering="_email_verified"
    )
    def email_is_verified(self, user):
        return user._email_verified

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            previous = (
                User.objects.filter(pk=obj.pk).values_list("email", flat=True).first()
                if change
                else None
            )
            super().save_model(request, obj, form, change)
            if previous and previous.lower() != obj.email.lower():
                # The old address must stop working (reset, login); the new
                # one is unproven until its owner confirms it
                EmailAddress.objects.filter(user=obj, email__iexact=previous).delete()
                if obj.email:
                    obj.set_primary_email(verified=False)
