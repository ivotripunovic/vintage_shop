"""
Tests for product forms.
"""

from decimal import Decimal
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from PIL import Image

from .forms import MAX_IMAGE_MB, MB, ProductForm, validate_photo
from .models import Product, ProductCategory, ProductCondition


class ValidatePhotoTests(SimpleTestCase):
    """validate_photo opens the file; the extension proves nothing."""

    def _file(self, name, content):
        return SimpleUploadedFile(name, content, content_type="image/jpeg")

    def _image(self, format, name):
        buffer = BytesIO()
        Image.new("RGB", (20, 20)).save(buffer, format=format)
        return self._file(name, buffer.getvalue())

    def test_accepts_supported_formats(self):
        for format, name in [
            ("JPEG", "a.jpg"),
            ("PNG", "a.png"),
            ("WEBP", "a.webp"),
            ("GIF", "a.gif"),
        ]:
            validate_photo(self._image(format, name))

    def test_rejects_fake_image(self):
        with self.assertRaisesMessage(ValidationError, "nije fotografija"):
            validate_photo(self._file("a.jpg", b"not an image"))

    def test_rejects_other_image_formats(self):
        with self.assertRaisesMessage(ValidationError, "dozvoljeni formati"):
            validate_photo(self._image("BMP", "a.bmp"))

    def test_heic_gets_iphone_advice(self):
        with self.assertRaisesMessage(ValidationError, "Najkompatibilnije"):
            validate_photo(self._file("IMG_0001.HEIC", b"\x00\x00\x00 ftypheic"))

    def test_rejects_too_large(self):
        big = self._file("a.jpg", b"x" * (MAX_IMAGE_MB * MB + 1))
        with self.assertRaisesMessage(ValidationError, f"veća od {MAX_IMAGE_MB} MB"):
            validate_photo(big)

    def test_leaves_file_ready_to_read(self):
        photo = self._image("JPEG", "a.jpg")
        validate_photo(photo)
        self.assertEqual(photo.tell(), 0)


class ProductFormDefaultsTests(TestCase):
    """Whole-dinar prices, required category/condition, stock default (#45)."""

    def setUp(self):
        self.category = ProductCategory.objects.create(name="Lampe", slug="lampe")
        self.condition = ProductCondition.objects.create(
            name="Kao novo", description="Bez vidljivih oštećenja"
        )

    def _form(self, **overrides):
        data = {
            "title": "Lampa",
            "description": "Stona lampa",
            "price": "4500",
            "category": self.category.id,
            "condition": self.condition.id,
            "stock": "1",
        }
        data.update(overrides)
        return ProductForm(data={k: v for k, v in data.items() if v is not None})

    def test_price_accepts_thousands_separators_and_zero_decimals(self):
        for raw in ["4500", "4.500", "4 500", "4500,00", "4.500,00"]:
            form = self._form(price=raw)
            self.assertTrue(form.is_valid(), (raw, form.errors))
            self.assertEqual(form.cleaned_data["price"], Decimal("4500"))

    def test_price_rejects_fractions_and_bad_grouping(self):
        for raw in ["4500,50", "4.5", "12.34", "abc", "0", "100000000"]:
            form = self._form(price=raw)
            self.assertFalse(form.is_valid(), raw)
            self.assertIn("price", form.errors)

    def test_category_and_condition_are_required(self):
        form = self._form(category=None, condition=None)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["category"], ["Izaberite kategoriju."])
        self.assertEqual(form.errors["condition"], ["Izaberite stanje."])

    def test_missing_stock_means_one_item(self):
        form = self._form(stock=None)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["stock"], 1)

    def test_edit_shows_price_grouped_by_thousands(self):
        form = ProductForm(instance=Product(price=Decimal("1234567.00")))
        self.assertIn('value="1.234.567"', str(form["price"]))

    def test_new_form_defaults_stock_to_one(self):
        self.assertEqual(ProductForm()["stock"].value(), 1)
