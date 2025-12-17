"""
User model for authentication (buyers and sellers use same User model).
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


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


class VerificationToken(models.Model):
    """Temporary token for email verification and password reset."""
    
    TOKEN_TYPE_EMAIL = 'email_verification'
    TOKEN_TYPE_PASSWORD = 'password_reset'
    
    TOKEN_TYPES = [
        (TOKEN_TYPE_EMAIL, 'Email Verification'),
        (TOKEN_TYPE_PASSWORD, 'Password Reset'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_tokens')
    token = models.CharField(max_length=100, unique=True)
    token_type = models.CharField(max_length=20, choices=TOKEN_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.token_type}"
    
    def is_expired(self):
        """Check if token has expired."""
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Check if token is valid (not expired and not used)."""
        return not self.is_expired() and not self.is_used
    
    def mark_used(self):
        """Mark token as used."""
        self.is_used = True
        self.used_at = timezone.now()
        self.save()
