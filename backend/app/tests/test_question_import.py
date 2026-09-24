"""Importing questions from a spreadsheet, CSV or Word document.

The behaviour worth protecting here is not "the happy path parses". It is that a bad
row is *reported* rather than dropped: an importer that silently discards the four
rows it could not read leaves an examiner publishing an exam four questions short and
finding out from a candidate.
"""

from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ExamStatus, QuestionSource, UserRole
from app.services.question_import import ImportError_, parse_questions
from app.tests.conftest import auth_headers, make_exam, make_question, make_subject, make_user

HEADER = [
    "Question",
    "Type",
    "Difficulty",
    "Topic",
    "Marks",
    "Option A",
    "Option B",
    "Option C",
    "Option D",
    "Correct",
    "Model Answer",
]


def _csv(rows: list[list[str]], header: list[str] | None = None) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header or HEADER)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _mcq_row(body: str = "What is supervised learning?", correct: str = "B") -> list[str]:
    return [
        body,
        "mcq",
        "medium",
        "Machine Learning",
        "2",
        "Learning without data",
        "Learning from labelled data",
        "Removing training data",
        "Encrypting data",
        correct,
        "",
    ]


class TestParsing:
    def test_a_clean_mcq_row_parses_with_the_right_option_marked(self):
        rows = parse_questions(filename="q.csv", data=_csv([_mcq_row()]))
        assert len(rows) == 1
        row = rows[0]
        assert row.ok, row.problems
        assert row.question_type.value == "mcq"
        assert row.marks == 2
        assert [o.is_correct for o in row.options] == [False, True, False, False]

    def test_the_row_number_matches_what_the_examiner_sees_in_excel(self):
        rows = parse_questions(filename="q.csv", data=_csv([_mcq_row(), _mcq_row("Another?")]))
        # Header is row 1, so the first question is row 2.
        assert [r.row_number for r in rows] == [2, 3]

    def test_column_names_are_matched_loosely(self):
        header = ["question_text", "QUESTION TYPE", "Level", "Points", "A", "B", "Answer"]
        data = _csv(
            [["Pick one.", "single choice", "easy", "3", "first", "second", "b"]], header=header
        )
        row = parse_questions(filename="q.csv", data=data)[0]
        assert row.ok, row.problems
        assert row.marks == 3
        assert row.difficulty.value == "easy"
        assert [o.is_correct for o in row.options] == [False, True]

    def test_a_numbered_answer_names_an_option(self):
        row = parse_questions(filename="q.csv", data=_csv([_mcq_row(correct="2")]))[0]
        assert row.ok, row.problems
        assert row.options[1].is_correct

    def test_true_false_is_built_from_the_answer_word(self):
        header = ["Question", "Type", "Correct"]
        data = _csv([["Backpropagation uses the chain rule.", "true/false", "TRUE"]], header)
        row = parse_questions(filename="q.csv", data=data)[0]
        assert row.ok, row.problems
        assert [(o.text, o.is_correct) for o in row.options] == [("True", True), ("False", False)]

    def test_numerical_answer_and_tolerance_become_the_spec(self):
        header = ["Question", "Type", "Correct", "Tolerance", "Unit", "Marks"]
        data = _csv([["Acceleration due to gravity?", "numerical", "9.81", "0.02", "m/s^2", "2"]], header)
        row = parse_questions(filename="q.csv", data=data)[0]
        assert row.ok, row.problems
        assert row.spec is not None
        assert row.spec["answer"] == pytest.approx(9.81)
        assert row.spec["tolerance"] == pytest.approx(0.02)

    def test_fill_blank_accepts_several_answers(self):
        header = ["Question", "Type", "Correct", "Marks"]
        data = _csv([["The chemical formula for water is ____.", "fill blank", "water|H2O", "1"]], header)
        row = parse_questions(filename="q.csv", data=data)[0]
        assert row.ok, row.problems
        assert row.spec is not None
        assert row.spec["accepted_answers"] == ["water", "H2O"]

    def test_a_written_question_takes_the_answer_column_as_its_model_answer(self):
        header = ["Question", "Type", "Correct", "Marks"]
        data = _csv([["State two limits of gradient descent.", "long answer", "Local minima; step size", "5"]], header)
        row = parse_questions(filename="q.csv", data=data)[0]
        assert row.ok, row.problems
        assert row.model_answer == "Local minima; step size"


class TestProblemsAreReportedNotSwallowed:
    def test_an_mcq_with_no_correct_answer_is_flagged(self):
        row = parse_questions(filename="q.csv", data=_csv([_mcq_row(correct="")]))[0]
        assert not row.ok
        assert any("no correct answer" in p.lower() for p in row.problems)

    def test_an_answer_naming_an_option_that_does_not_exist_is_flagged(self):
        row = parse_questions(filename="q.csv", data=_csv([_mcq_row(correct="F")]))[0]
        assert not row.ok
        assert any("empty" in p.lower() for p in row.problems)

    def test_a_missing_type_is_flagged(self):
        broken = _mcq_row()
        broken[1] = ""
        row = parse_questions(filename="q.csv", data=_csv([broken]))[0]
        assert not row.ok
        assert any("type is missing" in p.lower() for p in row.problems)

    def test_an_unknown_type_says_so_rather_than_guessing(self):
        broken = _mcq_row()
        broken[1] = "quiz-ish"
        row = parse_questions(filename="q.csv", data=_csv([broken]))[0]
        assert not row.ok
        assert any("quiz-ish" in p for p in row.problems)

    def test_non_numeric_marks_are_flagged(self):
        broken = _mcq_row()
        broken[4] = "two"
        row = parse_questions(filename="q.csv", data=_csv([broken]))[0]
        assert not row.ok
        assert any("marks" in p.lower() for p in row.problems)

    def test_an_empty_question_is_flagged(self):
        broken = _mcq_row(body="")
        row = parse_questions(filename="q.csv", data=_csv([broken]))[0]
        assert not row.ok
        assert any("empty" in p.lower() for p in row.problems)

    def test_a_single_choice_question_with_two_keys_is_flagged(self):
        row = parse_questions(filename="q.csv", data=_csv([_mcq_row(correct="A,B")]))[0]
        assert not row.ok
        assert any("more than one" in p.lower() for p in row.problems)

    def test_a_multi_select_question_may_have_two_keys(self):
        row_data = _mcq_row(correct="A,C")
        row_data[1] = "multi select"
        row = parse_questions(filename="q.csv", data=_csv([row_data]))[0]
        assert row.ok, row.problems
        assert [o.is_correct for o in row.options] == [True, False, True, False]

    def test_a_broken_row_does_not_take_the_good_ones_with_it(self):
        data = _csv([_mcq_row("First?"), _mcq_row("Second?", correct=""), _mcq_row("Third?")])
        rows = parse_questions(filename="q.csv", data=data)
        assert [r.ok for r in rows] == [True, False, True]

    def test_a_repeated_question_is_marked_as_a_duplicate(self):
        data = _csv([_mcq_row("Same question?"), _mcq_row("  same QUESTION?  ")])
        rows = parse_questions(filename="q.csv", data=data)
        assert rows[0].duplicate_of is None
        assert rows[1].duplicate_of == "row 2"


class TestFileLevelFailures:
    def test_an_unsupported_extension_is_refused_by_name(self):
        with pytest.raises(ImportError_, match="not a format"):
            parse_questions(filename="questions.zip", data=b"anything")

    def test_a_file_with_no_question_column_is_refused(self):
        data = _csv([["a", "b"]], header=["Alpha", "Beta"])
        with pytest.raises(ImportError_, match="No question column"):
            parse_questions(filename="q.csv", data=data)

    def test_a_header_with_no_rows_is_refused(self):
        with pytest.raises(ImportError_, match="no question rows"):
            parse_questions(filename="q.csv", data=_csv([]))


class TestWordAndProse:
    def test_a_numbered_word_paper_is_read_as_questions(self):
        docx = pytest.importorskip("docx")
        document = docx.Document()
        for line in [
            "1. What is supervised learning?",
            "A. Learning without data",
            "B. Learning from labelled data",
            "C. Removing training data",
            "Answer: B",
            "2. Backpropagation uses the chain rule.",
            "A. True",
            "B. False",
            "Answer: A",
        ]:
            document.add_paragraph(line)
        buffer = io.BytesIO()
        document.save(buffer)

        rows = parse_questions(filename="paper.docx", data=buffer.getvalue())
        assert len(rows) == 2
        assert rows[0].body == "What is supervised learning?"
        assert rows[0].options[1].is_correct
        assert rows[1].options[0].is_correct

    def test_a_mixed_type_paper_extracts_every_section_not_just_the_first(self):
        """5 Single Choice, 5 True/False, 3 Multiple Choice - all 13, not just section A."""
        docx = pytest.importorskip("docx")
        document = docx.Document()
        lines = ["Section A — Single Choice (Easy)"]
        for n in range(1, 6):
            lines += [f"{n}. Single choice question {n}?", "A. First", "B. Second", "Answer: A"]
        lines.append("Section B — True/False (Medium)")
        for n in range(6, 11):
            lines += [f"{n}. True/false question {n}?", "True", "False", "Answer: True"]
        lines.append("Section C — Multiple Choice (Medium)")
        for n in range(11, 14):
            lines += [
                f"{n}. Multiple choice question {n}?",
                "A. Alpha",
                "B. Beta",
                "C. Gamma",
                "D. Delta",
                # Not every option, since a multi-select question with every option
                # marked correct is refused by validate_question - same rule the
                # manual editor is bound by, and out of scope for this fix.
                "Answer: A, B, C",
            ]
        for line in lines:
            document.add_paragraph(line)
        buffer = io.BytesIO()
        document.save(buffer)

        rows = parse_questions(filename="paper.docx", data=buffer.getvalue())
        assert len(rows) == 13
        assert [r.problems for r in rows] == [[]] * 13
        types = [r.question_type.value for r in rows]
        assert types[:5] == ["mcq"] * 5
        assert types[5:10] == ["true_false"] * 5
        assert types[10:] == ["multi_select"] * 3

    def test_bare_true_false_lines_do_not_leak_into_the_question_body(self):
        docx = pytest.importorskip("docx")
        document = docx.Document()
        for line in [
            "1. A model can perform poorly when training data is unrepresentative.",
            "True",
            "False",
            "Answer: True",
        ]:
            document.add_paragraph(line)
        buffer = io.BytesIO()
        document.save(buffer)

        rows = parse_questions(filename="paper.docx", data=buffer.getvalue())
        assert len(rows) == 1
        row = rows[0]
        assert row.ok, row.problems
        assert row.question_type.value == "true_false"
        assert row.body == "A model can perform poorly when training data is unrepresentative."
        assert [(o.text, o.is_correct) for o in row.options] == [("True", True), ("False", False)]

    def test_an_answer_written_as_the_full_option_text_names_that_option(self):
        docx = pytest.importorskip("docx")
        document = docx.Document()
        for line in [
            "1. Which language is this?",
            "A. Python",
            "B. Java",
            "C. C++",
            "D. HTML",
            "Answer: Python",
        ]:
            document.add_paragraph(line)
        buffer = io.BytesIO()
        document.save(buffer)

        rows = parse_questions(filename="paper.docx", data=buffer.getvalue())
        assert len(rows) == 1
        row = rows[0]
        assert row.ok, row.problems
        assert [o.is_correct for o in row.options] == [True, False, False, False]

    def test_a_table_per_section_is_merged_not_just_the_first(self):
        docx = pytest.importorskip("docx")
        document = docx.Document()
        header_cells = ["Question", "Type", "Option A", "Option B", "Correct"]
        for section_rows in (
            [["Section A Q1?", "mcq", "yes", "no", "A"]],
            [["Section B Q1?", "true_false", "", "", "TRUE"]],
        ):
            table = document.add_table(rows=1 + len(section_rows), cols=len(header_cells))
            for column, value in enumerate(header_cells):
                table.cell(0, column).text = value
            for row_index, values in enumerate(section_rows, start=1):
                for column, value in enumerate(values):
                    table.cell(row_index, column).text = value
        buffer = io.BytesIO()
        document.save(buffer)

        rows = parse_questions(filename="paper.docx", data=buffer.getvalue())
        assert [r.body for r in rows] == ["Section A Q1?", "Section B Q1?"]
        assert [r.ok for r in rows] == [True, True]

    def test_a_word_table_wins_over_prose_when_both_are_present(self):
        docx = pytest.importorskip("docx")
        document = docx.Document()
        document.add_paragraph("1. A prose question nobody wants imported")
        table = document.add_table(rows=2, cols=4)
        for column, value in enumerate(["Question", "Type", "Option A", "Option B"]):
            table.cell(0, column).text = value
        for column, value in enumerate(["From the table?", "mcq", "yes", "no"]):
            table.cell(1, column).text = value
        buffer = io.BytesIO()
        document.save(buffer)

        rows = parse_questions(filename="paper.docx", data=buffer.getvalue())
        assert [r.body for r in rows] == ["From the table?"]


class TestPdf:
    def _pdf_bytes(self, lines: list[str]) -> bytes:
        pytest.importorskip("reportlab")
        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        y = 800
        for line in lines:
            pdf.drawString(50, y, line)
            y -= 20
        pdf.save()
        return buffer.getvalue()

    def test_a_pdf_with_a_question_table_is_imported_directly(self):
        data = self._pdf_bytes(
            [
                "1. What is supervised learning?",
                "A. Learning without data",
                "B. Learning from labelled data",
                "Answer: B",
            ]
        )
        rows = parse_questions(filename="paper.pdf", data=data)
        assert len(rows) == 1
        assert rows[0].ok, rows[0].problems
        assert rows[0].options[1].is_correct

    def test_labelled_headings_with_the_body_on_the_next_line_are_read(self):
        """The "Question 1 (Easy)" layout - heading, then body, then options."""
        data = self._pdf_bytes(
            [
                "SQL Question Bank",
                "Question 1 (Easy)",
                "Define the clause that sorts query results.",
                "A. SORT BY",
                "B. ORDER BY",
                "Answer: B. ORDER BY",
                "Question 2 (Hard)",
                "Which property keeps a committed transaction saved after a system",
                "failure?",
                "A. Atomicity",
                "B. Durability",
                "Answer: B. It is durability, a property of a transaction",
            ]
        )
        rows = parse_questions(filename="paper.pdf", data=data)
        assert [r.problems for r in rows] == [[], []]
        assert rows[0].body == "Define the clause that sorts query results."
        assert rows[0].difficulty.value == "easy"
        assert [o.is_correct for o in rows[0].options] == [False, True]
        # A wrapped line starting with a-f is body text, not option F.
        assert rows[1].body.endswith("system failure?")
        assert len(rows[1].options) == 2
        assert rows[1].difficulty.value == "hard"
        assert [o.is_correct for o in rows[1].options] == [False, True]

    def test_a_scanned_pdf_is_read_with_ocr(self):
        """No text layer at all - a picture of the paper - still yields its questions."""
        from app.services.ocr import engine_version

        if engine_version() is None:
            pytest.skip("Tesseract is not installed on this machine")
        from PIL import Image, ImageDraw, ImageFont

        page = Image.new("RGB", (1700, 1100), "white")
        draw = ImageDraw.Draw(page)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except OSError:
            font = ImageFont.load_default(size=40)
        lines = [
            "Question 1 (Easy)",
            "Which SQL command retrieves data from a table?",
            "A. INSERT",
            "B. SELECT",
            "C. UPDATE",
            "Answer: B",
        ]
        for n, line in enumerate(lines):
            draw.text((100, 100 + n * 90), line, fill="black", font=font)
        buffer = io.BytesIO()
        page.save(buffer, "PDF")

        rows = parse_questions(filename="scan.pdf", data=buffer.getvalue())
        assert len(rows) == 1
        assert rows[0].ok, rows[0].problems
        assert "SQL command" in rows[0].body
        assert [o.is_correct for o in rows[0].options] == [False, True, False]

    def test_a_pdf_with_no_questions_points_at_ai_generate(self):
        data = self._pdf_bytes(["Syllabus", "Unit 1: Introduction", "Unit 2: Data structures"])
        with pytest.raises(ImportError_, match="AI Generate"):
            parse_questions(filename="syllabus.pdf", data=data)


class TestSpreadsheet:
    def test_an_xlsx_workbook_parses(self):
        openpyxl = pytest.importorskip("openpyxl")
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(HEADER)
        sheet.append(_mcq_row())
        buffer = io.BytesIO()
        workbook.save(buffer)

        rows = parse_questions(filename="bank.xlsx", data=buffer.getvalue())
        assert len(rows) == 1
        assert rows[0].ok, rows[0].problems


class TestImportApi:
    def test_parse_reports_counts_without_writing_anything(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        headers = auth_headers(client, examiner)

        data = _csv([_mcq_row("Good one?"), _mcq_row("Bad one?", correct="")])
        response = client.post(
            "/api/v1/questions/import/parse",
            files={"file": ("bank.csv", data, "text/csv")},
            data={"subject_id": str(subject.id)},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["total"], body["valid"], body["invalid"]) == (2, 1, 1)

        # Nothing was written - parsing is a read.
        listed = client.get(f"/api/v1/questions?subject_id={subject.id}", headers=headers).json()
        assert listed == []

    def test_a_question_already_in_the_bank_is_flagged_as_a_duplicate(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        make_question(db, subject, body="What is supervised learning?", created_by=examiner)

        response = client.post(
            "/api/v1/questions/import/parse",
            files={"file": ("bank.csv", _csv([_mcq_row()]), "text/csv")},
            data={"subject_id": str(subject.id)},
            headers=auth_headers(client, examiner),
        )
        assert response.status_code == 200, response.text
        assert response.json()["rows"][0]["duplicate_of"] == "the question bank"

    def test_committing_creates_questions_labelled_as_imported(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        headers = auth_headers(client, examiner)

        parsed = client.post(
            "/api/v1/questions/import/parse",
            files={"file": ("bank.csv", _csv([_mcq_row()]), "text/csv")},
            data={"subject_id": str(subject.id)},
            headers=headers,
        ).json()

        response = client.post(
            "/api/v1/questions/import",
            json={"subject_id": str(subject.id), "rows": parsed["rows"]},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["created"] == 1

        listed = client.get(
            f"/api/v1/questions?subject_id={subject.id}&source=imported", headers=headers
        ).json()
        assert len(listed) == 1
        assert listed[0]["source"] == QuestionSource.IMPORTED.value

    def test_committing_an_invalid_row_is_refused_row_by_row(
        self, client: TestClient, db: Session
    ):
        """The client is not trusted to have honoured its own preview."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        headers = auth_headers(client, examiner)

        good = {
            "row_number": 2,
            "body": "A valid question?",
            "question_type": "mcq",
            "marks": 2,
            "options": [
                {"text": "yes", "is_correct": True},
                {"text": "no", "is_correct": False},
            ],
        }
        bad = {**good, "row_number": 3, "body": "No key here?", "options": [
            {"text": "yes", "is_correct": False},
            {"text": "no", "is_correct": False},
        ]}

        response = client.post(
            "/api/v1/questions/import",
            json={"subject_id": str(subject.id), "rows": [good, bad]},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["created"], body["failed"]) == (1, 1)
        assert body["errors"][0]["row_number"] == 3

    def test_importing_into_an_exam_adds_the_questions_to_its_pool(
        self, client: TestClient, db: Session
    ):
        examiner = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        exam = make_exam(db, subject, examiner, questions=[], status=ExamStatus.DRAFT)
        headers = auth_headers(client, examiner)

        parsed = client.post(
            "/api/v1/questions/import/parse",
            files={"file": ("bank.csv", _csv([_mcq_row(), _mcq_row("Second?")]), "text/csv")},
            data={"subject_id": str(subject.id)},
            headers=headers,
        ).json()

        response = client.post(
            "/api/v1/questions/import",
            json={
                "subject_id": str(subject.id),
                "exam_id": str(exam.id),
                "rows": parsed["rows"],
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text

        pool = client.get(f"/api/v1/exams/{exam.id}/pool", headers=headers).json()
        assert pool["stats"]["total_questions"] == 2
        assert [e["source"] for e in pool["entries"]] == ["imported", "imported"]

    def test_importing_into_someone_elses_exam_is_refused(self, client: TestClient, db: Session):
        owner = make_user(db, role=UserRole.EXAMINER)
        intruder = make_user(db, role=UserRole.EXAMINER)
        subject = make_subject(db)
        exam = make_exam(db, subject, owner, questions=[], status=ExamStatus.DRAFT)

        response = client.post(
            "/api/v1/questions/import",
            json={
                "subject_id": str(subject.id),
                "exam_id": str(exam.id),
                "rows": [
                    {
                        "body": "Anything?",
                        "question_type": "true_false",
                        "marks": 1,
                        "options": [
                            {"text": "True", "is_correct": True},
                            {"text": "False", "is_correct": False},
                        ],
                    }
                ],
            },
            headers=auth_headers(client, intruder),
        )
        assert response.status_code == 403

    def test_the_template_download_parses_through_our_own_parser(
        self, client: TestClient, db: Session
    ):
        """A template the importer cannot read would be a cruel joke."""
        examiner = make_user(db, role=UserRole.EXAMINER)
        response = client.get(
            "/api/v1/questions/import/template", headers=auth_headers(client, examiner)
        )
        assert response.status_code == 200

        rows = parse_questions(filename="template.csv", data=response.content)
        assert rows and all(row.ok for row in rows), [r.problems for r in rows]

    def test_an_empty_upload_is_refused(self, client: TestClient, db: Session):
        examiner = make_user(db, role=UserRole.EXAMINER)
        response = client.post(
            "/api/v1/questions/import/parse",
            files={"file": ("empty.csv", b"", "text/csv")},
            headers=auth_headers(client, examiner),
        )
        assert response.status_code == 422

    def test_a_candidate_cannot_import_questions(self, client: TestClient, db: Session):
        candidate = make_user(db, role=UserRole.CANDIDATE)
        response = client.post(
            "/api/v1/questions/import/parse",
            files={"file": ("bank.csv", _csv([_mcq_row()]), "text/csv")},
            headers=auth_headers(client, candidate),
        )
        assert response.status_code == 403
