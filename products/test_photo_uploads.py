"""
Tests for staged photo uploads on the listing form (#44): the upload and
discard endpoints, attaching on save, the no-JavaScript fallback and the
purge command.
"""

import os
import shutil
import tempfile
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from products.forms import MAX_PENDING_UPLOADS, MAX_PHOTOS
from products.models import (
    PhotoUpload,
    Product,
    ProductCategory,
    ProductCondition,
    ProductImage,
)
from products.quality import TEXT_TIPS
from products.test_images import photo_bytes
from sellers.models import Seller
from users.models import User

MEDIA_ROOT = tempfile.mkdtemp()


def photo(name="photo.jpg", size=(1200, 900)):
    return SimpleUploadedFile(name, photo_bytes(size=size), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PhotoUploadTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.seller = self.make_seller("upload")
        self.client.force_login(self.seller.user)
        parent = ProductCategory.objects.create(name="Kuća", slug="kuca")
        self.category = ProductCategory.objects.create(
            name="Lampe", slug="lampe", parent=parent
        )
        self.condition = ProductCondition.objects.create(name="Dobro")

    def make_seller(self, name):
        user = User.objects.create_user(
            username=name,
            email=f"{name}@example.com",
            password="pass12345",
            is_seller=True,
        )
        seller, _ = Seller.objects.get_or_create(
            user=user, defaults={"shop_name": name, "shop_slug": name}
        )
        return seller

    def make_product(self, seller=None, **kwargs):
        fields = {"title": "Lampa", "description": "Stona lampa", "price": 100}
        fields.update(kwargs)
        return Product.objects.create(seller=seller or self.seller, **fields)

    def upload(self, file=None, product=None):
        data = {"photo": file or photo()}
        if product:
            data["product"] = product.id
        return self.client.post(reverse("photo_upload"), data)

    def form_data(self, **overrides):
        data = {
            "title": "Stona lampa",
            "description": "Mesing, iz 1970-ih. Visina 40 cm.",
            "price": "4.500",
            "category": self.category.id,
            "condition": self.condition.id,
        }
        data.update(overrides)
        return data


class UploadEndpointTests(PhotoUploadTestCase):
    def test_upload_without_product_is_pending(self):
        response = self.upload(photo(size=(640, 480)))
        self.assertEqual(response.status_code, 201)
        data = response.json()
        upload = PhotoUpload.objects.get(id=data["id"])
        self.assertEqual(upload.seller, self.seller)
        self.assertEqual(data["kind"], "upload")
        self.assertEqual(data["thumb_url"], upload.thumbnail.url)
        self.assertEqual(
            data["remove_url"], reverse("photo_upload_discard", args=[upload.id])
        )
        self.assertTrue(any("Mala rezolucija" in tip for tip in data["tips"]))

    def test_upload_to_product_is_added_last(self):
        product = self.make_product()
        first = self.upload(product=product).json()
        second = self.upload(product=product).json()
        self.assertEqual(second["kind"], "image")
        orders = list(product.images.values_list("id", "order"))
        self.assertEqual(orders, [(first["id"], 0), (second["id"], 1)])
        self.assertEqual(
            ProductImage.objects.get(id=second["id"]).alt_text,
            "Lampa – fotografija 2",
        )
        self.assertFalse(PhotoUpload.objects.exists())

    def test_cannot_upload_to_another_sellers_product(self):
        other = self.make_product(seller=self.make_seller("other"))
        self.assertEqual(self.upload(product=other).status_code, 404)
        self.assertFalse(ProductImage.objects.exists())

    def test_buyers_and_get_are_refused(self):
        buyer = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pass12345"
        )
        self.client.force_login(buyer)
        self.assertEqual(self.upload().status_code, 403)
        self.client.force_login(self.seller.user)
        self.assertEqual(self.client.get(reverse("photo_upload")).status_code, 405)

    def test_fake_photo_is_rejected_with_message(self):
        fake = SimpleUploadedFile("a.jpg", b"not an image", "image/jpeg")
        response = self.upload(fake)
        self.assertEqual(response.status_code, 400)
        self.assertIn("nije fotografija", response.json()["error"])
        self.assertFalse(PhotoUpload.objects.exists())

    def test_missing_file(self):
        response = self.client.post(reverse("photo_upload"), {})
        self.assertEqual(response.status_code, 400)

    def test_listing_photo_limit(self):
        product = self.make_product()
        ProductImage.objects.bulk_create(
            ProductImage(product=product, image=f"products/{n}.jpg", order=n)
            for n in range(MAX_PHOTOS)
        )
        response = self.upload(product=product)
        self.assertEqual(response.status_code, 400)
        self.assertIn(f"najviše {MAX_PHOTOS}", response.json()["error"])

    def test_pending_upload_limit(self):
        PhotoUpload.objects.bulk_create(
            PhotoUpload(seller=self.seller, image=f"products/{n}.jpg")
            for n in range(MAX_PENDING_UPLOADS)
        )
        response = self.upload()
        self.assertEqual(response.status_code, 400)
        self.assertIn("previše", response.json()["error"])

    def test_discard_removes_upload_and_files(self):
        upload = PhotoUpload.objects.get(id=self.upload().json()["id"])
        paths = [upload.image.path, upload.thumbnail.path]
        url = reverse("photo_upload_discard", args=[upload.id])
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PhotoUpload.objects.exists())
        for path in paths:
            self.assertFalse(os.path.exists(path))

    def test_cannot_discard_another_sellers_upload(self):
        upload = PhotoUpload.objects.get(id=self.upload().json()["id"])
        self.client.force_login(self.make_seller("other").user)
        url = reverse("photo_upload_discard", args=[upload.id])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(PhotoUpload.objects.exists())


class CreateWithPhotosTests(PhotoUploadTestCase):
    def pending(self, count):
        return [self.upload().json()["id"] for _ in range(count)]

    def test_save_attaches_uploads_in_posted_order(self):
        a, b, c = self.pending(3)
        response = self.client.post(
            reverse("product_create"), self.form_data(photos=[c, a, b])
        )
        product = Product.objects.get(title="Stona lampa")
        self.assertRedirects(
            response, reverse("product_seller_detail", args=[product.id])
        )
        images = list(product.images.all())
        self.assertEqual([image.order for image in images], [0, 1, 2])
        self.assertEqual(len(images), 3)
        self.assertFalse(PhotoUpload.objects.exists())
        # The files moved with the rows, they weren't copied or deleted
        for image in images:
            self.assertTrue(os.path.exists(image.image.path))
            self.assertTrue(os.path.exists(image.thumbnail.path))
            self.assertIsNotNone(image.sharpness)

    def test_order_follows_posted_ids(self):
        ids = self.pending(2)
        names = {u.id: u.image.name for u in PhotoUpload.objects.filter(id__in=ids)}
        self.client.post(
            reverse("product_create"), self.form_data(photos=list(reversed(ids)))
        )
        product = Product.objects.get(title="Stona lampa")
        self.assertEqual(
            [image.image.name for image in product.images.all()],
            [names[ids[1]], names[ids[0]]],
        )

    def test_other_sellers_and_junk_ids_are_ignored(self):
        (mine,) = self.pending(1)
        other = self.make_seller("other")
        theirs = PhotoUpload.objects.create(seller=other, image=photo())
        self.client.post(
            reverse("product_create"),
            self.form_data(photos=[str(theirs.id), "x", str(mine), str(mine)]),
        )
        product = Product.objects.get(title="Stona lampa")
        self.assertEqual(product.images.count(), 1)
        self.assertTrue(PhotoUpload.objects.filter(id=theirs.id).exists())

    def test_invalid_form_keeps_photos(self):
        a, b = self.pending(2)
        response = self.client.post(
            reverse("product_create"), self.form_data(title="", photos=[b, a])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.exists())
        self.assertContains(response, "Naziv proizvoda je obavezan.")
        html = response.content.decode()
        # Shown again, in the chosen order, and posted again on the next save
        self.assertLess(html.index(f'id="upload-{b}"'), html.index(f'id="upload-{a}"'))
        self.assertContains(
            response,
            f'<input type="hidden" name="photos" value="{a}" form="product-form">',
        )

    def test_extra_photos_over_the_limit_are_dropped(self):
        ids = self.pending(MAX_PHOTOS + 1)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("product_create"), self.form_data(photos=ids), follow=True
            )
        product = Product.objects.get(title="Stona lampa")
        self.assertEqual(product.images.count(), MAX_PHOTOS)
        self.assertFalse(PhotoUpload.objects.exists())
        self.assertContains(response, f"Sačuvano je prvih {MAX_PHOTOS} fotografija.")

    def test_without_photos_draft_asks_for_them(self):
        response = self.client.post(
            reverse("product_create"), self.form_data(), follow=True
        )
        self.assertContains(response, "Dodajte fotografije da biste ga objavili.")


class NoJavaScriptTests(PhotoUploadTestCase):
    """The file input posts photos with the form when the script can't run."""

    def test_create_with_posted_files(self):
        response = self.client.post(
            reverse("product_create"),
            self.form_data(photo_files=[photo("a.jpg"), photo("b.jpg")]),
        )
        product = Product.objects.get(title="Stona lampa")
        self.assertRedirects(
            response, reverse("product_seller_detail", args=[product.id])
        )
        self.assertEqual(product.images.count(), 2)

    def test_bad_file_is_reported_and_the_rest_saved(self):
        fake = SimpleUploadedFile("notes.jpg", b"not an image", "image/jpeg")
        response = self.client.post(
            reverse("product_create"),
            self.form_data(photo_files=[photo("a.jpg"), fake]),
            follow=True,
        )
        product = Product.objects.get(title="Stona lampa")
        self.assertEqual(product.images.count(), 1)
        self.assertContains(response, "notes.jpg: ovo nije fotografija")

    def test_posted_files_survive_an_invalid_form(self):
        response = self.client.post(
            reverse("product_create"),
            self.form_data(title="", photo_files=[photo("a.jpg")]),
        )
        upload = PhotoUpload.objects.get()
        self.assertContains(response, f'id="upload-{upload.id}"')

    def test_edit_with_posted_files_adds_to_listing(self):
        product = self.make_product()
        ProductImage.objects.create(product=product, image=photo("first.jpg"))
        self.client.post(
            reverse("product_edit", args=[product.id]),
            self.form_data(photo_files=[photo("second.jpg")]),
        )
        self.assertEqual(list(product.images.values_list("order", flat=True)), [0, 1])

    def test_edit_page_lists_photos_for_the_script(self):
        product = self.make_product()
        image = ProductImage.objects.create(product=product, image=photo())
        response = self.client.get(reverse("product_edit", args=[product.id]))
        self.assertContains(response, f'data-product-id="{product.id}"')
        self.assertContains(response, reverse("product_image_delete", args=[image.id]))
        self.assertContains(response, "js/listing-photos.js")


class PurgePhotoUploadsTests(PhotoUploadTestCase):
    def test_deletes_old_uploads_and_their_files(self):
        old = PhotoUpload.objects.create(seller=self.seller, image=photo())
        new = PhotoUpload.objects.create(seller=self.seller, image=photo())
        PhotoUpload.objects.filter(id=old.id).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        paths = [old.image.path, old.thumbnail.path]
        out = StringIO()
        with self.captureOnCommitCallbacks(execute=True):
            call_command("purge_photo_uploads", stdout=out)
        self.assertIn("Deleted 1", out.getvalue())
        self.assertEqual(list(PhotoUpload.objects.all()), [new])
        for path in paths:
            self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.exists(new.image.path))


class ReviewRegressionTests(PhotoUploadTestCase):
    """Races and leftovers found in the PR #60 review."""

    def pending(self, count):
        return [self.upload().json()["id"] for _ in range(count)]

    def test_second_submit_of_same_form_does_not_share_photos(self):
        ids = self.pending(2)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("product_create"), self.form_data(photos=ids))
            response = self.client.post(
                reverse("product_create"), self.form_data(photos=ids), follow=True
            )
        first, second = Product.objects.order_by("id")
        self.assertEqual(first.images.count(), 2)
        self.assertEqual(second.images.count(), 0)
        self.assertContains(response, "Fotografija koje više nema: 2.")
        for image in first.images.all():
            self.assertTrue(os.path.exists(image.image.path))

    def test_purge_of_a_just_attached_upload_keeps_the_files(self):
        upload = PhotoUpload.objects.get(id=self.pending(1)[0])
        product = self.make_product()
        image = upload.attach_to(product, 0)
        # The purge still holds the row it read before the save
        with self.captureOnCommitCallbacks(execute=True):
            upload.delete()
        self.assertTrue(os.path.exists(image.image.path))
        self.assertTrue(os.path.exists(image.thumbnail.path))

    def test_deleting_a_seller_removes_their_pending_files(self):
        upload = PhotoUpload.objects.get(id=self.pending(1)[0])
        paths = [upload.image.path, upload.thumbnail.path]
        with self.captureOnCommitCallbacks(execute=True):
            self.seller.user.delete()
        for path in paths:
            self.assertFalse(os.path.exists(path))

    def test_rejected_upload_never_deletes_by_client_file_name(self):
        # A bare JPEG is kept as uploaded, so its name is still the
        # client's; a file of that name at MEDIA_ROOT must survive
        bystander = os.path.join(MEDIA_ROOT, "IMG_1.jpg")
        with open(bystander, "wb") as f:
            f.write(b"someone else's file")
        unsaved = PhotoUpload(seller=self.seller)
        unsaved.image = photo("IMG_1.jpg")
        self.assertTrue(unsaved.process())
        self.assertFalse(unsaved.image._committed)
        thumb = unsaved.thumbnail.path
        with self.captureOnCommitCallbacks(execute=True):
            unsaved.discard_unsaved()
        self.assertTrue(os.path.exists(bystander))
        self.assertFalse(os.path.exists(thumb))

    def test_purged_uploads_are_reported_on_save(self):
        (gone,) = self.pending(1)
        PhotoUpload.objects.filter(id=gone).delete()
        response = self.client.post(
            reverse("product_create"), self.form_data(photos=[gone]), follow=True
        )
        self.assertContains(response, "Fotografija koje više nema: 1.")
        response = self.client.post(
            reverse("product_create"), self.form_data(title="", photos=[gone])
        )
        self.assertContains(response, "Fotografija koje više nema: 1.")

    def test_cover_tip_is_kept_apart_from_other_tips(self):
        data = self.upload(photo("wide.jpg", size=(2000, 800))).json()
        self.assertIn("seče na kvadrat", data["cover_tip"])
        self.assertFalse(any("kvadrat" in tip for tip in data["tips"]))
        # Server-rendered: shown on the first photo only
        product = self.make_product()
        ProductImage.objects.create(product=product, image=photo("w1.jpg", (2000, 800)))
        ProductImage.objects.create(
            product=product, image=photo("w2.jpg", (2000, 800)), order=1
        )
        response = self.client.get(reverse("product_edit", args=[product.id]))
        html = response.content.decode()
        self.assertEqual(
            html.count(
                'class="photo-cover-tip text-[11px] leading-snug text-amber-700 mt-1"'
            ),
            1,
        )

    def test_bad_product_id_is_not_found(self):
        response = self.client.post(
            reverse("photo_upload"), {"photo": photo(), "product": "abc"}
        )
        self.assertEqual(response.status_code, 404)


class PublishFromCreateTests(PhotoUploadTestCase):
    """'Sačuvaj i objavi' on a new listing (#44, part 3)."""

    def test_publish_with_photo(self):
        ids = [self.upload().json()["id"]]
        response = self.client.post(
            reverse("product_create"),
            self.form_data(photos=ids, action="publish"),
            follow=True,
        )
        product = Product.objects.get(title="Stona lampa")
        self.assertEqual(product.status, "published")
        self.assertIsNotNone(product.listed_at)
        self.assertContains(response, "je objavljen i vidljiv kupcima")

    def test_publish_without_photo_saves_draft_and_says_why(self):
        response = self.client.post(
            reverse("product_create"), self.form_data(action="publish"), follow=True
        )
        product = Product.objects.get(title="Stona lampa")
        self.assertEqual(product.status, "draft")
        self.assertContains(response, "Nacrt je sačuvan, ali: Dodajte bar jednu")

    def test_publish_respects_listing_limit(self):
        ids = [self.upload().json()["id"]]
        with mock.patch.object(Seller, "can_publish", return_value=False):
            self.client.post(
                reverse("product_create"),
                self.form_data(photos=ids, action="publish"),
            )
        self.assertEqual(Product.objects.get(title="Stona lampa").status, "draft")

    def test_plain_save_stays_draft(self):
        ids = [self.upload().json()["id"]]
        self.client.post(
            reverse("product_create"), self.form_data(photos=ids, action="save")
        )
        self.assertEqual(Product.objects.get(title="Stona lampa").status, "draft")


class StepsAndPreviewTests(PhotoUploadTestCase):
    def test_form_has_steps_preview_and_shared_tip_texts(self):
        response = self.client.get(reverse("product_create"))
        for anchor in ("#fotografije", "#detalji", "#pregled"):
            self.assertContains(response, f'href="{anchor}"')
        self.assertContains(response, 'id="preview-card"')
        self.assertContains(response, self.seller.shop_name)
        # The live tips show the server's own messages
        for message in TEXT_TIPS.values():
            self.assertContains(response, escape(message))
        self.assertContains(response, 'id="listing-tip-rules"')
        self.assertContains(response, "js/listing-preview.js")
        self.assertContains(response, 'value="publish"')

    def test_edit_form_has_preview_with_cover(self):
        product = self.make_product()
        image = ProductImage.objects.create(product=product, image=photo())
        response = self.client.get(reverse("product_edit", args=[product.id]))
        self.assertContains(response, 'id="pregled"')
        self.assertContains(
            response, f'<img id="preview-image" src="{image.thumb_url}"'
        )
