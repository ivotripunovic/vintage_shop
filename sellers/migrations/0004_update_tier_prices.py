from decimal import Decimal

from django.db import migrations

NEW_PRICES = {
    "premijum": (Decimal("7000"), Decimal("9000")),
    "odrzivo": (Decimal("1000"), Decimal("6500")),
}


def set_prices(apps, schema_editor, index):
    SellerTier = apps.get_model("sellers", "SellerTier")
    for tier, prices in NEW_PRICES.items():
        SellerTier.objects.filter(tier=tier).update(monthly_price=prices[index])


def forwards(apps, schema_editor):
    set_prices(apps, schema_editor, 1)


def backwards(apps, schema_editor):
    set_prices(apps, schema_editor, 0)


class Migration(migrations.Migration):

    dependencies = [
        ("sellers", "0003_sellertier_seller_tier"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
