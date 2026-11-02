"""
Server-side processing for product photos.

Every saved photo is rotated upright from its EXIF orientation, stripped of
metadata (phone photos carry GPS coordinates in EXIF or XMP), capped at
MAX_EDGE pixels and given a THUMB_EDGE thumbnail for grids. The colour
profile is kept so wide-gamut phone photos don't turn dull. Simple quality
measurements are kept so sellers get tips on dark, blurry or small photos
(products.quality).
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
# Largest image decoded at full size (25 MP is ~75 MB as RGB; gunicorn
# workers are sized at 150 MB). JPEGs are decoded already scaled down to
# about MAX_EDGE, so this only limits PNG/WebP/GIF and huge JPEGs.
MAX_PIXELS = 25_000_000


@dataclass
class ProcessedPhoto:
    image: ContentFile | None  # None: the upload is kept as it is
    thumbnail: ContentFile
    width: int
    height: int
    brightness: float  # mean luminance, 0 (black) to 255 (white)
    sharpness: float  # variance of the edge map; low means blurry


def _jpeg(img, quality, icc_profile=None):
    # Pillow re-saves some metadata it finds in img.info (such as a JPEG
    # comment), and convert()/copy() carry info along; write none of it
    img.info = {}
    buffer = BytesIO()
    options = {"quality": quality, "optimize": True, "progressive": True}
    if icc_profile:
        options["icc_profile"] = icc_profile
    img.save(buffer, format="JPEG", **options)
    return buffer.getvalue()


def _flatten(img):
    """RGB on white, so transparent PNG/WebP areas don't turn black."""
    if img.mode.startswith("I"):
        # 16/32-bit grayscale: scale to 8 bits instead of clipping to white
        img = img.convert("I").point(lambda value: value * (1 / 256)).convert("L")
    has_alpha = img.mode in ("RGBA", "LA", "PA", "RGBa", "La") or (
        img.mode == "P" and "transparency" in img.info
    )
    if has_alpha:
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def _is_bare_jpeg(source):
    """A JPEG with nothing but the JFIF header: no EXIF, XMP, IPTC or comment."""
    if source.format != "JPEG" or "comment" in source.info:
        return False
    return all(
        marker == "APP0" and data.startswith(b"JFIF")
        for marker, data in getattr(source, "applist", [])
    )


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

    Returns None when the file is not a readable image or too large to
    decode; the caller then keeps the file untouched without a thumbnail.
    With keep_original the stored photo is never rewritten, only measured
    and thumbnailed.
    """
    try:
        file.seek(0)
        source = Image.open(file)
        original_size = source.size
        if source.format == "JPEG":
            # Let the decoder scale down by 1/2, 1/4 or 1/8 while reading,
            # staying at or above MAX_EDGE: a 48 MP photo never sits in memory
            source.draft("RGB", (MAX_EDGE, MAX_EDGE))
        if source.width * source.height > MAX_PIXELS:
            logger.warning("Photo %s is too large to process: %s", name, source.size)
            return None
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
    resized = max(img.size) > MAX_EDGE or source.size != original_size
    if max(img.size) > MAX_EDGE:
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)

    # A small JPEG with no metadata at all is stored as uploaded, so it isn't
    # re-encoded and loses nothing
    untouched = _is_bare_jpeg(source) and not (rotated or resized)

    icc_profile = source.info.get("icc_profile")
    stem = os.path.splitext(os.path.basename(name))[0]
    image = None
    if not keep_original and not untouched:
        image = ContentFile(_jpeg(img, JPEG_QUALITY, icc_profile), name=f"{stem}.jpg")

    thumb = img.copy()
    thumb.thumbnail((THUMB_EDGE, THUMB_EDGE), Image.Resampling.LANCZOS)
    brightness, sharpness = measure(thumb)
    if image is None:
        # The stored file keeps its own size (upright, as browsers show it)
        width, height = original_size
        if rotated and exif.get(ORIENTATION) in (5, 6, 7, 8):
            width, height = height, width
    else:
        width, height = img.size

    return ProcessedPhoto(
        image=image,
        thumbnail=ContentFile(
            _jpeg(thumb, THUMB_QUALITY, icc_profile), name=f"{stem}_thumb.jpg"
        ),
        width=width,
        height=height,
        brightness=brightness,
        sharpness=sharpness,
    )
