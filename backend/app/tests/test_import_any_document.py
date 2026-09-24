"""Importing questions from every document type the importer accepts.

Each test builds a small real file of that type - no fixtures checked in - holding the
same two-question paper, and asserts the questions, options and answer keys come out
the same whichever program the examiner wrote it in.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.services.question_import import (
    SUPPORTED_EXTENSIONS,
    ImportError_,
    _rtf_to_text,
    parse_questions,
)

PAPER = [
    "Question 1 (Easy)",
    "Which SQL command retrieves data from a table?",
    "A. INSERT",
    "B. SELECT",
    "C. UPDATE",
    "Answer: B",
    "2. Which clause filters groups after GROUP BY?",
    "A. WHERE",
    "B. HAVING",
    "Answer: B. HAVING",
]


def _assert_the_paper(rows) -> None:
    assert len(rows) == 2, [r.body for r in rows]
    assert [r.problems for r in rows] == [[], []]
    assert rows[0].body == "Which SQL command retrieves data from a table?"
    assert rows[0].difficulty.value == "easy"
    assert [o.is_correct for o in rows[0].options] == [False, True, False]
    assert [o.text for o in rows[1].options] == ["WHERE", "HAVING"]
    assert [o.is_correct for o in rows[1].options] == [False, True]


class TestTextFormats:
    def test_plain_text(self):
        data = "\n".join(PAPER).encode()
        _assert_the_paper(parse_questions(filename="paper.txt", data=data))

    def test_utf16_text_from_notepad(self):
        data = "\n".join(PAPER).encode("utf-16")
        _assert_the_paper(parse_questions(filename="paper.txt", data=data))

    def test_markdown_decoration_is_ignored(self):
        lines = ["# SQL quiz", "## Question 1 (Easy)", "**Which SQL command retrieves data from a table?**",
                 *PAPER[2:]]
        _assert_the_paper(parse_questions(filename="paper.md", data="\n".join(lines).encode()))

    def test_a_txt_with_a_question_header_is_still_read_as_csv(self):
        data = b"Question,Type,Option A,Option B,Correct\nIs 2 even?,mcq,yes,no,A\n"
        rows = parse_questions(filename="bank.txt", data=data)
        assert [r.body for r in rows] == ["Is 2 even?"]
        assert rows[0].ok, rows[0].problems

    def test_rtf(self):
        body = r"\par ".join(line.replace("{", r"\{").replace("}", r"\}") for line in PAPER)
        rtf = r"{\rtf1\ansi{\fonttbl{\f0 Arial;}}{\colortbl;\red0\green0\blue0;}\f0 " + body + "}"
        _assert_the_paper(parse_questions(filename="paper.rtf", data=rtf.encode()))

    def test_rtf_escapes_are_decoded(self):
        bs = chr(92)  # a backslash, built rather than escaped
        rtf = "{" + bs + "rtf1 caf" + bs + "'e9 " + bs + "u8364? done" + bs + "par next}"
        assert _rtf_to_text(rtf) == "caf" + chr(0xE9) + " " + chr(0x20AC) + " done" + chr(10) + "next"


class TestMarkupFormats:
    def test_html_text(self):
        html = "<html><head><style>p{}</style></head><body>" + "".join(
            f"<p>{line}</p>" for line in PAPER
        ) + "</body></html>"
        _assert_the_paper(parse_questions(filename="paper.html", data=html.encode()))

    def test_html_question_table_wins(self):
        html = (
            "<p>1. A stray prose question</p><table>"
            "<tr><th>Question</th><th>Type</th><th>Option A</th><th>Option B</th><th>Correct</th></tr>"
            "<tr><td>Is 2 even?</td><td>mcq</td><td>yes</td><td>no</td><td>A</td></tr></table>"
        )
        rows = parse_questions(filename="bank.htm", data=html.encode())
        assert [r.body for r in rows] == ["Is 2 even?"]

    def test_json_list(self):
        data = json.dumps([
            {"question": "Which SQL command retrieves data?", "type": "mcq",
             "options": ["INSERT", "SELECT"], "answer": "B"},
            {"question": "Which clause filters groups?", "type": "mcq",
             "options": [{"text": "WHERE"}, {"text": "HAVING", "is_correct": True}]},
        ]).encode()
        rows = parse_questions(filename="bank.json", data=data)
        assert [r.problems for r in rows] == [[], []]
        assert [o.is_correct for o in rows[0].options] == [False, True]
        assert [o.is_correct for o in rows[1].options] == [False, True]

    def test_json_wrapped_in_questions(self):
        data = json.dumps({"questions": [
            {"question": "Is 2 even?", "type": "mcq", "options": ["yes", "no"], "correct": "A"}
        ]}).encode()
        assert parse_questions(filename="bank.json", data=data)[0].ok

    def test_invalid_json_is_refused_by_name(self):
        with pytest.raises(ImportError_, match="not valid JSON"):
            parse_questions(filename="bank.json", data=b"{nope")


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class TestOfficeFormats:
    def test_odt(self):
        ns = 'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" ' \
             'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
        paragraphs = "".join(f"<text:p>{line}</text:p>" for line in PAPER)
        content = f'<office:document-content {ns}><office:body><office:text>{paragraphs}' \
                  "</office:text></office:body></office:document-content>"
        data = _zip({"mimetype": "application/vnd.oasis.opendocument.text", "content.xml": content})
        _assert_the_paper(parse_questions(filename="paper.odt", data=data))

    def test_pptx_reads_slides_in_order(self):
        ns = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" ' \
             'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'

        def slide(lines):
            paras = "".join(f"<a:p><a:r><a:t>{line}</a:t></a:r></a:p>" for line in lines)
            return f"<p:sld {ns}><p:cSld><p:spTree><p:sp><p:txBody>{paras}</p:txBody>" \
                   "</p:sp></p:spTree></p:cSld></p:sld>"

        # slide10 sorts before slide2 as text; it must still come last.
        data = _zip({
            "ppt/slides/slide1.xml": slide(PAPER[:6]),
            "ppt/slides/slide10.xml": slide(PAPER[9:]),
            "ppt/slides/slide2.xml": slide(PAPER[6:9]),
        })
        _assert_the_paper(parse_questions(filename="deck.pptx", data=data))

    def test_old_binary_office_files_explain_what_to_do(self, monkeypatch):
        import shutil

        monkeypatch.setattr(shutil, "which", lambda _name: None)
        with pytest.raises(ImportError_, match=r"Save it as \.docx"):
            parse_questions(filename="paper.doc", data=b"\xd0\xcf\x11\xe0")


def _paper_image() -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    page = Image.new("RGB", (1700, 1200), "white")
    draw = ImageDraw.Draw(page)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except OSError:
        font = ImageFont.load_default(size=40)
    for n, line in enumerate(PAPER):
        draw.text((100, 80 + n * 95), line, fill="black", font=font)
    buffer = io.BytesIO()
    page.save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def tesseract():
    from app.services.ocr import engine_version

    if engine_version() is None:
        pytest.skip("Tesseract is not installed on this machine")


class TestOcrFormats:
    def test_a_photo_of_a_paper_is_read_with_ocr(self, tesseract):
        _assert_the_paper(parse_questions(filename="scan.png", data=_paper_image()))

    def test_a_word_file_of_pasted_scans_is_read_with_ocr(self, tesseract):
        docx = pytest.importorskip("docx")
        document = docx.Document()
        document.add_picture(io.BytesIO(_paper_image()))
        buffer = io.BytesIO()
        document.save(buffer)
        _assert_the_paper(parse_questions(filename="scan.docx", data=buffer.getvalue()))

    def test_an_image_with_no_questions_says_so(self, tesseract):
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (400, 300), "white").save(buffer, "PNG")
        with pytest.raises(ImportError_, match="No questions were found in this image"):
            parse_questions(filename="blank.jpg", data=buffer.getvalue())


def test_every_advertised_extension_has_a_reader():
    for ext in ("txt", "md", "rtf", "html", "json", "docx", "odt", "pptx", "pdf", "png", "jpg"):
        assert ext in SUPPORTED_EXTENSIONS


def test_an_unknown_extension_lists_what_is_supported():
    with pytest.raises(ImportError_, match=r"Supported: .*\.pptx"):
        parse_questions(filename="archive.zip", data=b"PK")
