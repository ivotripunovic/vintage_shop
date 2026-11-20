"""
Keep allauth's EmailAddress in step with User.email / User.email_verified.

The custom auth flow (users/views.py) records verification on the User, while
allauth reads EmailAddress. Until the custom flow is replaced (#77), every
saved user has a primary EmailAddress for their current email:

- Stored lowercased, as allauth stores and looks up addresses.
- Verified if either side says so, and the User flag is raised to match.
  An existing address is never quietly un-verified: a stale User instance
  saved with email_verified=False must not undo an allauth confirmation.
  Changing the email starts a new, unverified address (callers that change
  it reset email_verified, see SellerAccountSettingsForm).
- Never verified for two users at once (allauth's unique_verified_email).
  Users whose emails differ only in case keep the first verified owner and
  log a warning instead of failing the save.

Other rows the user owns (for example extra verified emails from a social
provider) are left alone; only the row for a previous email is removed.
See docs/features/auth-allauth-migration.md.
"""

import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

SYNCED_FIELDS = {"email", "email_verified"}


def sync_primary_email(user, previous_email=None):
    from allauth.account.models import EmailAddress

    email = (user.email or "").lower()
    with transaction.atomic():
        if previous_email and previous_email.lower() != email:
            EmailAddress.objects.filter(
                user=user, email__iexact=previous_email
            ).delete()
        if not email:
            EmailAddress.objects.filter(user=user).delete()
            return

        # Another user's leftover row for this email (not their current
        # email) would block the verified row below; this user owns it now.
        EmailAddress.objects.filter(email__iexact=email).exclude(user=user).exclude(
            user__email__iexact=email
        ).delete()
        rows = list(EmailAddress.objects.filter(user=user))
        address = next((r for r in rows if r.email.lower() == email), None)
        stale_primary = [r.pk for r in rows if r.primary and r is not address]
        if stale_primary:
            EmailAddress.objects.filter(pk__in=stale_primary).update(primary=False)

        verified = user.email_verified or bool(address and address.verified)
        if (
            verified
            and EmailAddress.objects.filter(email__iexact=email, verified=True)
            .exclude(user=user)
            .exists()
        ):
            logger.warning(
                "User %s: %s is already verified for another account "
                "(emails differing only in case); leaving it unverified here",
                user.pk,
                email,
            )
            verified = False

        if address is None:
            EmailAddress.objects.create(
                user=user, email=email, primary=True, verified=verified
            )
        elif (address.email, address.primary, address.verified) != (
            email,
            True,
            verified,
        ):
            address.email = email
            address.primary = True
            address.verified = verified
            address.save(update_fields=["email", "primary", "verified"])

        if verified and not user.email_verified:
            # allauth verified it; let the custom login accept it too.
            # update() avoids re-running post_save.
            now = timezone.now()
            type(user).objects.filter(pk=user.pk).update(
                email_verified=True, email_verified_at=now
            )
            user.email_verified = True
            user.email_verified_at = now
