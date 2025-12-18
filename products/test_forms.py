"""
Tests for product forms.
"""

import pytest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict
from .forms import BulkProductImageForm, ProductImageForm


class BulkProductImageFormTests(TestCase):
    """Tests for BulkProductImageForm."""

    def test_clean_returns_files_in_cleaned_data(self):
        """Test that clean() properly stores files in cleaned_data."""
        # Create mock image files
        image1 = SimpleUploadedFile(
            "test1.jpg",
            b"fake image content 1",
            content_type="image/jpeg"
        )
        image2 = SimpleUploadedFile(
            "test2.png",
            b"fake image content 2",
            content_type="image/png"
        )
        
        files = MultiValueDict({'images': [image1, image2]})
        form = BulkProductImageForm(
            data={},
            files=files
        )
        
        # Form should be valid
        self.assertTrue(form.is_valid())
        
        # cleaned_data should contain 'images' key
        self.assertIn('images', form.cleaned_data)
        
        # cleaned_data['images'] should be the list of files
        returned_files = form.cleaned_data['images']
        self.assertEqual(len(returned_files), 2)
        
        # Files should have 'name' attribute (not raw bytes)
        for file in returned_files:
            self.assertTrue(hasattr(file, 'name'))
            self.assertTrue(hasattr(file, 'size'))
            self.assertTrue(hasattr(file, 'read'))

    def test_clean_requires_at_least_one_image(self):
        """Test that at least one image is required."""
        files = MultiValueDict({'images': []})
        form = BulkProductImageForm(
            data={},
            files=files
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('At least one image is required.', str(form.errors))

    def test_clean_validates_file_size(self):
        """Test that file size validation works."""
        # Create a mock file larger than 5MB
        large_file = SimpleUploadedFile(
            "large.jpg",
            b"x" * (6 * 1024 * 1024),  # 6MB
            content_type="image/jpeg"
        )
        
        files = MultiValueDict({'images': [large_file]})
        form = BulkProductImageForm(
            data={},
            files=files
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('File size must not exceed 5MB', str(form.errors))

    def test_clean_validates_file_extensions(self):
        """Test that only valid image extensions are allowed."""
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"not an image",
            content_type="text/plain"
        )
        
        files = MultiValueDict({'images': [invalid_file]})
        form = BulkProductImageForm(
            data={},
            files=files
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('Only', str(form.errors))

    def test_clean_accepts_valid_image_formats(self):
        """Test that all valid image formats are accepted."""
        valid_formats = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        
        for fmt in valid_formats:
            image = SimpleUploadedFile(
                f"test.{fmt}",
                b"fake image content",
                content_type=f"image/{fmt}"
            )
            
            files = MultiValueDict({'images': [image]})
            form = BulkProductImageForm(
                data={},
                files=files
            )
            
            self.assertTrue(form.is_valid(), f"Form should accept .{fmt} files")


class ProductImageFormTests(TestCase):
    """Tests for ProductImageForm."""

    def test_image_field_rejects_invalid_extensions(self):
        """Test that form rejects invalid image extensions."""
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"not an image",
            content_type="text/plain"
        )
        
        files = MultiValueDict({'image': [invalid_file]})
        form = ProductImageForm(
            data={'alt_text': 'Test image'},
            files=files
        )
        
        self.assertFalse(form.is_valid())
        # The form should have errors for the image field
        self.assertIn('image', form.errors)
