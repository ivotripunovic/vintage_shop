import pytest
from django.db.utils import IntegrityError

from users.models import User
from sellers.models import Seller
from products.models import Product, ProductCategory
from chat.models import Conversation, Message


@pytest.fixture
def buyer(db):
    return User.objects.create_user(
        email="buyer@example.com", username="buyer", password="pass", is_buyer=True
    )


@pytest.fixture
def seller_user(db):
    return User.objects.create_user(
        email="seller@example.com",
        username="seller",
        password="pass",
        is_seller=True,
        email_verified=True,
    )


@pytest.fixture
def seller(seller_user):
    return Seller.objects.get(user=seller_user)


@pytest.fixture
def category(db):
    return ProductCategory.objects.create(name="Test", slug="test")


@pytest.fixture
def product(seller, category):
    return Product.objects.create(
        seller=seller,
        title="Test Product",
        price="100",
        category=category,
        status="published",
    )


@pytest.fixture
def conversation(buyer, seller, product):
    return Conversation.objects.create(buyer=buyer, seller=seller, product=product)


class TestConversation:
    def test_str(self, conversation, buyer, seller, product):
        assert str(buyer.email) in str(conversation)
        assert str(seller) in str(conversation)

    def test_unique_together(self, buyer, seller, product):
        Conversation.objects.create(buyer=buyer, seller=seller, product=product)
        with pytest.raises(IntegrityError):
            Conversation.objects.create(buyer=buyer, seller=seller, product=product)

    def test_other_participant_from_buyer(self, conversation, buyer, seller):
        assert conversation.other_participant(buyer) == seller.user

    def test_other_participant_from_seller(self, conversation, buyer, seller):
        assert conversation.other_participant(seller.user) == buyer

    def test_product_nullable(self, buyer, seller):
        c = Conversation.objects.create(buyer=buyer, seller=seller, product=None)
        assert c.product is None

    def test_product_set_null_on_delete(self, conversation, product):
        product.delete()
        conversation.refresh_from_db()
        assert conversation.product is None


class TestMessage:
    def test_create_message(self, conversation, buyer):
        msg = Message.objects.create(
            conversation=conversation, sender=buyer, body="Hello!"
        )
        assert msg.is_read is False
        assert msg.body == "Hello!"

    def test_message_ordering(self, conversation, buyer, seller):
        m1 = Message.objects.create(conversation=conversation, sender=buyer, body="A")
        m2 = Message.objects.create(conversation=conversation, sender=seller.user, body="B")
        messages = list(conversation.messages.all())
        assert messages[0] == m1
        assert messages[1] == m2

    def test_str(self, conversation, buyer):
        msg = Message.objects.create(
            conversation=conversation, sender=buyer, body="Hi there"
        )
        assert "Hi there" in str(msg)

    def test_body_max_length(self, conversation, buyer):
        long_body = "x" * 2000
        msg = Message.objects.create(conversation=conversation, sender=buyer, body=long_body)
        assert len(msg.body) == 2000
