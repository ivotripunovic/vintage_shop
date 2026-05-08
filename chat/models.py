from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class Conversation(TimeStampedModel):
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_conversations_as_buyer",
    )
    seller = models.ForeignKey(
        "sellers.Seller",
        on_delete=models.CASCADE,
        related_name="chat_conversations",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_conversations",
    )

    class Meta:
        ordering = ["-updated_at"]
        unique_together = [("buyer", "seller", "product")]

    def __str__(self):
        return f"{self.buyer} ↔ {self.seller} ({self.product})"

    def other_participant(self, user):
        """Return the other user in the conversation."""
        if user == self.buyer:
            return self.seller.user
        return self.buyer


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.conversation_id}] {self.sender}: {self.body[:40]}"
