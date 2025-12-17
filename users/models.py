"""
User model for authentication (buyers and sellers use same User model).
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
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-date_joined"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email

    def has_complete_seller_profile(self):
        """Check if user has a complete seller profile."""
        if not self.is_seller:
            return False
        return hasattr(self, "seller_profile") and self.seller_profile is not None
