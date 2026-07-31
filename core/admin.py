from django.contrib import admin

from .models import WaitlistSubscriber


@admin.register(WaitlistSubscriber)
class WaitlistSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "ip_address", "created_at")
    search_fields = ("email",)
    ordering = ("-created_at",)
    readonly_fields = ("email", "ip_address", "created_at", "updated_at")
