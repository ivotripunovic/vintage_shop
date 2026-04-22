from django.core.management.base import BaseCommand
from django.utils.text import slugify
from products.models import ProductCategory


CATEGORIES = [
    {
        "name": "Nameštaj",
        "children": [
            "Sedenje",
            "Odlaganje",
            "Stolovi",
            "Osvetljenje",
            "Ukrasi za dom",
            "Dekorativni predmeti",
        ],
    },
    {
        "name": "Umetnost",
        "children": [
            "Slike",
            "Fotografija",
            "Skulpture",
            "Grafike",
            "Crteži",
        ],
    },
    {
        "name": "Nakit",
        "children": [
            "Prstenje",
            "Ogrlice",
            "Minđuše",
            "Narukvice",
            "Broševi",
            "Satovi",
        ],
    },
    {
        "name": "Moda",
        "children": [
            "Odeća",
            "Tašne",
            "Obuća",
            "Dodaci",
        ],
    },
    {
        "name": "Kolekcionarstvo",
        "children": [
            "Keramika i porcelan",
            "Srebrnina i metal",
            "Staklo",
            "Tekstil",
        ],
    },
]


def unique_slug(name, existing_slugs):
    base = slugify(name)
    slug = base
    counter = 1
    while slug in existing_slugs:
        slug = f"{base}-{counter}"
        counter += 1
    existing_slugs.add(slug)
    return slug


class Command(BaseCommand):
    help = "Seed product categories and subcategories"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing categories before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            ProductCategory.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared all existing categories."))

        existing_slugs = set(ProductCategory.objects.values_list("slug", flat=True))
        created_top = 0
        created_sub = 0

        for entry in CATEGORIES:
            slug = unique_slug(entry["name"], existing_slugs)
            parent, created = ProductCategory.objects.get_or_create(
                name=entry["name"],
                defaults={"slug": slug, "parent": None},
            )
            if created:
                created_top += 1

            for child_name in entry.get("children", []):
                child_slug = unique_slug(child_name, existing_slugs)
                _, child_created = ProductCategory.objects.get_or_create(
                    name=child_name,
                    defaults={"slug": child_slug, "parent": parent},
                )
                if child_created:
                    created_sub += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_top} top-level categories and {created_sub} subcategories."
            )
        )
