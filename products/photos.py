"""
Photos on the listing form: staged uploads and the items the form shows.

On a new listing each photo is uploaded on its own as a PhotoUpload before
the product exists; saving the form attaches them in the chosen order. On
an existing listing photos are added straight to the product. Without
JavaScript the form posts the files itself and they take the same path.
"""

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse

from sellers.models import Seller

from .forms import (
    MAX_PENDING_UPLOADS,
    MAX_PHOTOS,
    MAX_UPLOAD_MB,
    MB,
    validate_photo,
)
from .models import PhotoUpload, Product, ProductImage
from .quality import check_photo


@dataclass
class PhotoItem:
    """One photo as the listing form shows it."""

    id: int
    kind: str  # "upload" (not on a product yet) or "image"
    thumb_url: str
    remove_url: str
    tips: list = field(default_factory=list)
    # Shown only while the photo is first: it depends on the position, which
    # the seller changes in the browser
    cover_tip: str = ""

    def as_json(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "thumb_url": self.thumb_url,
            "remove_url": self.remove_url,
            "tips": self.tips,
            "cover_tip": self.cover_tip,
        }


def photo_item(photo):
    if isinstance(photo, PhotoUpload):
        kind, remove_url = "upload", reverse("photo_upload_discard", args=[photo.id])
    else:
        kind, remove_url = "image", reverse("product_image_delete", args=[photo.id])
    tips, cover_tip = [], ""
    for tip in check_photo(photo, cover=True):
        if tip.check == "cover":
            cover_tip = tip.message
        else:
            tips.append(tip.message)
    return PhotoItem(photo.id, kind, photo.thumb_url, remove_url, tips, cover_tip)


def posted_ids(raw_ids):
    """Positive integer ids from the form, without duplicates, in order."""
    ids = []
    for raw in raw_ids:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in ids:
            ids.append(value)
    return ids


def pending_uploads(seller, ids, lock=False):
    """
    The seller's uploads with these ids, in that order. With lock the rows
    are locked until the transaction ends, so two saves of one form can't
    both attach them.
    """
    uploads = PhotoUpload.objects.filter(seller=seller, id__in=ids)
    if lock:
        uploads = uploads.select_for_update()
    found = {upload.id: upload for upload in uploads}
    return [found[i] for i in ids if i in found]


def missing_message(count):
    return (
        f"Fotografija koje više nema: {count}. Otpremljene fotografije čuvamo "
        "24 sata dok se oglas ne sačuva; dodajte ih ponovo."
    )


def room_for_photo(seller, product=None):
    """Why another photo can't be added, or None if it can."""
    if product is not None:
        if product.images.count() >= MAX_PHOTOS:
            return f"Oglas može imati najviše {MAX_PHOTOS} fotografija."
    elif seller.photo_uploads.count() >= MAX_PENDING_UPLOADS:
        return (
            "Imate previše otpremljenih fotografija u nesačuvanim oglasima. "
            "Sačuvajte ovaj oglas ili pokušajte ponovo sutra."
        )
    return None


def add_photo(seller, file, product=None):
    """
    Validate, process and store one photo: on product if given, otherwise
    as the seller's pending upload. Raises ValidationError with a message
    for the seller.
    """
    problem = room_for_photo(seller, product)
    if problem:
        raise ValidationError(problem)
    validate_photo(file)
    photo = PhotoUpload(seller=seller) if product is None else ProductImage()
    photo.image = file
    # The slow part, done before taking any lock
    if not photo.process():
        raise ValidationError(
            f"{file.name}: fotografiju nije moguće obraditi (prevelika ili "
            "oštećena). Pokušajte sa manjom fotografijom."
        )
    with transaction.atomic():
        # Parallel uploads take turns on the seller (pending cap) or the
        # listing (photo cap and order), so the checks hold
        if product is None:
            seller = Seller.objects.select_for_update().get(pk=seller.pk)
            problem = room_for_photo(seller)
            if not problem:
                photo.save()
        else:
            product = Product.objects.select_for_update().get(pk=product.pk)
            problem = room_for_photo(seller, product)
        if product is not None and not problem:
            last = product.images.aggregate(last=models.Max("order"))["last"]
            photo.product = product
            photo.order = 0 if last is None else last + 1
            photo.alt_text = f"{product.title} – fotografija {photo.order + 1}"
            photo.save()
    if problem:
        # Outside the atomic block, so the cleanup isn't rolled back with it
        photo.discard_unsaved()
        raise ValidationError(problem)
    return photo


def add_posted_files(request, seller, product=None):
    """
    Photos sent with the form itself (no JavaScript). Returns the photos
    stored and the error messages for the ones that weren't.
    """
    files = request.FILES.getlist("photo_files")
    if sum(f.size for f in files) > MAX_UPLOAD_MB * MB:
        return [], [
            f"Izabrane fotografije zajedno prelaze {MAX_UPLOAD_MB} MB. "
            "Dodajte ih u više navrata."
        ]
    added, errors = [], []
    for file in files:
        try:
            added.append(add_photo(seller, file, product))
        except ValidationError as error:
            errors.extend(error.messages)
    return added, errors
