"""Thumbnail generation and the OCR pre-pass over handwritten scans.

The OCR tests render text with PIL and read it back, so they exercise the real Tesseract
path rather than a mock. They skip - rather than fail - where the binary is absent, since
a machine without Tesseract is a deployment gap, not a broken rule.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

from app.core.images import ImageError, load_image, make_thumbnail
from app.services import ocr

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _png(width: int, height: int, colour: tuple[int, int, int] = (200, 30, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _typed_page(text: str, *, width: int = 1000, height: int = 300) -> bytes:
    """A clean rendered page. Real answers are handwritten; this is legible on purpose so
    the test asserts the pipeline works, not that Tesseract can read handwriting."""
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    # The default bitmap font is tiny, so draw large and let the OCR up-scaler help.
    draw.text((40, height // 2 - 10), text, fill="black", font_size=48)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class TestThumbnails:
    def test_a_large_scan_is_reduced_to_the_long_edge(self):
        thumb = make_thumbnail(_png(2400, 1600))
        image = Image.open(io.BytesIO(thumb))
        assert max(image.size) == 512
        assert image.format == "JPEG"

    def test_aspect_ratio_is_preserved(self):
        thumb = make_thumbnail(_png(2000, 1000))
        image = Image.open(io.BytesIO(thumb))
        assert image.size == (512, 256)

    def test_a_small_image_is_not_upscaled(self):
        thumb = make_thumbnail(_png(120, 90))
        assert Image.open(io.BytesIO(thumb)).size == (120, 90)

    def test_the_thumbnail_is_much_smaller_than_the_original(self):
        original = _png(2400, 1600)
        assert len(make_thumbnail(original)) < len(original)

    def test_a_transparent_png_survives_the_jpeg_conversion(self):
        buffer = io.BytesIO()
        Image.new("RGBA", (800, 600), (10, 20, 30, 0)).save(buffer, format="PNG")
        image = Image.open(io.BytesIO(make_thumbnail(buffer.getvalue())))
        assert image.mode == "RGB"

    def test_garbage_bytes_are_refused_clearly(self):
        with pytest.raises(ImageError, match="not a readable image"):
            make_thumbnail(b"this is a PDF, or a lie, but it is not an image")

    def test_load_image_normalises_mode(self):
        assert load_image(_png(50, 50)).mode in {"RGB", "L"}


@pytest.fixture(scope="module")
def tesseract() -> str:
    version = ocr.engine_version()
    if version is None:
        pytest.skip("Tesseract is not installed on this machine")
    return version


class TestOcr:
    def test_it_reads_rendered_text(self, tesseract):
        result = ocr.extract_text(_typed_page("HYDROGEN BONDING"))
        assert "HYDROGEN" in result.text.upper()
        assert result.engine == "tesseract"

    def test_confidence_is_a_zero_to_one_fraction(self, tesseract):
        result = ocr.extract_text(_typed_page("ENTROPY INCREASES"))
        assert 0.0 <= result.confidence <= 1.0

    def test_a_blank_page_reads_as_empty(self, tesseract):
        result = ocr.extract_text(_png(1200, 800, (255, 255, 255)))
        assert result.is_empty

    def test_an_unreadable_file_raises_an_image_error(self, tesseract):
        with pytest.raises(ImageError):
            ocr.extract_text(b"not an image at all")
