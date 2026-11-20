"""
Keep allauth's EmailAddress in step with User.email / User.email_verified.

The custom auth flow (users/views.py) records verification on the User, while
allauth reads EmailAddress. Until the custom flow is replaced (#77), every
saved user has a primary EmailAddress for their current email:

- Stored lowercased, as allauth stores and looks up addresses.
- Verified if either side says so, and the User flag is raised to match.
  An existing address is never quietly un-verified: a stale User instance
  saved with email_verified=False must not undo an allauth confirmation.
- Changing the email (seller settings, admin, shell) makes the new address
  unverified, and User.email_verified follows it, unless allauth already
  holds that address verified for this user.
- Never verified for two users at once (allauth's unique_verified_email).
  If another account holds it verified (a case-variant duplicate, or a
  social provider's extra email), it stays unverified here and a warning is
  logged; the other account's row is never deleted.

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
    email_changed = bool(previous_email) and previous_email.lower() != email
    with transaction.atomic():
        if email_changed:
            EmailAddress.objects.filter(
                user=user, email__iexact=previous_email
            ).delete()
            # Links sent to the old address must not verify the new one, or
            # reset the password of an account that has moved on
            user.verification_tokens.filter(is_used=False).update(
                is_used=True, used_at=timezone.now()
            )
        if not email:
            EmailAddress.objects.filter(user=user).delete()
            return

        # Another user's unverified leftover row for this email (not their
        # current email). A *verified* one is theirs to keep, for example an
        # extra address from their social provider; it then blocks
        # verification here (below) instead of being deleted.
        EmailAddress.objects.filter(email__iexact=email, verified=False).exclude(
            user=user
        ).exclude(user__email__iexact=email).delete()

        rows = list(EmailAddress.objects.filter(user=user))
        address = next((r for r in rows if r.email.lower() == email), None)
        stale_primary = [r.pk for r in rows if r.primary and r is not address]
        if stale_primary:
            EmailAddress.objects.filter(pk__in=stale_primary).update(primary=False)

        if email_changed:
            # The User flag belonged to the old address; only a row that is
            # already verified (e.g. allauth making a secondary primary) counts
            verified = bool(address and address.verified)
        else:
            verified = user.email_verified or bool(address and address.verified)
        if (
            verified
            and EmailAddress.objects.filter(email__iexact=email, verified=True)
            .exclude(user=user)
            .exists()
        ):
            logger.warning(
                "User %s: %s is already verified for another account; "
                "leaving it unverified here",
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

        if verified != user.email_verified:
            # Keep the custom login in step. update() avoids re-running
            # post_save. Lowering only happens on an email change (above).
            verified_at = timezone.now() if verified else None
            type(user).objects.filter(pk=user.pk).update(
                email_verified=verified, email_verified_at=verified_at
            )
            user.email_verified = verified
            user.email_verified_at = verified_at
