"""
Give every user one primary allauth EmailAddress matching User.email (#76).

Email verification was recorded on User.email_verified by the custom flow and
on EmailAddress.verified by allauth, so most users had no EmailAddress and
allauth asked already-verified users to verify again. An address counts as
verified if either side says so, and the User flag is raised to match.

The logic is copied from users/email_sync.py on purpose: migrations must keep
working with historical models even if that module changes later.
"""

from django.db import migrations
from django.db.models import F
from django.db.models.functions import Lower
from django.utils import timezone


def backfill(apps, schema_editor):
    User = apps.get_model("users", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")

    # Rows for an email the user no longer has. Removing them first means the
    # upserts below cannot collide with another user's stale verified row.
    EmailAddress.objects.annotate(lower_email=Lower("email")).exclude(
        lower_email=Lower(F("user__email"))
    ).delete()

    now = timezone.now()
    for user in User.objects.exclude(email="").iterator():
        address = EmailAddress.objects.filter(
            user=user, email__iexact=user.email
        ).first()
        verified = user.email_verified or bool(address and address.verified)
        if address is None:
            EmailAddress.objects.create(
                user=user, email=user.email, primary=True, verified=verified
            )
        else:
            address.email = user.email
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
