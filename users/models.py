"""
User model for authentication (buyers and sellers use same User model).

Signup, login, email verification and password flows are django-allauth's;
whether an email is verified lives in allauth's EmailAddress (#79).
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


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
        flow (a social provider vouching for it, seeding, tests).
        """
        from allauth.account.models import EmailAddress

        email = self.email.lower()
        EmailAddress.objects.filter(user=self, primary=True).exclude(
            email__iexact=email
        ).update(primary=False)
        address = EmailAddress.objects.filter(user=self, email__iexact=email).first()
        if address is None:
            EmailAddress.objects.create(
                user=self, email=email, primary=True, verified=True
            )
        elif not (address.verified and address.primary):
            address.verified = True
            address.primary = True
            address.save(update_fields=["verified", "primary"])

    def has_complete_seller_profile(self):
        """Check if user has a complete seller profile."""
        if not self.is_seller:
            return False
        return hasattr(self, "seller_profile") and self.seller_profile is not None
