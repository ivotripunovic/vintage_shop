"""Admin configuration for billing app."""

from django.contrib import admin
from django.utils.html import format_html
from .models import Invoice, Payment, BillingPlan


@admin.register(BillingPlan)
class BillingPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "plan_type", "is_active"]
    list_filter = ["plan_type", "is_active"]


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0
    readonly_fields = ["created_at", "updated_at", "verified_at", "verified_by"]
    fields = ["amount", "verified_at", "verified_by", "bank_reference", "notes"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "seller", "amount", "status", "due_date", "days_until_due_display"]
    list_filter = ["status", "created_at", "due_date"]
    search_fields = ["invoice_number", "seller__shop_name", "seller__user__email"]
    readonly_fields = ["created_at", "updated_at", "invoice_number"]
    inlines = [PaymentInline]
    fieldsets = (
        ("Invoice Information", {
            "fields": ("invoice_number", "seller", "amount", "billing_plan")
        }),
        ("Period", {
            "fields": ("period_start", "period_end")
        }),
        ("Due Date & Status", {
            "fields": ("due_date", "status")
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at")
        }),
    )

    def days_until_due_display(self, obj):
        """Display days until due with color coding."""
        days = obj.days_until_due
        if obj.is_overdue:
            color = "red"
            text = f"OVERDUE ({days} days)"
        elif days <= 3:
            color = "orange"
            text = f"{days} days"
        else:
            color = "green"
            text = f"{days} days"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, text
        )
    days_until_due_display.short_description = "Days Until Due"

    actions = ["mark_overdue", "mark_verified"]

    def mark_overdue(self, request, queryset):
        """Admin action to mark invoices as overdue."""
        for invoice in queryset:
            invoice.mark_overdue()
        self.message_user(request, f"{queryset.count()} invoice(s) marked as overdue.")
    mark_overdue.short_description = "Mark selected invoices as overdue"

    def mark_verified(self, request, queryset):
        """Admin action to mark invoices as verified."""
        for invoice in queryset:
            invoice.mark_verified()
        self.message_user(request, f"{queryset.count()} invoice(s) marked as verified.")
    mark_verified.short_description = "Mark selected invoices as verified"
