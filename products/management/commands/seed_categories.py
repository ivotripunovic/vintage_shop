from django.core.management.base import BaseCommand
from django.utils.text import slugify
from products.models import ProductCategory


# Hierarchy from Grupe.md
# Strings = leaf node, dicts with "children" = intermediate node
CATEGORIES = [
    {"name": "Novo"},
    {
        "name": "Moda",
        "children": [
            "Garderoba ženska",
            "Garderoba muška",
            "Obuća",
            "Aksesoari i nakit",
            "Dizajnerski komadi",
        ],
    },
    {
        "name": "Kuća",
        "children": [
            {
                "name": "Kuhinja & trpezarija",
                "children": [
                    "Porcelan i keramika",
                    "Čaše i servisi",
                    "Escajg",
                    "Kristal",
                ],
            },
            {
                "name": "Rasveta",
                "children": [
                    "Stone lampe",
                    "Lusteri",
                    "Industrijska rasveta",
                    "Retro lampe",
                ],
            },
            {
                "name": "Nameštaj",
                "children": [
                    "Stolice, fotelje",
                    "Stolovi i komode",
                    "Ormari i vitrine",
                    "Retro / mid-century komadi",
                ],
            },
        ],
    },
    {
        "name": "Antikviteti",
        "children": [
            "Nameštaj",
            "Dekoracija",
        ],
    },
    {
        "name": "Umetnost",
        "children": [
            "Slike i crteži",
            "Skulpture",
            "Fotografija",
            "Ručni radovi",
            "Printovi i plakati",
        ],
    },
    {
        "name": "Tehnika i elektronika",
        "children": [
            "Mobilni telefoni",
            "Računari i oprema",
            "TV i audio",
            "Foto i video oprema",
            "Kućni aparati",
            "Gaming",
        ],
    },
    {
        "name": "Kolekcionarski predmeti",
        "children": [
            "Stari novac",
            "Značke",
            "Razglednice",
            "Stare knjige",
            "Satovi",
        ],
    },
    {
        "name": "Sport i slobodno vreme",
        "children": [
            "Bicikli",
            "Fitnes oprema",
            "Kamp oprema",
            "Instrumenti",
            "Hobiji",
        ],
    },
    {"name": "Upcycled"},
    {"name": "Handmade"},
    {"name": "Editors pick"},
]


def make_slug(name, parent=None):
    """Build slug from full ancestor path: kuca-namestaj-stolice-fotelje."""
    part = slugify(name) or "kategorija"
    if parent and parent.slug:
        return f"{parent.slug}-{part}"
    return part


def seed_node(node, parent, order, counters):
    """Recursively create a category node and its children."""
    name = node if isinstance(node, str) else node["name"]
    slug = make_slug(name, parent)
    obj, created = ProductCategory.objects.get_or_create(
        name=name,
        parent=parent,
        defaults={"slug": slug, "order": order},
    )
    if not created and obj.order != order:
        obj.order = order
        obj.save(update_fields=["order"])
    if created:
        level = "top" if parent is None else "sub"
        counters[level] = counters.get(level, 0) + 1

    if isinstance(node, dict):
        for i, child in enumerate(node.get("children", [])):
            seed_node(child, obj, i, counters)


class Command(BaseCommand):
    help = "Seed product categories and subcategories from Grupe.md hierarchy"

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

        counters = {}

        for i, entry in enumerate(CATEGORIES):
            seed_node(entry, parent=None, order=i, counters=counters)

        top = counters.get("top", 0)
        sub = counters.get("sub", 0)
        self.stdout.write(self.style.SUCCESS(
            f"Done. Created {top} top-level and {sub} subcategories ({top + sub} total)."
        ))
