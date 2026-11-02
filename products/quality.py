"""
Listing quality tips for sellers, in the spirit of Booking.com's property
page score: a short checklist of concrete fixes for photos and text.

Tips are advice only; they never block publishing (that is publish_error's
job). Photo tips use the measurements taken on upload (products.images);
photos uploaded before those existed have none and are skipped until
backfill_photos has run.
"""

import re
from dataclasses import dataclass

MIN_PHOTOS = 3
MIN_LONG_EDGE = 1000  # buyers zoom in; the detail page shows ~600px at 2x
DARK_BELOW = 45  # mean luminance 0-255
BRIGHT_ABOVE = 240
# Edge variance on a 512px copy: the seed photos measure 290+, the same photos
# blurred 0.3% of their size about 200, so this flags clear blur only
BLURRY_BELOW = 150
# Grid cards crop to a square; a cover longer than this loses its sides
MAX_COVER_RATIO = 1.6

MIN_TITLE_CHARS = 15
MIN_TITLE_WORDS = 3
MIN_DESCRIPTION_CHARS = 120


@dataclass(frozen=True)
class Tip:
    check: str  # one of CHECKS
    message: str
    image_id: int | None = None  # set when the tip is about one photo


PHOTO_CHECKS = ("count", "resolution", "light", "sharpness", "cover")
TEXT_CHECKS = ("title", "capitals", "description", "measurements")
CHECKS = PHOTO_CHECKS + TEXT_CHECKS


@dataclass
class Report:
    tips: list

    @property
    def checks(self):
        return len(CHECKS)

    @property
    def passed(self):
        """Checks with no tip; several photos failing one check count once."""
        return self.checks - len({tip.check for tip in self.tips})

    @property
    def percent(self):
        return round(100 * self.passed / self.checks)

    @property
    def photo_tips(self):
        return [tip for tip in self.tips if tip.check in PHOTO_CHECKS]

    @property
    def text_tips(self):
        return [tip for tip in self.tips if tip.check in TEXT_CHECKS]

    def for_image(self, image_id):
        return [tip for tip in self.tips if tip.image_id == image_id]


def check_photos(images):
    """Tips for the ordered photos of one listing."""
    tips = []
    if len(images) < MIN_PHOTOS:
        more = "još fotografija" if images else "fotografije"
        tips.append(
            Tip(
                "count",
                f"Dodajte {more}: bar {MIN_PHOTOS} — ceo predmet spreda "
                "i pozadi, pa detalj (etiketa, pečat, oštećenje).",
            )
        )
    for number, image in enumerate(images, start=1):
        label = "Naslovna fotografija" if number == 1 else f"Fotografija {number}"
        if image.width and max(image.width, image.height) < MIN_LONG_EDGE:
            tips.append(
                Tip(
                    "resolution",
                    f"{label}: mala rezolucija ({image.width}×{image.height}). "
                    "Kupci uvećavaju slike; slikajte izbliza, punom kamerom "
                    "telefona, bez zumiranja.",
                    image.id,
                )
            )
        if image.brightness is not None and image.brightness < DARK_BELOW:
            tips.append(
                Tip(
                    "light",
                    f"{label}: pretamna. Slikajte pored prozora po danu, bez blica.",
                    image.id,
                )
            )
        elif image.brightness is not None and image.brightness > BRIGHT_ABOVE:
            tips.append(
                Tip(
                    "light",
                    f"{label}: presvetla, detalji se gube. Izbegnite direktno "
                    "sunce i blic.",
                    image.id,
                )
            )
        if image.sharpness is not None and image.sharpness < BLURRY_BELOW:
            tips.append(
                Tip(
                    "sharpness",
                    f"{label}: deluje mutno. Dodirnite predmet na ekranu da "
                    "izoštrite i držite telefon mirno.",
                    image.id,
                )
            )
        if number == 1 and image.width and image.height:
            ratio = max(image.width, image.height) / min(image.width, image.height)
            if ratio > MAX_COVER_RATIO:
                tips.append(
                    Tip(
                        "cover",
                        f"{label}: u pretrazi se seče na kvadrat, pa se deo "
                        "predmeta ne vidi. Izaberite fotografiju na kojoj je "
                        "predmet u sredini.",
                        image.id,
                    )
                )
    return tips


def check_text(title, description):
    """Tips for the listing title and description."""
    tips = []
    title = (title or "").strip()
    description = (description or "").strip()

    if len(title) < MIN_TITLE_CHARS or len(title.split()) < MIN_TITLE_WORDS:
        tips.append(
            Tip(
                "title",
                "Naslov: dodajte šta je, brend ili poreklo i veličinu, "
                "npr. „Kožna jakna Levi's, veličina M“.",
            )
        )
    letters = [c for c in title if c.isalpha()]
    if len(letters) >= 8 and all(c.isupper() for c in letters):
        tips.append(
            Tip(
                "capitals",
                "Naslov: pišite običnim slovima; VELIKA SLOVA deluju kao vika.",
            )
        )

    if len(description) < MIN_DESCRIPTION_CHARS:
        tips.append(
            Tip(
                "description",
                "Opis: napišite bar nekoliko rečenica — materijal, godište ili "
                "period, kako je korišćeno i eventualna oštećenja.",
            )
        )
    if not re.search(r"\d", description):
        tips.append(
            Tip(
                "measurements",
                "Mere: navedite dimenzije ili veličinu (npr. dužina 70 cm, "
                "širina 50 cm). To je najčešće pitanje kupaca.",
            )
        )
    return tips


def listing_report(product, images=None):
    """Quality report for a saved product; images default to its photos."""
    images = list(product.images.all() if images is None else images)
    return Report(check_photos(images) + check_text(product.title, product.description))
