"""
User model for authentication (buyers and sellers use same User model).

Signup, login, email verification and password flows are django-allauth's;
whether an email is verified lives in allauth's EmailAddress (#79).
"""

import logging

from django.contrib.auth.models import AbstractUser
from django.db import models

logger = logging.getLogger(__name__)


class User(AbstractUser):
    """
    Custom User model with email as unique identifier.
    Can be either a buyer or seller (or both).
    """

    email = models.EmailField(unique=True)
    is_seller = models.BooleanField(default=False)
    is_buyer = models.BooleanField(default=True)
    # Buyer profile; sellers use their shop image and description instead
    profile_picture = models.ImageField(
        upload_to="profile_pictures/", blank=True, null=True
    )
    bio = models.CharField(max_length=300, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-date_joined"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email

    @property
    def email_verified(self):
        """allauth holds the login email as a verified address."""
        from allauth.account.models import EmailAddress

        if not self.pk or not self.email:
            return False
        return EmailAddress.objects.filter(
            user=self, email__iexact=self.email, verified=True
        ).exists()

    def mark_email_verified(self):
        """Record the login email as verified and primary in allauth.

        For code that proves ownership outside allauth's own confirmation
        flow (a social provider vouching for it, seeding, tests). Returns
        False, and changes nothing, if another account already holds the
        address verified (allauth allows one verified owner per address).
        """
        from allauth.account.models import EmailAddress

        email = self.email.lower()
        if (
            EmailAddress.objects.filter(email__iexact=email, verified=True)
            .exclude(user=self)
            .exists()
        ):
            logger.warning(
                "User %s: %s is verified for another account; not marking it",
                self.pk,
                email,
            )
            return False
        self.set_primary_email(verified=True)
        return True

    def set_primary_email(self, verified=False):
        """Make allauth's primary address match the login email.

        Called when User.email is changed outside allauth (the admin); the
        new address is unverified unless ``verified``. allauth's own email
        change flow (/auth/email/) does this itself.
        """
        from allauth.account.models import EmailAddress

        email = self.email.lower()
        EmailAddress.objects.filter(user=self, primary=True).exclude(
            email__iexact=email
        ).update(primary=False)
        address = EmailAddress.objects.filter(user=self, email__iexact=email).first()
        if address is None:
            EmailAddress.objects.create(
                user=self, email=email, primary=True, verified=verified
            )
        elif not address.primary or (verified and not address.verified):
            address.primary = True
            address.verified = address.verified or verified
            address.save(update_fields=["verified", "primary"])

    def has_complete_seller_profile(self):
        """Check if user has a complete seller profile."""
        if not self.is_seller:
            return False
        return hasattr(self, "seller_profile") and self.seller_profile is not None
