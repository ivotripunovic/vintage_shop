"""
Keep allauth's EmailAddress in step with User.email / User.email_verified.

The custom auth flow (users/views.py) records verification on the User, while
allauth reads EmailAddress. Until the custom flow is replaced (#77), every
user has exactly one EmailAddress: primary, for their current email, and
verified exactly when User.email_verified is. Each side wins on its own event:

- saving the User mirrors it into EmailAddress (users.signals), and
- confirming through allauth sets User.email_verified (users.signals).

The one-off backfill (migration 0004) reconciles existing data instead.
See docs/features/auth-allauth-migration.md.
"""

from django.db import transaction

SYNCED_FIELDS = {"email", "email_verified"}


def sync_primary_email(user):
    from allauth.account.models import EmailAddress

    if not user.email:
        return
    with transaction.atomic():
        # One address per user: drop rows left over from an earlier email
        EmailAddress.objects.filter(user=user).exclude(
            email__iexact=user.email
        ).delete()
        # ...including another user's leftover row for this email, which would
        # break allauth's unique verified-email constraint. Rows for another
        # user's *current* email are kept (User.email is unique, so that only
        # differs in case).
        EmailAddress.objects.filter(email__iexact=user.email).exclude(
            user=user
        ).exclude(user__email__iexact=user.email).delete()
        address = EmailAddress.objects.filter(
            user=user, email__iexact=user.email
        ).first()
        if address is None:
            EmailAddress.objects.create(
                user=user,
                email=user.email,
                primary=True,
                verified=user.email_verified,
            )
        elif (address.email, address.primary, address.verified) != (
            user.email,
            True,
            user.email_verified,
        ):
            address.email = user.email
            address.primary = True
            address.verified = user.email_verified
            address.save(update_fields=["email", "primary", "verified"])
