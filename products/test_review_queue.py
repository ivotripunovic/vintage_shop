"""
Tests for the admin "New ads for review" queue and team chat threads.
"""

from decimal import Decimal

import pytest
from django.core import mail
from django.urls import reverse

from chat.models import Conversation
from products.models import Product
from users.models import User

QUEUE_URL = reverse("admin:products_newad_changelist")


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@test.com",
        username="admin",
        password="pass",
        is_staff=True,
        is_superuser=True,
        email_verified=True,
    )


@pytest.fixture
def seller(db):
    user = User.objects.create_user(
        email="seller@test.com",
        username="seller",
        password="pass",
        is_seller=True,
        email_verified=True,
    )
    return user.seller_profile


def _product(seller, title, status="published"):
    return Product.objects.create(
        seller=seller,
        title=title,
        description="Opis",
        price=Decimal("1000"),
        status=status,
    )


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


def test_queue_lists_published_ads_only(admin_client, seller):
    _product(seller, "Live lamp")
    _product(seller, "Draft lamp", status="draft")
    _product(seller, "Deleted lamp").soft_delete()

    response = admin_client.get(QUEUE_URL)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Live lamp" in content
    assert "Draft lamp" not in content
    assert "Deleted lamp" not in content


def test_queue_shows_unreviewed_first(admin_client, admin_user, seller):
    reviewed = _product(seller, "Reviewed chair")
    _product(seller, "Fresh chair")
    Product.objects.filter(pk=reviewed.pk).update(
        reviewed_at=reviewed.listed_at, reviewed_by=admin_user
    )

    content = admin_client.get(QUEUE_URL).content.decode()

    assert content.index("Fresh chair") < content.index("Reviewed chair")


def test_mark_reviewed_action(admin_client, admin_user, seller):
    product = _product(seller, "Mirror")

    admin_client.post(
        QUEUE_URL, {"action": "mark_reviewed", "_selected_action": [product.pk]}
    )

    product.refresh_from_db()
    assert product.reviewed_at is not None
    assert product.reviewed_by == admin_user


def test_message_seller_starts_team_thread(admin_client, admin_user, seller):
    product = _product(seller, "Clock")

    response = admin_client.post(
        QUEUE_URL, {"action": "message_seller", "_selected_action": [product.pk]}
    )

    conversation = Conversation.objects.get(buyer=admin_user, product=product)
    assert conversation.is_team
    assert response.status_code == 302
    assert response.url == reverse("chat_detail", args=[conversation.pk])


def test_message_seller_needs_exactly_one_ad(admin_client, seller):
    first = _product(seller, "Vase")
    second = _product(seller, "Bowl")

    admin_client.post(
        QUEUE_URL,
        {"action": "message_seller", "_selected_action": [first.pk, second.pk]},
    )

    assert not Conversation.objects.exists()


def test_team_thread_hides_admin_email_from_seller(client, admin_user, seller):
    product = _product(seller, "Radio")
    conversation = Conversation.objects.create(
        buyer=admin_user, seller=seller, product=product, is_team=True
    )
    conversation.messages.create(sender=admin_user, body="Dodajte više slika.")
    client.force_login(seller.user)

    inbox = client.get(reverse("chat_inbox")).content.decode()
    detail = client.get(reverse("chat_detail", args=[conversation.pk])).content.decode()

    assert "Tim " in inbox
    assert "admin@test.com" not in inbox
    assert "admin@test.com" not in detail


def test_team_message_email_names_the_team(admin_client, admin_user, seller):
    product = _product(seller, "Typewriter")
    conversation = Conversation.objects.create(
        buyer=admin_user, seller=seller, product=product, is_team=True
    )

    admin_client.post(
        reverse("chat_send", args=[conversation.pk]), {"body": "Savet: bolja slika."}
    )

    assert len(mail.outbox) == 1
    assert "admin@test.com" not in mail.outbox[0].body
    assert conversation.buyer_label in mail.outbox[0].body
