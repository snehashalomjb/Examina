"""OCR pre-pass over handwritten answer scans (Tesseract).

Handwritten ``image_upload`` answers go straight to a human - the spec routes them past
the automatic grader on purpose. This module runs first and attaches whatever text
Tesseract can make out, so the examiner opens the queue with something searchable and
skimmable beside the image instead of a bare photograph.

The output is *advisory*. Handwriting recognition is unreliable enough that a score must
never be derived from it; ``ocr_confidence`` is stored alongside so the UI can say how
much to trust what it shows.

Tesseract is a hard dependency of the deployment (see the Dockerfile and the README's
Windows note). It is still called defensively: an OCR failure at upload time must never
cost a candidate their answer, so callers record the failure and move on.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytesseract
from PIL import Image

from app.core.config import settings
from app.core.images import load_image
from app.core.logging_config import get_logger

logger = get_logger("ocr")

#: Tesseract reports -1 for boxes it did not score; those are excluded from the mean.
_NO_CONFIDENCE = -1.0

#: PSM 6 - "a single uniform block of text" - is the closest fit for an answer sheet.
_CONFIG = "--oem 1 --psm 6"


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float  # 0..1, mean over the words Tesseract was willing to score
    engine: str

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


def _configure() -> None:
    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


def engine_version() -> str | None:
    """The installed Tesseract version, or None when the binary cannot be reached."""
    _configure()
    try:
        return str(pytesseract.get_tesseract_version())
    except Exception as exc:  # noqa: BLE001 - any failure here means "not available"
        logger.warning("Tesseract is not reachable: %s", exc)
        return None


def extract_text(data: bytes) -> OcrResult:
    """Read an image and return its recognised text with a mean word confidence.

    Raises ``RuntimeError`` if Tesseract cannot be run at all - the caller decides
    whether that is fatal (it never is on the candidate's upload path).
    """
    _configure()
    image = _prepare(load_image(data))

    try:
        data_frame = pytesseract.image_to_data(
            image, lang=settings.OCR_LANGUAGES, config=_CONFIG, output_type=pytesseract.Output.DICT
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract is not installed or not on PATH. Install it and/or set TESSERACT_CMD."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - a corrupt page must not escape as a 500
        raise RuntimeError(f"OCR failed: {exc}") from exc

    words: list[str] = []
    confidences: list[float] = []
    for word, raw_confidence in zip(
        data_frame.get("text", []), data_frame.get("conf", []), strict=False
    ):
        if not word or not word.strip():
            continue
        words.append(word)
        try:
            value = float(raw_confidence)
        except (TypeError, ValueError):
            continue
        if value > _NO_CONFIDENCE:
            confidences.append(value)

    text = " ".join(words).strip()
    confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
    return OcrResult(text=text, confidence=round(confidence, 4), engine="tesseract")


def _prepare(image: Image.Image) -> Image.Image:
    """Greyscale and up-scale small scans - Tesseract wants roughly 300 DPI text.

    Nothing more aggressive than this: binarising or de-skewing a phone photo of
    handwriting tends to destroy more strokes than it recovers.
    """
    if image.mode != "L":
        image = image.convert("L")

    long_edge = max(image.size)
    if long_edge < 1400:
        scale = 1400 / long_edge
        image = image.resize(
            (int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS
        )
    return image
