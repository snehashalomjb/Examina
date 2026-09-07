"""PDF text extraction for the question-bank importer.

An examiner uploads a syllabus, a past paper or a set of lecture notes; this pulls the
text out so the AI generator has source material to work from. Nothing here interprets
the content - it only turns bytes into text and reports what it could not read.

``pypdf`` is a pure-Python parser, so it handles a digital PDF (one with a text layer)
and returns nothing useful for a pure scan. That case is reported rather than silently
producing an empty prompt, because "generated 5 questions from nothing" is worse than
"this PDF has no text layer".
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from app.core.logging_config import get_logger

logger = get_logger("pdf_extract")

#: A prompt built from more than this is truncated. Well past a long syllabus, and far
#: short of any provider's context limit, so the cap never surprises the examiner.
MAX_SOURCE_CHARS = 40_000

#: Below this there is nothing for the generator to work from - almost always a scan.
MIN_USEFUL_CHARS = 200


class PdfError(Exception):
    """The upload could not be read as a PDF, or carries no extractable text."""


@dataclass(frozen=True)
class PdfText:
    text: str
    pages: int
    #: Pages that yielded no text at all - a mixed digital/scanned document is common.
    empty_pages: int
    truncated: bool

    @property
    def characters(self) -> int:
        return len(self.text)


def extract_pdf_text(data: bytes, *, max_chars: int = MAX_SOURCE_CHARS) -> PdfText:
    """Pull the text layer out of a PDF.

    Raises ``PdfError`` when the file is not a readable PDF, is encrypted, or holds too
    little text to generate from.
    """
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise PdfError(
            "PDF import is not available on this server - the pypdf package is missing"
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError as exc:
        raise PdfError("That file could not be read as a PDF") from exc
    except Exception as exc:  # pypdf raises a wide range on malformed input
        raise PdfError("That file could not be read as a PDF") from exc

    if reader.is_encrypted:
        # An empty user password is the common "protected but readable" case; anything
        # else needs a password we do not have.
        try:
            if reader.decrypt("") == 0:
                raise PdfError("That PDF is password protected - remove the password first")
        except PdfError:
            raise
        except Exception as exc:
            raise PdfError("That PDF is password protected - remove the password first") from exc

    chunks: list[str] = []
    empty_pages = 0
    total = 0
    truncated = False

    for index, page in enumerate(reader.pages):
        try:
            page_text = (page.extract_text() or "").strip()
        except Exception:
            # One unreadable page should not lose the rest of the document.
            logger.warning("Could not extract text from PDF page %d", index + 1)
            page_text = ""

        if not page_text:
            empty_pages += 1
            continue

        remaining = max_chars - total
        if remaining <= 0:
            truncated = True
            break
        if len(page_text) > remaining:
            page_text = page_text[:remaining]
            truncated = True

        chunks.append(page_text)
        total += len(page_text)

    text = "\n\n".join(chunks)
    pages = len(reader.pages)

    if len(text) < MIN_USEFUL_CHARS:
        raise PdfError(
            "No readable text was found in that PDF. It looks like a scan - "
            "upload a digital PDF, or use AI Tools to generate from a topic instead."
        )

    logger.info(
        "Extracted %d chars from %d page(s) (%d empty, truncated=%s)",
        len(text),
        pages,
        empty_pages,
        truncated,
    )
    return PdfText(text=text, pages=pages, empty_pages=empty_pages, truncated=truncated)
