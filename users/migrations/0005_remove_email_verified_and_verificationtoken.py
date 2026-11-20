"""
Drop User.email_verified / email_verified_at and VerificationToken (#79).

allauth's EmailAddress is now the only record of verification. The #76 sync
kept the two in step, but before the columns go, every user still flagged
verified gets a verified primary EmailAddress for their login email (unless
another account already holds that address verified), so nobody loses their
verified state. VerificationToken only served the old custom links.
"""

from django.db import migrations


def reconcile(apps, schema_editor):
    User = apps.get_model("users", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")
    for user in User.objects.filter(email_verified=True).exclude(email="").iterator():
        email = user.email.lower()
        taken = (
            EmailAddress.objects.filter(email__iexact=email, verified=True)
            .exclude(user=user)
            .exists()
        )
        if taken:
            # Left unverified; listed in the deploy output for a manual check
            print(
                f"\n  users.0005: user {user.pk} stays unverified, {email} is "
                "verified for another account",
                end="",
            )
            continue
        EmailAddress.objects.filter(user=user, primary=True).exclude(
            email__iexact=email
        ).update(primary=False)
        address = EmailAddress.objects.filter(user=user, email__iexact=email).first()
        if address is None:
            EmailAddress.objects.create(
                user=user, email=email, primary=True, verified=True
            )
        else:
            address.verified = True
            address.primary = True
            address.save(update_fields=["verified", "primary"])


def restore_flag(apps, schema_editor):
    """Reverse: rebuild email_verified from allauth's rows."""
    User = apps.get_model("users", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")
    for user in User.objects.exclude(email="").iterator():
        if EmailAddress.objects.filter(
            user=user, email__iexact=user.email, verified=True
        ).exists():
            User.objects.filter(pk=user.pk).update(email_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_backfill_allauth_email_addresses"),
        ("account", "0009_emailaddress_unique_primary_email"),
    ]

    operations = [
        migrations.RunPython(reconcile, restore_flag),
        migrations.RemoveField(
            model_name="user",
            name="email_verified",
        ),
        migrations.RemoveField(
            model_name="user",
            name="email_verified_at",
        ),
        migrations.DeleteModel(
            name="VerificationToken",
        ),
    ]
