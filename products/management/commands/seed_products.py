import random
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta

from users.models import User
from sellers.models import Seller, SellerSubscription
from products.models import Product, ProductCategory, ProductCondition, ProductImage
from products.management.seed_data import CONDITIONS, SELLERS, PRODUCTS

SEED_IMAGES_DIR = Path(settings.BASE_DIR) / "seed_data" / "product_images"


class Command(BaseCommand):
    help = "Seed conditions, sellers and products. Run seed_categories first."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all products, conditions and seed sellers before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            Product.objects.all().delete()
            ProductCondition.objects.all().delete()
            seed_shop_names = [s["shop_name"] for s in SELLERS]
            Seller.objects.filter(shop_name__in=seed_shop_names).delete()
            User.objects.filter(email__endswith="@seed.vs").delete()
            User.objects.filter(email__regex=r"^seller\d+@example\.com$").delete()
            self.stdout.write(self.style.WARNING("Cleared products, conditions and seed sellers."))

        if not ProductCategory.objects.filter(parent__isnull=False).exists():
            self.stdout.write(self.style.ERROR(
                "No subcategories found. Run `python manage.py seed_categories` first."
            ))
            return

        images_available = SEED_IMAGES_DIR.exists()
        if not images_available:
            self.stdout.write(self.style.WARNING(
                "No images found. Run `python manage.py download_seed_images --key <KEY>` first."
            ))

        conditions = self._seed_conditions()
        sellers = self._seed_sellers()
        self._seed_products(sellers, conditions, images_available)

    def _seed_conditions(self):
        created = 0
        conditions = {}
        for data in CONDITIONS:
            obj, is_new = ProductCondition.objects.get_or_create(
                name=data["name"],
                defaults={"description": data["description"], "order": data["order"]},
            )
            conditions[data["name"]] = obj
            if is_new:
                created += 1
        self.stdout.write(f"Stanja: {created} kreirana, {len(CONDITIONS) - created} već postoje.")
        return conditions

    def _seed_sellers(self):
        created = 0
        sellers = []
        for i, data in enumerate(SELLERS):
            email = f"seller{i + 1}@seed.vs"
            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "first_name": data["shop_name"].split()[0],
                    "last_name": "Seed",
                    "is_seller": True,
                    "email_verified": True,
                },
            )
            if user_created:
                user.set_unusable_password()
                user.save()

            # Signal auto-creates a Seller — update it with proper shop data.
            seller = Seller.objects.get(user=user)
            seller_created = not bool(seller.shop_name)
            Seller.objects.filter(pk=seller.pk).update(
                shop_name=data["shop_name"],
                shop_slug=slugify(data["shop_name"]),
                shop_description="Pažljivo odabrani vintage predmeti sa garancijom autentičnosti.",
                location=data["location"],
                status="active",
                bank_account_holder=data["shop_name"],
                bank_name="Banka",
                bank_account_number=f"RS35000000000000000{i:02d}",
            )
            seller.refresh_from_db()
            SellerSubscription.objects.get_or_create(
                seller=seller,
                defaults={
                    "plan_type": "monthly",
                    "start_date": timezone.now().date(),
                    "status": "active",
                    "amount": Decimal("999"),
                    "renewal_date": (timezone.now() + timedelta(days=30)).date(),
                },
            )
            sellers.append(seller)
            if seller_created:
                created += 1

        self.stdout.write(f"Prodavci: {created} kreirani, {len(SELLERS) - created} već postoje.")
        return sellers

    def _seed_products(self, sellers, conditions, attach_images=False):
        created = images_attached = skipped_missing = 0
        condition_list = list(conditions.values())
        seller_count = len(sellers)

        for subcategory_name, templates in PRODUCTS.items():
            try:
                category = ProductCategory.objects.get(name=subcategory_name)
            except ProductCategory.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  Podkategorija '{subcategory_name}' nije pronađena, preskačem."
                ))
                skipped_missing += len(templates)
                continue

            for i, tpl in enumerate(templates):
                product, is_new = Product.objects.get_or_create(
                    title=tpl["title"],
                    defaults={
                        "seller": sellers[i % seller_count],
                        "description": tpl["description"],
                        "price": Decimal(str(tpl["price"])),
                        "category": category,
                        "condition": random.choice(condition_list),
                        "stock": random.randint(1, 3),
                        "status": "published",
                    },
                )
                if is_new:
                    created += 1

                if attach_images and not product.images.exists():
                    img_path = SEED_IMAGES_DIR / subcategory_name / f"{i + 1:02d}.jpg"
                    if img_path.exists():
                        with open(img_path, "rb") as f:
                            ProductImage.objects.create(
                                product=product,
                                image=File(f, name=img_path.name),
                                alt_text=tpl["title"],
                                order=0,
                            )
                        images_attached += 1

        msg = f"Proizvodi: {created} kreirani."
        if images_attached:
            msg += f" {images_attached} slika zakačeno."
        if skipped_missing:
            msg += f" {skipped_missing} preskočeni (nedostaje podkategorija)."
        self.stdout.write(self.style.SUCCESS(msg))
