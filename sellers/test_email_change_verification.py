"""Changing the email in seller settings must re-verify it (review of #85)."""

import pytest
from allauth.account.models import EmailAddress
from django.core import mail
from django.urls import reverse

from users.models import User


@pytest.mark.django_db
def test_seller_email_change_resets_verification_and_sends_link(
    client, django_capture_on_commit_callbacks
):
    user = User.objects.create_user(
        email="old@example.com",
        username="old@example.com",
        password="Pw-strong-123",
        is_seller=True,
    )
    user.email_verified = True
    user.save()
    client.force_login(user)
    data = {"shop_name": user.seller_profile.shop_name, "email": "new@example.com"}
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(reverse("seller_settings"), data)
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.email == "new@example.com"
    assert not user.email_verified
    assert list(
        EmailAddress.objects.filter(user=user).values_list("email", "verified")
    ) == [("new@example.com", False)]
    assert [m.to for m in mail.outbox] == [["new@example.com"]]
