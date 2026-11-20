from allauth.account.signals import email_confirmed
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .email_sync import SYNCED_FIELDS, sync_primary_email
from .models import User

# Set on a User instance by our allauth adapters while allauth signs it up:
# allauth then creates the EmailAddress rows itself (setup_user_email asserts
# there are none yet), so the sync must wait for the adapter's own save.
SKIP_SYNC_ATTR = "_allauth_signup_in_progress"


def _syncs(update_fields):
    return update_fields is None or bool(SYNCED_FIELDS & set(update_fields))


@receiver(pre_save, sender=User)
def remember_previous_email(sender, instance, update_fields=None, raw=False, **kwargs):
    if raw or instance.pk is None or not _syncs(update_fields):
        return
    instance._previous_email = (
        User.objects.filter(pk=instance.pk).values_list("email", flat=True).first()
    )


@receiver(post_save, sender=User)
def sync_allauth_email_address(
    sender, instance, created, update_fields=None, raw=False, **kwargs
):
    """Mirror the user's email and verification state into allauth (#76)."""
    if raw or getattr(instance, SKIP_SYNC_ATTR, False):  # loaddata, allauth signup
        return
    if not created and not _syncs(update_fields):
        return  # e.g. login() saving last_login
    sync_primary_email(instance, getattr(instance, "_previous_email", None))


@receiver(email_confirmed)
def mark_user_email_verified(sender, request, email_address, **kwargs):
    """An address confirmed through allauth counts for the custom login too."""
    user = email_address.user
    if user.email.lower() == email_address.email.lower() and not user.email_verified:
        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified", "email_verified_at"])
