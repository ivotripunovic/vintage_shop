from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("sender", "body", "created_at", "is_read")
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "buyer", "seller", "product", "message_count", "updated_at")
    list_filter = ("seller",)
    search_fields = ("buyer__email", "seller__shop_name", "product__title")
    readonly_fields = ("created_at", "updated_at")
    inlines = [MessageInline]

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = "Poruka"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "body_preview", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("sender__email", "body")
    readonly_fields = ("created_at",)

    def body_preview(self, obj):
        return obj.body[:60]
    body_preview.short_description = "Poruka"
