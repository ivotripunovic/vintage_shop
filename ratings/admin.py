"""Admin for ratings and rating reports."""

from django.contrib import admin

from .models import Rating, RatingReport


class RatingReportInline(admin.TabularInline):
    model = RatingReport
    extra = 0
    readonly_fields = ["reporter", "reason", "created_at"]
    fields = ["reporter", "reason", "is_resolved", "created_at"]


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["sale", "direction", "author", "subject", "score", "is_hidden"]
    list_filter = ["direction", "is_hidden", "created_at"]
    search_fields = ["author__email", "subject__email", "text", "sale__product_title"]
    list_select_related = ["sale", "author", "subject"]
    raw_id_fields = ["sale", "author", "subject"]
    inlines = [RatingReportInline]
    actions = ["hide_ratings", "show_ratings"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Sakrij izabrane ocene")
    def hide_ratings(self, request, queryset):
        queryset.update(is_hidden=True)

    @admin.action(description="Ponovo prikaži izabrane ocene")
    def show_ratings(self, request, queryset):
        queryset.update(is_hidden=False)


@admin.register(RatingReport)
class RatingReportAdmin(admin.ModelAdmin):
    list_display = ["rating", "reporter", "reason", "is_resolved", "created_at"]
    list_filter = ["is_resolved", "created_at"]
    list_select_related = ["rating__author", "rating__subject", "reporter"]
    raw_id_fields = ["rating", "reporter"]
    actions = ["hide_and_resolve", "dismiss"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Sakrij ocenu i reši prijavu")
    def hide_and_resolve(self, request, queryset):
        Rating.objects.filter(reports__in=queryset).update(is_hidden=True)
        queryset.update(is_resolved=True)

    @admin.action(description="Odbaci prijavu (ocena ostaje)")
    def dismiss(self, request, queryset):
        queryset.update(is_resolved=True)
