"""
Give every user a primary allauth EmailAddress matching User.email (#76).

Email verification was recorded on User.email_verified by the custom flow and
on EmailAddress.verified by allauth, so most users had no EmailAddress and
allauth asked already-verified users to verify again.

Same rules as users/email_sync.py, whose logic is copied on purpose so this
migration keeps working with historical models if that module changes:
addresses are stored lowercased, an address is verified if either side was
(and the User flag is raised to match), an address is never verified for two
users (for emails differing only in case, the first user to hold it
verified keeps it), rows for another
user's email are removed, and other rows a user owns are kept as secondaries.
"""

from django.db import migrations
from django.utils import timezone


def backfill(apps, schema_editor):
    User = apps.get_model("users", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")

    # Rows for an email that belongs to a different user now. Removing them
    # first means the rows below cannot collide with a stale verified row.
    for owner in User.objects.exclude(email="").iterator():
        EmailAddress.objects.filter(email__iexact=owner.email).exclude(
            user=owner
        ).exclude(user__email__iexact=owner.email).delete()

    now = timezone.now()
    for user in User.objects.exclude(email="").order_by("pk").iterator():
        email = user.email.lower()
        EmailAddress.objects.filter(user=user, primary=True).exclude(
            email__iexact=email
        ).update(primary=False)
        address = EmailAddress.objects.filter(user=user, email__iexact=email).first()
        verified = user.email_verified or bool(address and address.verified)
        if (
            verified
            and EmailAddress.objects.filter(email__iexact=email, verified=True)
            .exclude(user=user)
            .exists()
        ):
            verified = False
        if address is None:
            EmailAddress.objects.create(
                user=user, email=email, primary=True, verified=verified
            )
        else:
            address.email = email
            address.primary = True
            address.verified = verified
            address.save(update_fields=["email", "primary", "verified"])
        if verified and not user.email_verified:
            User.objects.filter(pk=user.pk).update(
                email_verified=True, email_verified_at=now
            )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_user_profile_picture_bio"),
        ("account", "0009_emailaddress_unique_primary_email"),
    ]

    operations = [
        # Nothing to undo: the rows are what allauth expects anyway
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
