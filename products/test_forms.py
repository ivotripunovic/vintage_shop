"""
Tests for product forms.
"""

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from .forms import BulkProductImageForm, ProductForm, ProductImageForm
from .models import Product, ProductCategory, ProductCondition


class BulkProductImageFormTests(TestCase):
    """Tests for BulkProductImageForm."""

    def test_clean_returns_files_in_cleaned_data(self):
        """Test that clean() properly stores files in cleaned_data."""
        # Create mock image files
        image1 = SimpleUploadedFile(
            "test1.jpg", b"fake image content 1", content_type="image/jpeg"
        )
        image2 = SimpleUploadedFile(
            "test2.png", b"fake image content 2", content_type="image/png"
        )

        files = MultiValueDict({"images": [image1, image2]})
        form = BulkProductImageForm(data={}, files=files)

        # Form should be valid
        self.assertTrue(form.is_valid())

        # cleaned_data should contain 'images' key
        self.assertIn("images", form.cleaned_data)

        # cleaned_data['images'] should be the list of files
        returned_files = form.cleaned_data["images"]
        self.assertEqual(len(returned_files), 2)

        # Files should have 'name' attribute (not raw bytes)
        for file in returned_files:
            self.assertTrue(hasattr(file, "name"))
            self.assertTrue(hasattr(file, "size"))
            self.assertTrue(hasattr(file, "read"))

    def test_clean_requires_at_least_one_image(self):
        """Test that at least one image is required."""
        files = MultiValueDict({"images": []})
        form = BulkProductImageForm(data={}, files=files)

        self.assertFalse(form.is_valid())
        self.assertIn("Potrebna je barem jedna slika.", str(form.errors))

    def test_clean_validates_file_size(self):
        """Test that file size validation rejects files over 20MB."""
        large_file = SimpleUploadedFile(
            "large.jpg",
            b"x" * (21 * 1024 * 1024),  # 21MB — over the 20MB limit
            content_type="image/jpeg",
        )

        files = MultiValueDict({"images": [large_file]})
        form = BulkProductImageForm(data={}, files=files)

        self.assertFalse(form.is_valid())

    def test_clean_validates_file_extensions(self):
        """Test that only valid image extensions are allowed."""
        invalid_file = SimpleUploadedFile(
            "test.txt", b"not an image", content_type="text/plain"
        )

        files = MultiValueDict({"images": [invalid_file]})
        form = BulkProductImageForm(data={}, files=files)

        self.assertFalse(form.is_valid())
        self.assertIn("Dozvoljeni formati", str(form.errors))

    def test_clean_accepts_valid_image_formats(self):
        """Test that all valid image formats are accepted."""
        valid_formats = ["jpg", "jpeg", "png", "gif", "webp"]

        for fmt in valid_formats:
            image = SimpleUploadedFile(
                f"test.{fmt}", b"fake image content", content_type=f"image/{fmt}"
            )

            files = MultiValueDict({"images": [image]})
            form = BulkProductImageForm(data={}, files=files)

            self.assertTrue(form.is_valid(), f"Form should accept .{fmt} files")


class ProductImageFormTests(TestCase):
    """Tests for ProductImageForm."""

    def test_image_field_rejects_invalid_extensions(self):
        """Test that form rejects invalid image extensions."""
        invalid_file = SimpleUploadedFile(
            "test.txt", b"not an image", content_type="text/plain"
        )

        files = MultiValueDict({"image": [invalid_file]})
        form = ProductImageForm(data={"alt_text": "Test image"}, files=files)

        self.assertFalse(form.is_valid())
        # The form should have errors for the image field
        self.assertIn("image", form.errors)


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
