"""
Make thumbnails and quality measurements for photos uploaded before they
existed.

By default the stored photos are left as they are. With --rewrite-originals
each photo is also rotated upright, stripped of metadata (GPS from phones)
and capped at 2000px, and the old file is deleted; back up media/ first.
Safe to run again: photos that already have a thumbnail are skipped unless
--all is given.
"""

from django.core.management.base import BaseCommand

from products.models import ProductImage


class Command(BaseCommand):
    help = "Create thumbnails and quality measurements for existing photos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rewrite-originals",
            action="store_true",
            help="Also resize, rotate and strip metadata from the stored photos.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Process photos that already have a thumbnail too.",
        )

    def handle(self, *args, **options):
        images = ProductImage.objects.order_by("id")
        if not options["all"]:
            images = images.filter(thumbnail="")
        keep_original = not options["rewrite_originals"]

        done = failed = 0
        for image in images.iterator():
            try:
                with image.image.open("rb"):
                    ok = image.process(keep_original=keep_original)
            except FileNotFoundError:
                ok = False
            if not ok:
                failed += 1
                self.stderr.write(f"Skipped photo {image.id}: {image.image.name}")
                continue
            fields = ["thumbnail", "width", "height", "brightness", "sharpness"]
            if not keep_original:
                fields.append("image")
            image.save(update_fields=fields)
            done += 1
        self.stdout.write(f"Processed {done} photo(s), skipped {failed}.")
