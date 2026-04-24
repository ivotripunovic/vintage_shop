import time
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from products.management.seed_data import PRODUCTS, SUBCATEGORY_SEARCH

SEED_IMAGES_DIR = Path(settings.BASE_DIR) / "seed_data" / "product_images"
PEXELS_API = "https://api.pexels.com/v1/search"


class Command(BaseCommand):
    help = "Download product images from Pexels into seed_data/product_images/."

    def add_arguments(self, parser):
        parser.add_argument("--key", required=True, help="Pexels API key")
        parser.add_argument("--force", action="store_true", help="Re-download existing images")

    def handle(self, *args, **options):
        api_key = options["key"]
        force = options["force"]
        session = requests.Session()
        session.headers.update({"Authorization": api_key})

        SEED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        downloaded = skipped = failed = 0
        total = sum(len(v) for v in PRODUCTS.values())

        for subcategory, products in PRODUCTS.items():
            subdir = SEED_IMAGES_DIR / subcategory
            subdir.mkdir(exist_ok=True)

            query = SUBCATEGORY_SEARCH.get(subcategory, subcategory)

            for idx, product in enumerate(products):
                filename = f"{idx + 1:02d}.jpg"
                dest = subdir / filename

                if dest.exists() and not force:
                    skipped += 1
                    continue

                # Use idx as page offset so each product in a subcategory gets a different photo
                try:
                    resp = session.get(
                        PEXELS_API,
                        params={"query": query, "per_page": 1, "page": idx + 1},
                        timeout=15,
                    )
                    resp.raise_for_status()
                    photos = resp.json().get("photos", [])

                    if not photos:
                        self.stdout.write(self.style.WARNING(
                            f"  No results for '{query}' (page {idx + 1})"
                        ))
                        failed += 1
                        continue

                    img_url = photos[0]["src"]["large"]
                    img_resp = requests.get(img_url, timeout=30)
                    img_resp.raise_for_status()
                    dest.write_bytes(img_resp.content)

                    downloaded += 1
                    done = downloaded + skipped + failed
                    self.stdout.write(f"  [{done}/{total}] {subcategory} / {product['title'][:40]}")

                    time.sleep(0.3)

                except requests.RequestException as e:
                    self.stdout.write(self.style.ERROR(f"  Failed: {product['title']} — {e}"))
                    failed += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {downloaded} downloaded, {skipped} skipped, {failed} failed."
        ))
