"""
Drop User.is_buyer and User.is_seller (#89).

Every account can buy, and a seller is now a user with a shop (a
sellers.Seller row); User.is_seller is a property over that. Shops are
already Seller rows, so nobody loses one. Before the column goes, any user
flagged seller without a Seller row is listed in the deploy output: such a
user stops being a seller and can open a shop again from "Dodaj oglas".
"""

from django.db import migrations


def flagged_sellers_without_shop(apps):
    """Users with is_seller=True and no Seller row, by pk."""
    User = apps.get_model("users", "User")
    Seller = apps.get_model("sellers", "Seller")
    shops = Seller.objects.values("user_id")
    return list(
        User.objects.filter(is_seller=True)
        .exclude(pk__in=shops)
        .order_by("pk")
        .values_list("pk", "email")
    )


def list_sellers_without_shop(apps, schema_editor):
    for pk, email in flagged_sellers_without_shop(apps):
        print(
            f"\n  users.0006: user {pk} ({email}) was flagged seller but has "
            "no shop; they are no longer a seller",
            end="",
        )


def restore_flags(apps, schema_editor):
    """Reverse: a user with a shop is a seller again."""
    User = apps.get_model("users", "User")
    Seller = apps.get_model("sellers", "Seller")
    User.objects.filter(pk__in=Seller.objects.values("user_id")).update(is_seller=True)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_remove_email_verified_and_verificationtoken"),
        ("sellers", "0005_seller_trader_confirmation"),
    ]

    operations = [
        # Reversed last, once the columns are back (is_buyer defaults True)
        migrations.RunPython(list_sellers_without_shop, restore_flags),
        migrations.RemoveField(model_name="user", name="is_buyer"),
        migrations.RemoveField(model_name="user", name="is_seller"),
    ]
