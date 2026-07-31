from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from users.models import User
from sellers.models import Seller
from products.models import Product, ProductCategory
from chat.models import Conversation, Message
from chat.views import EMAIL_NOTIFY_COOLDOWN


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def buyer(db):
    return User.objects.create_user(
        email="buyer@test.com", username="buyer", password="pass",
        is_buyer=True, email_verified=True,
    )


@pytest.fixture
def seller_user(db):
    return User.objects.create_user(
        email="seller@test.com", username="seller", password="pass",
        is_seller=True, email_verified=True,
    )


@pytest.fixture
def seller(seller_user):
    return Seller.objects.get(user=seller_user)


@pytest.fixture
def outsider(db):
    return User.objects.create_user(
        email="other@test.com", username="other", password="pass",
    )


@pytest.fixture
def category(db):
    return ProductCategory.objects.create(name="Cat", slug="cat")


@pytest.fixture
def product(seller, category):
    return Product.objects.create(
        seller=seller, title="Widget", price="50",
        category=category, status="published",
    )


@pytest.fixture
def conversation(buyer, seller, product):
    return Conversation.objects.create(buyer=buyer, seller=seller, product=product)


@pytest.fixture
def message(conversation, buyer):
    return Message.objects.create(conversation=conversation, sender=buyer, body="Hello")


# ---------------------------------------------------------------------------
# chat_inbox
# ---------------------------------------------------------------------------

class TestChatInbox:
    def test_redirects_anonymous(self, client):
        res = client.get(reverse("chat_inbox"))
        assert res.status_code == 302
        assert "/auth/" in res["Location"]

    def test_buyer_sees_own_conversations(self, client, buyer, conversation):
        client.force_login(buyer)
        res = client.get(reverse("chat_inbox"))
        assert res.status_code == 200
        assert conversation in [c for c, *_ in res.context["conv_list"]]

    def test_seller_sees_own_conversations(self, client, seller_user, conversation):
        client.force_login(seller_user)
        res = client.get(reverse("chat_inbox"))
        assert res.status_code == 200
        assert conversation in [c for c, *_ in res.context["conv_list"]]

    def test_outsider_sees_nothing(self, client, outsider, conversation):
        client.force_login(outsider)
        res = client.get(reverse("chat_inbox"))
        assert res.status_code == 200
        assert res.context["conv_list"] == []


# ---------------------------------------------------------------------------
# chat_detail
# ---------------------------------------------------------------------------

class TestChatDetail:
    def test_buyer_can_view(self, client, buyer, conversation):
        client.force_login(buyer)
        res = client.get(reverse("chat_detail", args=[conversation.pk]))
        assert res.status_code == 200

    def test_seller_can_view(self, client, seller_user, conversation):
        client.force_login(seller_user)
        res = client.get(reverse("chat_detail", args=[conversation.pk]))
        assert res.status_code == 200

    def test_outsider_gets_403(self, client, outsider, conversation):
        client.force_login(outsider)
        res = client.get(reverse("chat_detail", args=[conversation.pk]))
        assert res.status_code == 403

    def test_marks_messages_read(self, client, buyer, seller_user, conversation):
        # Seller sends a message
        msg = Message.objects.create(
            conversation=conversation, sender=seller_user, body="Hi", is_read=False
        )
        # Buyer opens the thread → message should be marked read
        client.force_login(buyer)
        client.get(reverse("chat_detail", args=[conversation.pk]))
        msg.refresh_from_db()
        assert msg.is_read is True

    def test_does_not_mark_own_messages_read(self, client, buyer, conversation):
        msg = Message.objects.create(
            conversation=conversation, sender=buyer, body="Own", is_read=False
        )
        client.force_login(buyer)
        client.get(reverse("chat_detail", args=[conversation.pk]))
        msg.refresh_from_db()
        assert msg.is_read is False


# ---------------------------------------------------------------------------
# chat_send
# ---------------------------------------------------------------------------

class TestChatSend:
    def test_buyer_can_send(self, client, buyer, conversation):
        client.force_login(buyer)
        res = client.post(
            reverse("chat_send", args=[conversation.pk]),
            {"body": "Hey seller!"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["message"]["body"] == "Hey seller!"
        assert data["message"]["is_mine"] is True

    def test_seller_can_send(self, client, seller_user, conversation):
        client.force_login(seller_user)
        res = client.post(
            reverse("chat_send", args=[conversation.pk]),
            {"body": "Hi buyer!"},
        )
        assert res.status_code == 200
        assert res.json()["ok"] is True

    def test_outsider_gets_403(self, client, outsider, conversation):
        client.force_login(outsider)
        res = client.post(
            reverse("chat_send", args=[conversation.pk]),
            {"body": "Intruder"},
        )
        assert res.status_code == 403

    def test_empty_body_returns_400(self, client, buyer, conversation):
        client.force_login(buyer)
        res = client.post(
            reverse("chat_send", args=[conversation.pk]),
            {"body": ""},
        )
        assert res.status_code == 400
        assert res.json()["ok"] is False

    def test_get_not_allowed(self, client, buyer, conversation):
        client.force_login(buyer)
        res = client.get(reverse("chat_send", args=[conversation.pk]))
        assert res.status_code == 405

    def test_emails_the_other_participant(self, client, buyer, seller_user, conversation):
        client.force_login(buyer)
        client.post(reverse("chat_send", args=[conversation.pk]), {"body": "Hey seller!"})
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [seller_user.email]

    def test_does_not_email_within_cooldown(self, client, buyer, conversation):
        client.force_login(buyer)
        client.post(reverse("chat_send", args=[conversation.pk]), {"body": "First"})
        client.post(reverse("chat_send", args=[conversation.pk]), {"body": "Second"})
        assert len(mail.outbox) == 1

    def test_emails_again_after_cooldown_elapses(self, client, buyer, seller_user, conversation):
        conversation.last_emailed_at = timezone.now() - EMAIL_NOTIFY_COOLDOWN - timedelta(seconds=1)
        conversation.save(update_fields=["last_emailed_at"])

        client.force_login(buyer)
        client.post(reverse("chat_send", args=[conversation.pk]), {"body": "Still here?"})

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [seller_user.email]

    def test_updates_last_emailed_at(self, client, buyer, conversation):
        assert conversation.last_emailed_at is None
        client.force_login(buyer)
        client.post(reverse("chat_send", args=[conversation.pk]), {"body": "Hey seller!"})
        conversation.refresh_from_db()
        assert conversation.last_emailed_at is not None


# ---------------------------------------------------------------------------
# chat_poll
# ---------------------------------------------------------------------------

class TestChatPoll:
    def test_returns_new_messages(self, client, buyer, seller_user, conversation):
        msg = Message.objects.create(
            conversation=conversation, sender=seller_user, body="New msg"
        )
        client.force_login(buyer)
        res = client.get(
            reverse("chat_poll", args=[conversation.pk]), {"after": 0}
        )
        assert res.status_code == 200
        data = res.json()
        assert any(m["id"] == msg.id for m in data["messages"])

    def test_after_filter(self, client, buyer, seller_user, conversation):
        m1 = Message.objects.create(conversation=conversation, sender=seller_user, body="A")
        m2 = Message.objects.create(conversation=conversation, sender=seller_user, body="B")
        client.force_login(buyer)
        res = client.get(
            reverse("chat_poll", args=[conversation.pk]), {"after": m1.id}
        )
        data = res.json()
        ids = [m["id"] for m in data["messages"]]
        assert m1.id not in ids
        assert m2.id in ids

    def test_outsider_gets_403(self, client, outsider, conversation):
        client.force_login(outsider)
        res = client.get(
            reverse("chat_poll", args=[conversation.pk]), {"after": 0}
        )
        assert res.status_code == 403

    def test_marks_polled_messages_read(self, client, buyer, seller_user, conversation):
        msg = Message.objects.create(
            conversation=conversation, sender=seller_user, body="Unread", is_read=False
        )
        client.force_login(buyer)
        client.get(reverse("chat_poll", args=[conversation.pk]), {"after": 0})
        msg.refresh_from_db()
        assert msg.is_read is True


# ---------------------------------------------------------------------------
# chat_start
# ---------------------------------------------------------------------------

class TestChatStart:
    def test_creates_and_redirects(self, client, buyer, seller, product):
        client.force_login(buyer)
        res = client.post(
            reverse("chat_start"),
            {"seller_id": seller.pk, "product_id": product.pk},
        )
        assert res.status_code == 302
        assert Conversation.objects.filter(buyer=buyer, seller=seller, product=product).exists()

    def test_get_or_create_idempotent(self, client, buyer, seller, product, conversation):
        client.force_login(buyer)
        client.post(reverse("chat_start"), {"seller_id": seller.pk, "product_id": product.pk})
        assert Conversation.objects.filter(buyer=buyer, seller=seller, product=product).count() == 1

    def test_seller_cannot_message_self(self, client, seller_user, seller, product):
        client.force_login(seller_user)
        res = client.post(
            reverse("chat_start"),
            {"seller_id": seller.pk, "product_id": product.pk},
        )
        assert res.status_code == 400

    def test_invalid_seller_id_returns_404(self, client, buyer):
        client.force_login(buyer)
        res = client.post(reverse("chat_start"), {"seller_id": 99999})
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# chat_unread
# ---------------------------------------------------------------------------

class TestChatUnread:
    def test_returns_count(self, client, buyer, seller_user, conversation):
        Message.objects.create(
            conversation=conversation, sender=seller_user, body="Unread", is_read=False
        )
        client.force_login(buyer)
        res = client.get(reverse("chat_unread"))
        assert res.status_code == 200
        assert res.json()["count"] == 1

    def test_own_messages_not_counted(self, client, buyer, conversation):
        Message.objects.create(
            conversation=conversation, sender=buyer, body="Mine", is_read=False
        )
        client.force_login(buyer)
        res = client.get(reverse("chat_unread"))
        assert res.json()["count"] == 0
