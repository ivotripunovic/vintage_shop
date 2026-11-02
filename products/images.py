"""
Server-side processing for product photos.

Every saved photo is rotated upright from its EXIF orientation, stripped of
metadata (phone photos carry GPS coordinates), capped at MAX_EDGE pixels and
given a THUMB_EDGE thumbnail for grids. Simple quality measurements are kept
so sellers can get tips on dark, blurry or small photos (products.quality).
"""

import logging
import os
from dataclasses import dataclass
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

logger = logging.getLogger(__name__)

MAX_EDGE = 2000  # long edge of the stored photo
THUMB_EDGE = 600  # long edge of the grid thumbnail (~300px cards at 2x)
JPEG_QUALITY = 85
THUMB_QUALITY = 80
# Measurements are taken on a copy this size, so they don't depend on the
# photo's resolution
MEASURE_EDGE = 512
ORIENTATION = 0x0112  # EXIF tag


@dataclass
class ProcessedPhoto:
    image: ContentFile | None  # None: the upload is kept as it is
    thumbnail: ContentFile
    width: int
    height: int
    brightness: float  # mean luminance, 0 (black) to 255 (white)
    sharpness: float  # variance of the edge map; low means blurry


def _jpeg(img, quality):
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buffer.getvalue()


def _flatten(img):
    """RGB on white, so transparent PNG/WebP areas don't turn black."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def measure(img):
    """Brightness and sharpness of an upright RGB image."""
    gray = img.convert("L")
    gray.thumbnail((MEASURE_EDGE, MEASURE_EDGE))
    brightness = ImageStat.Stat(gray).mean[0]
    sharpness = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0]
    return round(brightness, 1), round(sharpness, 1)


def process_photo(file, name, keep_original=False):
    """
    Process an uploaded or stored photo.

    Returns None when the file is not a readable image; the caller then keeps
    the file untouched without a thumbnail. With keep_original the stored
    photo is never rewritten, only measured and thumbnailed.
    """
    try:
        file.seek(0)
        source = Image.open(file)
        source.load()
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
    ) as error:
        logger.warning("Cannot process photo %s: %s", name, error)
        return None

    exif = source.getexif()
    rotated = exif.get(ORIENTATION, 1) != 1
    upright = ImageOps.exif_transpose(source) if rotated else source
    img = _flatten(upright)
    resized = max(img.size) > MAX_EDGE
    if resized:
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)

    # A small upright JPEG without metadata is stored as uploaded, so it isn't
    # re-encoded and loses nothing
    has_metadata = bool(source.info.get("exif") or exif)
    untouched = source.format == "JPEG" and not (rotated or resized or has_metadata)

    stem = os.path.splitext(os.path.basename(name))[0]
    image = None
    if not keep_original and not untouched:
        image = ContentFile(_jpeg(img, JPEG_QUALITY), name=f"{stem}.jpg")

    thumb = img.copy()
    thumb.thumbnail((THUMB_EDGE, THUMB_EDGE), Image.Resampling.LANCZOS)
    brightness, sharpness = measure(img)
    # Size of the photo as stored: the kept upload, or the processed copy
    width, height = upright.size if image is None else img.size

    return ProcessedPhoto(
        image=image,
        thumbnail=ContentFile(_jpeg(thumb, THUMB_QUALITY), name=f"{stem}_thumb.jpg"),
        width=width,
        height=height,
        brightness=brightness,
        sharpness=sharpness,
    )
