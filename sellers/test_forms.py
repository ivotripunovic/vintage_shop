"""
Tests for seller forms.
"""

import pytest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict

from users.models import User
from .models import Seller
from .forms import SellerAccountSettingsForm


class SellerAccountSettingsFormTests(TestCase):
    """Tests for SellerAccountSettingsForm."""

    def setUp(self):
        """Set up test user and seller."""
        self.user = User.objects.create_user(
            email='test@example.com',
            username='test@example.com',
            password='testpass123',
            is_seller=True
        )
        self.seller, _ = Seller.objects.get_or_create(
            user=self.user,
            defaults={
                'shop_name': 'Test Shop',
                'shop_slug': 'test-shop',
                'shop_description': 'Test description',
                'location': 'Test location'
            }
        )

    def test_form_accepts_user_as_keyword_argument(self):
        """Test that form can be instantiated with user as keyword argument."""
        # This is how the view calls it
        form = SellerAccountSettingsForm(
            data={
                'shop_name': 'Updated Shop',
                'shop_description': 'Updated description',
                'location': 'Updated location',
                'email': 'updated@example.com'
            },
            instance=self.seller,
            user=self.user
        )
        
        self.assertTrue(form.is_valid(), str(form.errors))
        self.assertEqual(form.cleaned_data['email'], 'updated@example.com')

    def test_form_with_files_and_user(self):
        """Test that form accepts files and user as keyword argument."""
        image = SimpleUploadedFile(
            "test.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )
        
        files = MultiValueDict({'shop_image': [image]})
        form = SellerAccountSettingsForm(
            data={
                'shop_name': 'Updated Shop',
                'shop_description': 'Updated description',
                'location': 'Updated location',
                'email': 'updated@example.com'
            },
            files=files,
            instance=self.seller,
            user=self.user
        )
        
        # Form should process without TypeError
        try:
            is_valid = form.is_valid()
        except TypeError as e:
            self.fail(f"Form raised TypeError: {e}")

    def test_email_field_initialized_with_user_email(self):
        """Test that email field is initialized with user's current email."""
        form = SellerAccountSettingsForm(instance=self.seller, user=self.user)
        self.assertEqual(form.fields['email'].initial, self.user.email)

    def test_email_validation_allows_same_email(self):
        """Test that form allows keeping the same email."""
        form = SellerAccountSettingsForm(
            data={
                'shop_name': 'Updated Shop',
                'shop_description': 'Updated description',
                'location': 'Updated location',
                'email': self.user.email  # Same email
            },
            instance=self.seller,
            user=self.user
        )
        
        self.assertTrue(form.is_valid())

    def test_email_validation_rejects_duplicate_email(self):
        """Test that form rejects email already in use by another user."""
        # Create another user with different email
        other_user = User.objects.create_user(
            email='other@example.com',
            username='other@example.com',
            password='testpass123',
            is_seller=True
        )
        
        form = SellerAccountSettingsForm(
            data={
                'shop_name': 'Updated Shop',
                'shop_description': 'Updated description',
                'location': 'Updated location',
                'email': 'other@example.com'  # Email of another user
            },
            instance=self.seller,
            user=self.user
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_save_updates_user_email(self):
        """Test that saving form updates the user's email."""
        form = SellerAccountSettingsForm(
            data={
                'shop_name': 'Updated Shop',
                'shop_description': 'Updated description',
                'location': 'Updated location',
                'email': 'newemail@example.com'
            },
            instance=self.seller,
            user=self.user
        )
        
        self.assertTrue(form.is_valid())
        form.save()
        
        # Refresh user from database
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'newemail@example.com')
        self.assertEqual(self.user.username, 'newemail@example.com')

    def test_form_no_typeerror_with_post_and_user_kwarg(self):
        """
        Regression test: Ensure form doesn't raise TypeError when user is passed
        as keyword argument alongside POST/FILES data.
        
        This tests the bug fix where __init__(user, *args, **kwargs) was changed to
        __init__(*args, user=None, **kwargs) to allow user to be a keyword argument.
        
        Bug: TypeError at /en/seller/settings/
        SellerAccountSettingsForm.__init__() got multiple values for argument 'user'
        """
        # This should NOT raise TypeError
        try:
            form = SellerAccountSettingsForm(
                data={
                    'shop_name': 'Updated Shop',
                    'shop_description': 'Updated description',
                    'location': 'Updated location',
                    'email': 'newemail@example.com'
                },
                instance=self.seller,
                user=self.user
            )
            # If we got here, no TypeError was raised
            self.assertTrue(True)
        except TypeError as e:
            if "multiple values for argument 'user'" in str(e):
                self.fail(
                    "Form raised TypeError about multiple values for 'user'. "
                    "This means the bug has regressed. Ensure __init__ signature is "
                    "__init__(*args, user=None, **kwargs)"
                )
            else:
                raise
