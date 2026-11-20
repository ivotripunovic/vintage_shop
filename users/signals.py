from allauth.account.signals import email_confirmed
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .email_sync import SYNCED_FIELDS, sync_primary_email
from .models import User


@receiver(post_save, sender=User)
def sync_allauth_email_address(
    sender, instance, created, update_fields=None, raw=False, **kwargs
):
    """Mirror the user's email and verification state into allauth (#76).

    New users are skipped: allauth's own signup creates their EmailAddress
    right after the first save (setup_user_email asserts there is none yet).
    The custom register views call sync_primary_email themselves.
    """
    if raw or created:  # loaddata, or a new user
        return
    if update_fields is not None and not SYNCED_FIELDS & set(update_fields):
        return  # e.g. login() saving last_login
    sync_primary_email(instance)


@receiver(email_confirmed)
def mark_user_email_verified(sender, request, email_address, **kwargs):
    """An address confirmed through allauth counts for the custom login too."""
    user = email_address.user
    if user.email.lower() == email_address.email.lower() and not user.email_verified:
        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified", "email_verified_at"])
