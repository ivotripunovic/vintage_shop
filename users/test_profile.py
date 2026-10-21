"""
Buyer profile picture and short bio on the account settings page (issue #4).
"""

import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from users.forms import UserProfileForm
from users.models import User

MEDIA_ROOT = tempfile.mkdtemp()


def _picture(name="me.png", size=(10, 10)):
    buffer = BytesIO()
    Image.new("RGB", size).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BuyerProfileTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            email="buyer@test.com", username="buyer", password="testpass123"
        )
        self.client.force_login(self.user)
        self.url = reverse("account-settings")

    def test_buyer_sees_profile_form(self):
        response = self.client.get(self.url)
        self.assertIsInstance(response.context["profile_form"], UserProfileForm)
        self.assertContains(response, "Sačuvaj profil")

    def test_buyer_uploads_picture_and_bio(self):
        response = self.client.post(
            self.url, {"bio": "Volim stare ploče.", "profile_picture": _picture()}
        )
        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "Volim stare ploče.")
        self.assertTrue(self.user.profile_picture.name.startswith("profile_pictures/"))

        response = self.client.get(self.url)
        self.assertContains(response, "Volim stare ploče.")
        self.assertContains(response, self.user.profile_picture.url)

    def test_saving_bio_keeps_existing_picture(self):
        self.client.post(self.url, {"bio": "", "profile_picture": _picture()})
        self.client.post(self.url, {"bio": "Novi opis"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "Novi opis")
        self.assertTrue(self.user.profile_picture)

    def test_buyer_removes_picture(self):
        self.client.post(self.url, {"bio": "", "profile_picture": _picture()})
        self.client.post(self.url, {"bio": "", "remove_picture": "on"})
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile_picture)

    def test_bio_is_limited_to_300_characters(self):
        response = self.client.post(self.url, {"bio": "a" * 301})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["profile_form"].errors["bio"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "")

    def test_rejects_file_that_is_not_an_image(self):
        not_image = SimpleUploadedFile("me.png", b"not an image", "image/png")
        response = self.client.post(self.url, {"bio": "", "profile_picture": not_image})
        self.assertTrue(response.context["profile_form"].errors["profile_picture"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile_picture)

    def test_rejects_unsupported_format(self):
        buffer = BytesIO()
        Image.new("RGB", (10, 10)).save(buffer, format="BMP")
        bmp = SimpleUploadedFile("me.bmp", buffer.getvalue(), "image/bmp")
        response = self.client.post(self.url, {"bio": "", "profile_picture": bmp})
        self.assertIn(
            "Dozvoljeni formati",
            response.context["profile_form"].errors["profile_picture"][0],
        )


class SellerProfileTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@test.com",
            username="seller",
            password="testpass123",
            is_seller=True,
        )
        self.client.force_login(self.seller)
        self.url = reverse("account-settings")

    def test_seller_is_pointed_to_shop_settings(self):
        response = self.client.get(self.url)
        self.assertIsNone(response.context["profile_form"])
        self.assertContains(response, reverse("seller_settings"))

    def test_seller_cannot_set_buyer_bio(self):
        self.client.post(self.url, {"bio": "Ignored"})
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.bio, "")
