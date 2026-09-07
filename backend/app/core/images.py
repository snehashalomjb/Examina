"""Server-side image derivatives for uploaded answer scans and webcam snapshots.

Thumbnails are generated here rather than in the browser for the same reason scores are
computed on the server: what a client uploads is not trusted to be what it claims. The
examiner queue renders these, so a review page of thirty scripts costs a few hundred
kilobytes instead of tens of megabytes.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.logging_config import get_logger

logger = get_logger("images")

#: Long-edge size of a generated thumbnail. Big enough that an examiner can tell whether
#: a scan is legible before opening the full image.
THUMBNAIL_MAX_EDGE = 512
THUMBNAIL_QUALITY = 78

#: Guard against a decompression bomb: a small file that expands to a huge bitmap.
MAX_PIXELS = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImageError(ValueError):
    """The uploaded bytes are not a usable image."""


def load_image(data: bytes) -> Image.Image:
    """Decode, apply EXIF rotation, and drop to RGB.

    Phone cameras write the orientation into EXIF rather than rotating the pixels, so a
    scan photographed in portrait arrives sideways unless it is transposed here.
    """
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageError("That file is not a readable image") from exc

    if image.width * image.height > MAX_PIXELS:
        raise ImageError("That image is too large to process")

    image = ImageOps.exif_transpose(image)
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    return image


def make_thumbnail(data: bytes, *, max_edge: int = THUMBNAIL_MAX_EDGE) -> bytes:
    """Return JPEG bytes of a down-scaled copy. Never upscales a small original."""
    image = load_image(data)
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
    return buffer.getvalue()
