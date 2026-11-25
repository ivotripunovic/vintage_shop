"""
Give every shop without an active subscription its starting one (#89).

Shops used to get one from the bank details page or the dashboard if they
had none (shops added in the admin, older shops). Those fallbacks are gone:
Seller.open_for and the admin now create it when the shop opens. Same terms
as Seller.create_initial_subscription: monthly, at the tier's price. No
invoice is made; invoices come only from a tier change.
"""

from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def backfill(apps, schema_editor):
    from sellers.models import DEFAULT_TIER_SETTINGS

    Seller = apps.get_model("sellers", "Seller")
    SellerTier = apps.get_model("sellers", "SellerTier")
    SellerSubscription = apps.get_model("sellers", "SellerSubscription")
    prices = dict(SellerTier.objects.values_list("tier", "monthly_price"))
    start = timezone.now().date()
    for seller in Seller.objects.exclude(subscriptions__status="active"):
        price = prices.get(seller.tier)
        if price is None:
            price = DEFAULT_TIER_SETTINGS[seller.tier]["monthly_price"]
        SellerSubscription.objects.create(
            seller=seller,
            plan_type="monthly",
            start_date=start,
            renewal_date=start + timedelta(days=30),
            status="active",
            amount=price,
        )
        print(f"\n  sellers.0006: started a subscription for shop {seller.pk}", end="")


class Migration(migrations.Migration):

    dependencies = [
        ("sellers", "0005_seller_trader_confirmation"),
    ]

    operations = [
        # Not reversed: the rows look like any other subscription
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
