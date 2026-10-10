import datetime

from django.contrib import admin
from django.utils import timezone

from .models import WaitlistSubscriber

STALE_UNCONFIRMED_AGE = datetime.timedelta(days=7)


class ConfirmationStatusFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            ("confirmed", "Confirmed"),
            ("unconfirmed", "Unconfirmed"),
            ("notified", "Launch email sent"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "confirmed":
            return queryset.filter(confirmed_at__isnull=False)
        if self.value() == "unconfirmed":
            return queryset.filter(confirmed_at__isnull=True)
        if self.value() == "notified":
            return queryset.filter(notified_at__isnull=False)
        return queryset


@admin.register(WaitlistSubscriber)
class WaitlistSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "is_confirmed", "ip_address", "created_at", "notified_at")
    list_filter = (ConfirmationStatusFilter,)
    search_fields = ("email",)
    ordering = ("-created_at",)
    readonly_fields = (
        "email",
        "ip_address",
        "confirmed_at",
        "confirmation_sent_at",
        "notified_at",
        "created_at",
        "updated_at",
    )
    actions = ["delete_stale_unconfirmed"]

    @admin.display(boolean=True, description="Confirmed")
    def is_confirmed(self, obj):
        return obj.is_confirmed

    @admin.action(description="Delete unconfirmed older than 7 days (from selection)")
    def delete_stale_unconfirmed(self, request, queryset):
        cutoff = timezone.now() - STALE_UNCONFIRMED_AGE
        deleted, _ = queryset.filter(
            confirmed_at__isnull=True, created_at__lt=cutoff
        ).delete()
        self.message_user(
            request, f"Deleted {deleted} stale unconfirmed subscriber(s)."
        )
