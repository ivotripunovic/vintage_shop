"""
Tests for photo processing (products.images), listing tips (products.quality)
and the backfill_photos command.
"""

import os
import shutil
import tempfile
from io import BytesIO, StringIO
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image, ImageDraw, ImageFilter

from products.images import MAX_EDGE, MAX_PIXELS, THUMB_EDGE, _flatten
from products.models import Product, ProductImage
from products.quality import CHECKS, check_photos, check_text, listing_report
from sellers.models import Seller
from users.models import User

MEDIA_ROOT = tempfile.mkdtemp()

GOOD_TITLE = "Kožna jakna Levi's, veličina M"
GOOD_DESCRIPTION = (
    "Prava koža, kupljena 1998. Nošena, ali čuvana: postava cela, rajsferšlus "
    "radi. Mala ogrebotina na levom rukavu. Dužina 70 cm, ramena 48 cm."
)


def photo_bytes(size=(1200, 900), format="JPEG", exif_orientation=None, mode="RGB"):
    """A detailed test photo: a checkerboard is sharp and mid-bright."""
    img = Image.new(mode, size, "white")
    draw = ImageDraw.Draw(img)
    step = max(size) // 24
    for x in range(0, size[0], step):
        for y in range(0, size[1], step):
            if (x // step + y // step) % 2:
                draw.rectangle([x, y, x + step, y + step], fill="black")
    kwargs = {}
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation  # Orientation
        exif[0x8825] = {1: "N"}  # GPSInfo
        kwargs["exif"] = exif
    buffer = BytesIO()
    img.save(buffer, format=format, **kwargs)
    return buffer.getvalue()


def upload(name="photo.jpg", **kwargs):
    return SimpleUploadedFile(name, photo_bytes(**kwargs), content_type="image/jpeg")


class SellerMixin:
    def make_product(self, **kwargs):
        user = User.objects.create_user(
            username="photos",
            email="photos@example.com",
            password="pass12345",
            is_seller=True,
        )
        seller, _ = Seller.objects.get_or_create(
            user=user, defaults={"shop_name": "Foto", "shop_slug": "foto"}
        )
        fields = {"title": GOOD_TITLE, "description": GOOD_DESCRIPTION, "price": 100}
        fields.update(kwargs)
        return Product.objects.create(seller=seller, **fields)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PhotoProcessingTests(SellerMixin, TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.product = self.make_product()

    def add(self, file):
        return ProductImage.objects.create(product=self.product, image=file)

    def test_large_photo_is_capped_and_thumbnailed(self):
        image = self.add(upload(size=(4000, 3000)))
        with Image.open(image.image.path) as stored:
            self.assertEqual(stored.size, (MAX_EDGE, 1500))
        with Image.open(image.thumbnail.path) as thumb:
            self.assertEqual(max(thumb.size), THUMB_EDGE)
        self.assertEqual((image.width, image.height), (MAX_EDGE, 1500))
        self.assertEqual(image.thumb_url, image.thumbnail.url)

    def test_exif_rotation_applied_and_metadata_stripped(self):
        # Orientation 6: the camera was held upright, pixels are landscape
        image = self.add(upload(size=(1200, 900), exif_orientation=6))
        with Image.open(image.image.path) as stored:
            self.assertEqual(stored.size, (900, 1200))
            self.assertEqual(len(stored.getexif()), 0)

    def test_small_clean_jpeg_is_stored_as_uploaded(self):
        data = photo_bytes(size=(1200, 900))
        image = self.add(SimpleUploadedFile("clean.jpg", data, "image/jpeg"))
        with open(image.image.path, "rb") as stored:
            self.assertEqual(stored.read(), data)
        self.assertTrue(image.thumbnail)

    def test_transparent_png_becomes_jpeg_on_white(self):
        data = photo_bytes(size=(800, 800), format="PNG", mode="RGBA")
        image = self.add(SimpleUploadedFile("cut.png", data, "image/png"))
        self.assertTrue(image.image.name.endswith(".jpg"))
        with Image.open(image.image.path) as stored:
            self.assertEqual(stored.format, "JPEG")

    def test_unreadable_file_is_kept_without_thumbnail(self):
        image = self.add(SimpleUploadedFile("bad.jpg", b"not a photo", "image/jpeg"))
        self.assertTrue(image.image)
        self.assertFalse(image.thumbnail)
        self.assertIsNone(image.sharpness)
        self.assertEqual(image.thumb_url, image.image.url)

    def test_reordering_does_not_reprocess(self):
        image = self.add(upload())
        thumb = image.thumbnail.name
        image.order = 5
        image.save()
        image.refresh_from_db()
        self.assertEqual(image.thumbnail.name, thumb)

    def test_measures_brightness_and_sharpness(self):
        sharp = self.add(upload())
        blurred = Image.open(BytesIO(photo_bytes())).filter(ImageFilter.GaussianBlur(8))
        buffer = BytesIO()
        blurred.save(buffer, format="JPEG")
        blurry = self.add(SimpleUploadedFile("blur.jpg", buffer.getvalue()))
        self.assertGreater(sharp.sharpness, 10 * blurry.sharpness)
        self.assertAlmostEqual(sharp.brightness, 127, delta=20)

    def test_xmp_and_comment_metadata_are_stripped(self):
        # GPS can travel in XMP instead of EXIF; such a JPEG must not be
        # stored as uploaded
        img = Image.open(BytesIO(photo_bytes(size=(800, 600))))
        buffer = BytesIO()
        xmp = b'<x:xmpmeta><rdf:Description exif:GPSLatitude="44,49N"/></x:xmpmeta>'
        img.save(buffer, format="JPEG", xmp=xmp, comment=b"Ulica 12, Beograd")
        image = self.add(SimpleUploadedFile("xmp.jpg", buffer.getvalue()))
        with open(image.image.path, "rb") as stored:
            data = stored.read()
        self.assertNotIn(b"GPSLatitude", data)
        self.assertNotIn(b"Beograd", data)

    def test_colour_profile_is_kept(self):
        from PIL import ImageCms

        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        img = Image.open(BytesIO(photo_bytes(size=(3000, 2000))))
        buffer = BytesIO()
        img.save(buffer, format="JPEG", icc_profile=icc)
        image = self.add(SimpleUploadedFile("p3.jpg", buffer.getvalue()))
        for field in (image.image, image.thumbnail):
            with Image.open(field.path) as stored:
                self.assertEqual(stored.info.get("icc_profile"), icc)

    def test_transparent_and_16_bit_images_flatten_sensibly(self):
        # PNG can't store "PA"; it only appears in memory, so test it directly
        for mode in ("LA", "PA"):
            clear = Image.new("RGBA", (40, 40), (10, 20, 30, 0)).convert(mode)
            flat = _flatten(clear)
            self.assertEqual(flat.getpixel((0, 0)), (255, 255, 255), mode)

        transparent = BytesIO()
        Image.new("LA", (400, 400), (0, 0)).save(transparent, format="PNG")
        image = self.add(SimpleUploadedFile("la.png", transparent.getvalue()))
        self.assertGreater(image.brightness, 250)  # white, not black

        gray16 = BytesIO()
        Image.new("I;16", (400, 400), 0x8000).save(gray16, format="PNG")  # mid gray
        image = self.add(SimpleUploadedFile("g16.png", gray16.getvalue()))
        self.assertAlmostEqual(image.brightness, 128, delta=2)

    def test_huge_png_is_kept_unprocessed(self):
        side = int(MAX_PIXELS**0.5) + 10
        buffer = BytesIO()
        Image.new("1", (side, side)).save(buffer, format="PNG")
        image = self.add(SimpleUploadedFile("huge.png", buffer.getvalue()))
        self.assertFalse(image.thumbnail)

    def test_replacing_photo_deletes_old_files_after_commit(self):
        image = self.add(upload())
        old = [image.image.path, image.thumbnail.path]
        image.image = upload(name="new.jpg", size=(800, 600))
        with self.captureOnCommitCallbacks(execute=True):
            image.save()
        self.assertEqual((image.width, image.height), (800, 600))
        for path in old:
            self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.exists(image.thumbnail.path))

    def test_deleting_photo_removes_files(self):
        image = self.add(upload())
        paths = [image.image.path, image.thumbnail.path]
        with self.captureOnCommitCallbacks(execute=True):
            image.delete()
        for path in paths:
            self.assertFalse(os.path.exists(path))


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BackfillPhotosTests(SellerMixin, TestCase):
    def setUp(self):
        self.product = self.make_product()
        # As stored before this change: big, rotated, no thumbnail
        self.image = ProductImage(product=self.product)
        self.image.image.save(
            "old.jpg",
            ContentFile(photo_bytes(size=(3000, 2000), exif_orientation=6)),
            save=False,
        )
        ProductImage.objects.bulk_create([self.image])  # skips save()
        self.image = ProductImage.objects.get()

    def run_command(self, *args):
        out = StringIO()
        call_command("backfill_photos", *args, stdout=out, stderr=StringIO())
        self.image.refresh_from_db()
        return out.getvalue()

    def test_adds_thumbnail_and_keeps_original(self):
        original = self.image.image.name
        self.assertIn("Processed 1", self.run_command())
        self.assertTrue(self.image.thumbnail)
        self.assertEqual(self.image.image.name, original)
        self.assertEqual((self.image.width, self.image.height), (2000, 3000))
        self.assertIn("Processed 0", self.run_command())  # idempotent

    def test_rewrite_originals_resizes_and_deletes_old_file(self):
        old_path = self.image.image.path
        with self.captureOnCommitCallbacks(execute=True):
            self.run_command("--rewrite-originals")
        with Image.open(self.image.image.path) as stored:
            self.assertEqual(stored.size, (1333, MAX_EDGE))
            self.assertEqual(len(stored.getexif()), 0)
        self.assertFalse(os.path.exists(old_path))

    def test_error_on_one_photo_skips_it_and_keeps_its_files(self):
        old_path = self.image.image.path
        with mock.patch.object(
            ProductImage, "save", side_effect=RuntimeError("disk full")
        ), self.captureOnCommitCallbacks(execute=True):
            out = self.run_command("--rewrite-originals")
        self.assertIn("skipped 1", out)
        self.assertTrue(os.path.exists(old_path))
        self.assertFalse(self.image.thumbnail)

    def test_missing_file_is_skipped(self):
        self.image.image.storage.delete(self.image.image.name)
        self.assertIn("skipped 1", self.run_command())


class Photo:
    """Stand-in for a measured ProductImage."""

    def __init__(self, id=1, width=1600, height=1200, brightness=120, sharpness=900):
        self.id, self.width, self.height = id, width, height
        self.brightness, self.sharpness = brightness, sharpness


def checks(tips):
    return sorted(tip.check for tip in tips)


class QualityTipsTests(SimpleTestCase):
    def good_photos(self):
        return [Photo(id=i) for i in range(1, 4)]

    def test_good_photos_get_no_tips(self):
        self.assertEqual(check_photos(self.good_photos()), [])

    def test_too_few_photos(self):
        self.assertEqual(checks(check_photos([Photo()])), ["count"])
        self.assertIn("Dodajte fotografije", check_photos([])[0].message)

    def test_bad_photo_gets_tips_tied_to_it(self):
        photos = self.good_photos()
        photos[1] = Photo(id=2, width=640, height=480, brightness=20, sharpness=40)
        tips = check_photos(photos)
        self.assertEqual(checks(tips), ["light", "resolution", "sharpness"])
        self.assertTrue(all(tip.image_id == 2 for tip in tips))
        self.assertTrue(all(tip.message.startswith("Fotografija 2:") for tip in tips))

    def test_overexposed_photo(self):
        photos = self.good_photos()
        photos[0] = Photo(id=1, brightness=250)
        self.assertIn(
            "Naslovna fotografija: presvetla", check_photos(photos)[0].message
        )

    def test_long_cover_gets_crop_tip_but_later_photos_do_not(self):
        photos = self.good_photos()
        photos[2] = Photo(id=3, width=2000, height=800)
        self.assertEqual(check_photos(photos), [])
        photos[0] = Photo(id=1, width=2000, height=800)
        self.assertEqual(checks(check_photos(photos)), ["cover"])

    def test_unmeasured_photos_are_skipped(self):
        photos = [
            Photo(id=i, width=None, brightness=None, sharpness=None) for i in (1, 2, 3)
        ]
        self.assertEqual(check_photos(photos), [])

    def test_good_text_gets_no_tips(self):
        self.assertEqual(check_text(GOOD_TITLE, GOOD_DESCRIPTION), [])

    def test_weak_text(self):
        tips = check_text("JAKNA KOZNA ODLICNA", "Kao nova.")
        self.assertEqual(checks(tips), ["capitals", "description", "measurements"])
        self.assertEqual(checks(check_text("Jakna", GOOD_DESCRIPTION)), ["title"])

    def test_report_counts_each_check_once(self):
        product = Product(title="Jakna", description=GOOD_DESCRIPTION)
        bad = [Photo(id=i, sharpness=10) for i in (1, 2, 3)]
        report = listing_report(product, bad)
        self.assertEqual(report.checks, len(CHECKS))
        self.assertEqual(report.passed, len(CHECKS) - 2)  # sharpness, title
        self.assertEqual(len(report.for_image(2)), 1)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ListingTipsPageTests(SellerMixin, TestCase):
    def test_seller_sees_tips_on_product_and_photo_pages(self):
        product = self.make_product(title="Jakna")
        ProductImage.objects.create(product=product, image=upload(size=(640, 480)))
        self.client.force_login(product.seller.user)

        response = self.client.get(reverse("product_seller_detail", args=[product.id]))
        self.assertContains(response, "Kvalitet oglasa")
        self.assertContains(response, "Naslov: dodajte")
        self.assertContains(response, "mala rezolucija (640×480)")

        response = self.client.get(reverse("product_edit", args=[product.id]))
        self.assertContains(response, "Mala rezolucija (640×480)")
        self.assertContains(response, "Za dobre fotografije")
        self.assertContains(response, '<span id="photo-count">1</span>')
