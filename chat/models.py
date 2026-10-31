from django.conf import settings
from django.db import models

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
    # When each side was last emailed about new messages; tracked per
    # recipient so one side's notification doesn't silence the other's
    buyer_emailed_at = models.DateTimeField(null=True, blank=True)
    seller_emailed_at = models.DateTimeField(null=True, blank=True)
    # Started by an admin from the review queue; the admin sits on the buyer side
    is_team = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = [("buyer", "seller", "product")]

    def __str__(self):
        return f"{self.buyer} ↔ {self.seller} ({self.product})"

    # Participants are shown by name, never by email, so contact details
    # aren't handed out and deals stay on the platform

    @property
    def buyer_label(self):
        """Name shown for the buyer side: first name, or the team name."""
        if self.is_team:
            return f"Tim {settings.SITE_NAME}"
        return self.buyer.first_name or "Kupac"

    @property
    def seller_label(self):
        return self.seller.shop_name

    def label_for(self, user):
        """Public name of a participant in this conversation."""
        if user.pk == self.buyer_id:
            return self.buyer_label
        return self.seller_label

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
