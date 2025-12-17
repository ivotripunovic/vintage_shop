"""
Django signals for sellers app.
Auto-creates Seller profile when a User is created with is_seller=True.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now
from datetime import timedelta
from users.models import User
from .models import Seller, SellerSubscription


@receiver(post_save, sender=User)
def create_seller_profile(sender, instance, created, **kwargs):
    """
    Create a Seller profile when a new User is created with is_seller=True.
    """
    if created and instance.is_seller:
        # Create seller profile if it doesn't exist
        if not hasattr(instance, 'seller_profile'):
            seller = Seller.objects.create(
                user=instance,
                shop_name=instance.email.split('@')[0],  # Use email prefix as default shop name
                shop_slug=instance.email.split('@')[0].replace('.', '-'),  # Slug version
            )
            
            # Create initial subscription
            start_date = now().date()
            renewal_date = start_date + timedelta(days=30)
            SellerSubscription.objects.create(
                seller=seller,
                plan_type='monthly',
                start_date=start_date,
                renewal_date=renewal_date,
                status='active',
                amount=9.99
            )
