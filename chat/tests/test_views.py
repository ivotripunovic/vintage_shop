from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from chat.models import Conversation, Message
from chat.views import EMAIL_NOTIFY_COOLDOWN
from products.models import Product, ProductCategory
from sellers.models import Seller
from users.models import User

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def buyer(db):
    return User.objects.create_user(
        email="buyer@test.com",
        username="buyer",
        password="pass",
        is_buyer=True,
        email_verified=True,
    )


@pytest.fixture
def seller_user(db):
    return User.objects.create_user(
        email="seller@test.com",
        username="seller",
        password="pass",
        is_seller=True,
        email_verified=True,
    )


@pytest.fixture
def seller(seller_user):
    return Seller.objects.get(user=seller_user)


@pytest.fixture
def outsider(db):
    return User.objects.create_user(
        email="other@test.com",
        username="other",
        password="pass",
    )


@pytest.fixture
def category(db):
    return ProductCategory.objects.create(name="Cat", slug="cat")


@pytest.fixture
def product(seller, category):
    return Product.objects.create(
        seller=seller,
        title="Widget",
        price="50",
        category=category,
        status="published",
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

    def test_shows_unread_count_and_last_message(
        self, client, buyer, seller_user, conversation
    ):
        Message.objects.create(conversation=conversation, sender=buyer, body="Mine")
        Message.objects.create(
            conversation=conversation, sender=seller_user, body="First"
        )
        Message.objects.create(
            conversation=conversation, sender=seller_user, body="Latest"
        )
        client.force_login(buyer)
        res = client.get(reverse("chat_inbox"))
        [(conv, unread, last_msg)] = res.context["conv_list"]
        assert unread == 2
        assert last_msg["body"] == "Latest"
        assert b"Latest" in res.content

    def test_query_count_does_not_grow_with_conversations(
        self, client, buyer, seller, category, django_assert_max_num_queries
    ):
        for i in range(5):
            product = Product.objects.create(
                seller=seller, title=f"P{i}", price="1", category=category
            )
            conv = Conversation.objects.create(
                buyer=buyer, seller=seller, product=product
            )
            Message.objects.create(conversation=conv, sender=buyer, body="Hi")
        client.force_login(buyer)
        # Session, user, the annotated conversation list, plus the shared
        # page chrome; previously this was 2 extra queries per conversation
        with django_assert_max_num_queries(10):
            res = client.get(reverse("chat_inbox"))
        assert len(res.context["conv_list"]) == 5


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

    def test_shows_the_latest_100_messages_oldest_first(
        self, client, buyer, conversation
    ):
        Message.objects.bulk_create(
            Message(conversation=conversation, sender=buyer, body=f"m{i}")
            for i in range(105)
        )
        client.force_login(buyer)
        res = client.get(reverse("chat_detail", args=[conversation.pk]))
        bodies = [m.body for m in res.context["chat_messages"]]
        assert bodies == [f"m{i}" for i in range(5, 105)]
        assert res.context["last_id"] == Message.objects.latest("id").id

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

    def test_emails_the_other_participant(
        self, client, buyer, seller_user, conversation
    ):
        client.force_login(buyer)
        client.post(
            reverse("chat_send", args=[conversation.pk]), {"body": "Hey seller!"}
        )
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [seller_user.email]

    def test_does_not_email_within_cooldown(self, client, buyer, conversation):
        client.force_login(buyer)
        client.post(reverse("chat_send", args=[conversation.pk]), {"body": "First"})
        client.post(reverse("chat_send", args=[conversation.pk]), {"body": "Second"})
        assert len(mail.outbox) == 1

    def test_emails_again_after_cooldown_elapses(
        self, client, buyer, seller_user, conversation
    ):
        conversation.seller_emailed_at = (
            timezone.now() - EMAIL_NOTIFY_COOLDOWN - timedelta(seconds=1)
        )
        conversation.save(update_fields=["seller_emailed_at"])

        client.force_login(buyer)
        client.post(
            reverse("chat_send", args=[conversation.pk]), {"body": "Still here?"}
        )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [seller_user.email]

    def test_records_when_the_recipient_was_emailed(self, client, buyer, conversation):
        client.force_login(buyer)
        client.post(
            reverse("chat_send", args=[conversation.pk]), {"body": "Hey seller!"}
        )
        conversation.refresh_from_db()
        assert conversation.seller_emailed_at is not None
        assert conversation.buyer_emailed_at is None

    def test_reply_within_cooldown_still_emails_the_first_sender(
        self, client, buyer, seller_user, conversation
    ):
        # The cooldown is per recipient: emailing the seller must not stop
        # the buyer from hearing about the seller's quick reply
        client.force_login(buyer)
        client.post(reverse("chat_send", args=[conversation.pk]), {"body": "Hi"})
        client.force_login(seller_user)
        client.post(reverse("chat_send", args=[conversation.pk]), {"body": "Hello"})

        assert [m.to for m in mail.outbox] == [[seller_user.email], [buyer.email]]


# ---------------------------------------------------------------------------
# chat_poll
# ---------------------------------------------------------------------------


class TestChatPoll:
    def test_returns_new_messages(self, client, buyer, seller_user, conversation):
        msg = Message.objects.create(
            conversation=conversation, sender=seller_user, body="New msg"
        )
        client.force_login(buyer)
        res = client.get(reverse("chat_poll", args=[conversation.pk]), {"after": 0})
        assert res.status_code == 200
        data = res.json()
        assert any(m["id"] == msg.id for m in data["messages"])

    def test_after_filter(self, client, buyer, seller_user, conversation):
        m1 = Message.objects.create(
            conversation=conversation, sender=seller_user, body="A"
        )
        m2 = Message.objects.create(
            conversation=conversation, sender=seller_user, body="B"
        )
        client.force_login(buyer)
        res = client.get(reverse("chat_poll", args=[conversation.pk]), {"after": m1.id})
        data = res.json()
        ids = [m["id"] for m in data["messages"]]
        assert m1.id not in ids
        assert m2.id in ids

    def test_outsider_gets_403(self, client, outsider, conversation):
        client.force_login(outsider)
        res = client.get(reverse("chat_poll", args=[conversation.pk]), {"after": 0})
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
        assert Conversation.objects.filter(
            buyer=buyer, seller=seller, product=product
        ).exists()

    def test_get_or_create_idempotent(
        self, client, buyer, seller, product, conversation
    ):
        client.force_login(buyer)
        client.post(
            reverse("chat_start"), {"seller_id": seller.pk, "product_id": product.pk}
        )
        assert (
            Conversation.objects.filter(
                buyer=buyer, seller=seller, product=product
            ).count()
            == 1
        )

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
