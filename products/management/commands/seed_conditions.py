from django.core.management.base import BaseCommand
from products.models import ProductCondition
from products.management.seed_data import CONDITIONS


class Command(BaseCommand):
    help = "Seed product conditions (stanja proizvoda)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all conditions before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            ProductCondition.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared all conditions."))

        created = 0
        for data in CONDITIONS:
            obj, is_new = ProductCondition.objects.get_or_create(
                name=data["name"],
                defaults={"description": data["description"], "order": data["order"]},
            )
            if is_new:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Stanja: {created} kreirana, {len(CONDITIONS) - created} već postoje."
        ))
