"""Parse a spreadsheet, CSV or Word document into reviewable question rows.

Three deliberate properties:

1. Parsing never writes. It returns rows plus per-row problems, and the examiner
   decides what to import. A file with fourteen good rows and two broken ones should
   let fourteen questions through - after someone has looked at the two.

2. A row that cannot be understood is reported, not skipped. An importer that quietly
   drops the rows it dislikes is worse than one that fails: the examiner publishes an
   exam three questions short and finds out from a candidate.

3. Nothing here trusts the file's own claims about correctness. Every row goes through
   the same ``validate_question`` the manual editor and the API use, so an import
   cannot produce a question the authoring form would have refused.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Any

from app.db.models.enums import (
    OPTION_BEARING_TYPES,
    Difficulty,
    QuestionCategory,
    QuestionType,
)
from app.services.validators import OptionDraft, ValidationError, validate_question

#: The column names an examiner is likely to have typed. Matching is case- and
#: punctuation-insensitive, because "Question Text", "question_text" and "QUESTION"
#: are all the same column to a human and none of them is more correct.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "body": ("question", "question text", "body", "text", "problem", "statement"),
    "question_type": ("type", "question type", "qtype", "kind"),
    "difficulty": ("difficulty", "level"),
    "topic": ("topic", "subtopic", "unit", "chapter"),
    "category": ("category", "section", "shelf"),
    "marks": ("marks", "mark", "points", "score", "weight"),
    "negative_marks": ("negative marks", "negative", "penalty", "negative mark"),
    "correct": ("correct", "answer", "correct answer", "correct option", "key"),
    "model_answer": ("model answer", "expected answer", "reference answer", "solution"),
    "explanation": ("explanation", "rationale", "why"),
    "tags": ("tags", "labels"),
    "min_words": ("min words", "minimum words"),
    "max_words": ("max words", "maximum words", "word limit"),
    "tolerance": ("tolerance", "margin"),
    "unit": ("unit", "units"),
    "case_sensitive": ("case sensitive", "case"),
}

#: Option columns are positional: "Option A".."Option F", or "A".."F".
OPTION_PATTERN = re.compile(r"^(?:option[\s_-]*)?([a-f])$", re.IGNORECASE)

#: What an examiner might write in a "type" cell for each real type.
TYPE_ALIASES: dict[str, QuestionType] = {
    "mcq": QuestionType.MCQ,
    "single": QuestionType.MCQ,
    "single choice": QuestionType.MCQ,
    "single select": QuestionType.MCQ,
    "multiple choice": QuestionType.MCQ,
    "multi select": QuestionType.MULTI_SELECT,
    "multi": QuestionType.MULTI_SELECT,
    "multiselect": QuestionType.MULTI_SELECT,
    "multiple answer": QuestionType.MULTI_SELECT,
    "true false": QuestionType.TRUE_FALSE,
    "true/false": QuestionType.TRUE_FALSE,
    "truefalse": QuestionType.TRUE_FALSE,
    "tf": QuestionType.TRUE_FALSE,
    "fill blank": QuestionType.FILL_BLANK,
    "fill in the blank": QuestionType.FILL_BLANK,
    "fillblank": QuestionType.FILL_BLANK,
    "blank": QuestionType.FILL_BLANK,
    "numerical": QuestionType.NUMERICAL,
    "numeric": QuestionType.NUMERICAL,
    "number": QuestionType.NUMERICAL,
    "short answer": QuestionType.SHORT_ANSWER,
    "short": QuestionType.SHORT_ANSWER,
    "long answer": QuestionType.LONG_ANSWER,
    "long": QuestionType.LONG_ANSWER,
    "essay": QuestionType.LONG_ANSWER,
    "descriptive": QuestionType.LONG_ANSWER,
    "handwritten": QuestionType.IMAGE_UPLOAD,
    "image upload": QuestionType.IMAGE_UPLOAD,
    "upload": QuestionType.IMAGE_UPLOAD,
    "coding": QuestionType.CODING,
    "code": QuestionType.CODING,
    "programming": QuestionType.CODING,
    "passage": QuestionType.PASSAGE,
    "comprehension": QuestionType.PASSAGE,
}


class ImportError_(Exception):
    """The file itself could not be read - wrong format, corrupt, or empty."""


@dataclass
class ParsedOption:
    text: str
    is_correct: bool


@dataclass
class ParsedRow:
    """One candidate question, as understood, plus everything wrong with it.

    ``problems`` empty means this row would be accepted by the same validation the
    manual editor applies. It is not a promise that the question is *good* - only that
    it is well-formed.
    """

    #: 1-based, counting the header, so it matches what the examiner sees in Excel.
    row_number: int
    body: str = ""
    question_type: QuestionType = QuestionType.MCQ
    difficulty: Difficulty = Difficulty.MEDIUM
    category: QuestionCategory = QuestionCategory.ACADEMIC
    topic: str | None = None
    marks: float = 1.0
    negative_marks: float = 0.0
    model_answer: str | None = None
    explanation: str | None = None
    tags: list[str] = field(default_factory=list)
    min_words: int | None = None
    max_words: int | None = None
    options: list[ParsedOption] = field(default_factory=list)
    spec: dict[str, Any] | None = None
    problems: list[str] = field(default_factory=list)
    #: Set when an identical body appears earlier in the same file, or already in
    #: the bank. A duplicate is a warning an examiner should see, not a hard error -
    #: two exams legitimately reuse a question, and only they can tell.
    duplicate_of: str | None = None

    @property
    def ok(self) -> bool:
        return not self.problems

    def as_payload(self, subject_id: str) -> dict[str, Any]:
        """The row as a ``QuestionCreate`` body."""
        return {
            "subject_id": subject_id,
            "question_type": self.question_type.value,
            "difficulty": self.difficulty.value,
            "category": self.category.value,
            "topic": self.topic,
            "body": self.body,
            "marks": self.marks,
            "negative_marks": self.negative_marks,
            "model_answer": self.model_answer,
            "explanation": self.explanation,
            "tags": self.tags or None,
            "min_words": self.min_words,
            "max_words": self.max_words,
            "spec": self.spec,
            "options": [
                {"text": o.text, "is_correct": o.is_correct, "order_index": i}
                for i, o in enumerate(self.options)
            ],
        }


def _normalise_header(value: str) -> str:
    return re.sub(r"[\s_\-\.]+", " ", (value or "").strip().lower())


def _map_columns(headers: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    """Return (field name -> column index, option letter -> column index)."""
    fields: dict[str, int] = {}
    options: dict[str, int] = {}
    for index, raw in enumerate(headers):
        header = _normalise_header(raw)
        if not header:
            continue
        letter_match = OPTION_PATTERN.match(header)
        if letter_match:
            options[letter_match.group(1).upper()] = index
            continue
        for name, aliases in COLUMN_ALIASES.items():
            if header in aliases and name not in fields:
                fields[name] = index
                break
    return fields, options


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    value = row[index]
    return "" if value is None else str(value).strip()


def _parse_float(text: str, default: float) -> float | None:
    """None signals "present but unreadable", which is a problem worth reporting."""
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return None


def _parse_type(text: str) -> QuestionType | None:
    if not text:
        return None
    key = _normalise_header(text)
    if key in TYPE_ALIASES:
        return TYPE_ALIASES[key]
    try:
        return QuestionType(key.replace(" ", "_"))
    except ValueError:
        return None


def _parse_correct_letters(text: str) -> list[str]:
    """"B", "b", "A,C", "A and C", "2" all name options.

    Numbers are accepted because plenty of question banks are written with 1-based
    option numbers, and rejecting those would fail files that are perfectly clear.
    """
    found: list[str] = []
    for token in re.split(r"[,;/&]|\band\b|\s+", text.strip()):
        token = token.strip().upper().rstrip(".)")
        if not token:
            continue
        if re.fullmatch(r"[A-F]", token):
            found.append(token)
        elif re.fullmatch(r"[1-6]", token):
            found.append(chr(ord("A") + int(token) - 1))
    return list(dict.fromkeys(found))


def _row_to_question(
    row_number: int,
    row: list[str],
    fields: dict[str, int],
    options: dict[str, int],
) -> ParsedRow:
    parsed = ParsedRow(row_number=row_number)

    parsed.body = _cell(row, fields.get("body"))
    if not parsed.body:
        parsed.problems.append("The question text is empty.")

    type_text = _cell(row, fields.get("question_type"))
    question_type = _parse_type(type_text)
    if question_type is None:
        if type_text:
            parsed.problems.append(f"'{type_text}' is not a question type we recognise.")
        else:
            parsed.problems.append("The question type is missing.")
    else:
        parsed.question_type = question_type

    difficulty_text = _normalise_header(_cell(row, fields.get("difficulty")))
    if difficulty_text:
        try:
            parsed.difficulty = Difficulty(difficulty_text)
        except ValueError:
            parsed.problems.append(f"'{difficulty_text}' is not easy, medium or hard.")

    category_text = _normalise_header(_cell(row, fields.get("category"))).replace(" ", "_")
    if category_text:
        try:
            parsed.category = QuestionCategory(category_text)
        except ValueError:
            parsed.problems.append(f"'{category_text}' is not a question category.")

    parsed.topic = _cell(row, fields.get("topic")) or None
    parsed.model_answer = _cell(row, fields.get("model_answer")) or None
    parsed.explanation = _cell(row, fields.get("explanation")) or None
    tags_text = _cell(row, fields.get("tags"))
    parsed.tags = [t.strip() for t in re.split(r"[,;]", tags_text) if t.strip()]

    marks = _parse_float(_cell(row, fields.get("marks")), 1.0)
    if marks is None:
        parsed.problems.append("The marks value is not a number.")
    else:
        parsed.marks = marks

    negative = _parse_float(_cell(row, fields.get("negative_marks")), 0.0)
    if negative is None:
        parsed.problems.append("The negative marks value is not a number.")
    else:
        parsed.negative_marks = abs(negative)

    for name in ("min_words", "max_words"):
        text = _cell(row, fields.get(name))
        if text:
            try:
                setattr(parsed, name, int(float(text)))
            except ValueError:
                parsed.problems.append(f"The {name.replace('_', ' ')} value is not a number.")

    # --- options and the key
    correct_text = _cell(row, fields.get("correct"))
    if parsed.question_type in OPTION_BEARING_TYPES:
        if parsed.question_type is QuestionType.TRUE_FALSE:
            answer = _normalise_header(correct_text)
            truthy = answer in {"true", "t", "yes", "y", "1"}
            falsy = answer in {"false", "f", "no", "n", "0"}
            if not truthy and not falsy:
                parsed.problems.append("A true/false question needs TRUE or FALSE as its answer.")
            parsed.options = [
                ParsedOption("True", truthy),
                ParsedOption("False", falsy),
            ]
        else:
            letters = _parse_correct_letters(correct_text)
            for letter in sorted(options):
                text = _cell(row, options[letter])
                if text:
                    parsed.options.append(ParsedOption(text, letter in letters))
            if len(parsed.options) < 2:
                parsed.problems.append("Fewer than two options were found.")
            if not correct_text:
                parsed.problems.append("No correct answer is given.")
            elif not letters:
                parsed.problems.append(
                    f"'{correct_text}' does not name any of the options."
                )
            elif not any(o.is_correct for o in parsed.options):
                parsed.problems.append(
                    f"The answer '{correct_text}' points at an option that is empty."
                )
            if parsed.question_type is QuestionType.MCQ:
                marked = sum(1 for o in parsed.options if o.is_correct)
                if marked > 1:
                    parsed.problems.append(
                        "A single-choice question has more than one option marked correct."
                    )
    elif parsed.question_type is QuestionType.NUMERICAL:
        answer = _parse_float(correct_text, None)  # type: ignore[arg-type]
        if answer is None:
            parsed.problems.append("A numerical question needs a numeric answer.")
        else:
            tolerance = _parse_float(_cell(row, fields.get("tolerance")), 0.0) or 0.0
            parsed.spec = {
                "answer": answer,
                "tolerance": tolerance,
                "unit": _cell(row, fields.get("unit")) or None,
            }
    elif parsed.question_type is QuestionType.FILL_BLANK:
        accepted = [a.strip() for a in re.split(r"[|;\n]", correct_text) if a.strip()]
        if not accepted:
            parsed.problems.append("A fill-in-the-blank question needs at least one answer.")
        else:
            case_text = _normalise_header(_cell(row, fields.get("case_sensitive")))
            parsed.spec = {
                "accepted_answers": accepted,
                "case_sensitive": case_text in {"yes", "y", "true", "1", "sensitive"},
            }
    elif parsed.question_type in (QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER):
        # The "correct" column is where an examiner writing a spreadsheet naturally
        # puts the model answer for a written question.
        if not parsed.model_answer:
            parsed.model_answer = correct_text or None
        if not parsed.model_answer:
            parsed.problems.append("A written question needs a model answer to grade against.")

    # --- the same rules the authoring form and the API apply
    if parsed.ok:
        try:
            parsed.spec = validate_question(
                question_type=parsed.question_type,
                body=parsed.body,
                marks=parsed.marks,
                negative_marks=parsed.negative_marks,
                options=[
                    OptionDraft(o.text, o.is_correct, i) for i, o in enumerate(parsed.options)
                ],
                model_answer=parsed.model_answer,
                min_words=parsed.min_words,
                max_words=parsed.max_words,
                spec=parsed.spec,
                image_key=None,
            )
        except ValidationError as exc:
            parsed.problems.append(str(exc))

    return parsed


def _rows_from_csv(data: bytes) -> list[list[str]]:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 decodes any byte string
        raise ImportError_("That file is not text we can read.")

    sample = text[:4096]
    try:
        dialect: Any = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel  # a single-column file sniffs as nothing; comma is fine
    return [list(row) for row in csv.reader(io.StringIO(text), dialect) if any(row)]


def _rows_from_xlsx(data: bytes) -> list[list[str]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ImportError_("Spreadsheet support is not installed on the server.") from exc

    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ImportError_("That file could not be opened as a spreadsheet.") from exc

    sheet = workbook.active
    if sheet is None:
        raise ImportError_("That workbook has no sheets.")
    rows = [
        ["" if cell is None else str(cell) for cell in row]
        for row in sheet.iter_rows(values_only=True)
    ]
    workbook.close()
    return [row for row in rows if any(cell.strip() for cell in row)]


def _rows_from_docx(data: bytes) -> list[list[str]]:
    """Read a Word document's first table, or fall back to numbered paragraphs.

    Examiners write Word question papers both ways, and a table is unambiguous where
    prose is not, so a table wins whenever the document has one.
    """
    try:
        import docx
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ImportError_("Word support is not installed on the server.") from exc

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ImportError_("That file could not be opened as a Word document.") from exc

    for table in document.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        rows = [row for row in rows if any(row)]
        if len(rows) >= 2:
            return rows

    return _rows_from_prose([p.text for p in document.paragraphs])


#: "1. What is X?" / "Q3) What is X?" - the numbering examiners actually type.
QUESTION_START = re.compile(r"^\s*(?:q(?:uestion)?\s*)?(\d{1,3})\s*[\.\):]\s*(.+)$", re.IGNORECASE)
#: "A. Learning from data" / "(b) Removing data" / "C) ..." - optionally starred correct.
OPTION_LINE = re.compile(r"^\s*\(?([a-fA-F])\)?\s*[\.\):]?\s*(.+?)\s*(\*)?\s*$")
ANSWER_LINE = re.compile(r"^\s*(?:answer|ans|correct)\s*[:\-]\s*(.+)$", re.IGNORECASE)


def _rows_from_prose(lines: list[str]) -> list[list[str]]:
    """Turn a numbered question paper into header-shaped rows.

    Emitted in the same column order as the CSV template, so everything downstream -
    validation, duplicate detection, the preview - is identical whichever format the
    examiner started from.
    """
    header = [
        "Question",
        "Type",
        "Option A",
        "Option B",
        "Option C",
        "Option D",
        "Option E",
        "Option F",
        "Correct",
    ]
    rows: list[list[str]] = [header]

    body: str | None = None
    options: list[tuple[str, str, bool]] = []
    answer = ""

    def flush() -> None:
        nonlocal body, options, answer
        if body is None:
            return
        cells = [""] * 6
        starred = ""
        for letter, text, is_correct in options:
            index = ord(letter.upper()) - 65
            if 0 <= index < 6:
                cells[index] = text
                if is_correct:
                    starred = letter.upper()
        rows.append(
            [
                body,
                "mcq" if any(cells) else "short_answer",
                *cells,
                answer or starred,
            ]
        )
        body, options, answer = None, [], ""

    for line in lines:
        text = line.strip()
        if not text:
            continue

        start = QUESTION_START.match(text)
        if start:
            flush()
            body = start.group(2).strip()
            continue

        if body is None:
            continue

        found_answer = ANSWER_LINE.match(text)
        if found_answer:
            answer = found_answer.group(1).strip()
            continue

        option = OPTION_LINE.match(text)
        if option and len(text) < 400:
            options.append((option.group(1), option.group(2).strip(), bool(option.group(3))))
            continue

        # A continuation line - part of the question, wrapped.
        body = f"{body} {text}".strip()

    flush()
    return rows


#: Extension -> reader. PDF import already has its own AI-backed route, which reads a
#: syllabus rather than a formatted question table, so it is deliberately not here.
READERS = {
    "csv": _rows_from_csv,
    "tsv": _rows_from_csv,
    "txt": _rows_from_csv,
    "xlsx": _rows_from_xlsx,
    "xlsm": _rows_from_xlsx,
    "docx": _rows_from_docx,
}


def parse_questions(*, filename: str, data: bytes) -> list[ParsedRow]:
    """Read a file into rows. Raises ``ImportError_`` only when nothing can be read."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    reader = READERS.get(extension)
    if reader is None:
        raise ImportError_(
            f"'{extension or filename}' is not a format we can import. "
            "Use CSV, Excel (.xlsx) or Word (.docx)."
        )

    rows = reader(data)
    if len(rows) < 2:
        raise ImportError_(
            "That file has a header but no question rows." if rows else "That file is empty."
        )

    fields, options = _map_columns(rows[0])
    if "body" not in fields:
        raise ImportError_(
            "No question column was found. Name one column 'Question' and try again."
        )

    parsed: list[ParsedRow] = []
    seen: dict[str, int] = {}
    for offset, row in enumerate(rows[1:], start=2):
        if not any(str(cell or "").strip() for cell in row):
            continue
        item = _row_to_question(offset, list(row), fields, options)

        # Duplicate detection within the file. Whitespace and case are not meaningful
        # differences between two copies of the same question.
        fingerprint = re.sub(r"\s+", " ", item.body.strip().casefold())
        if fingerprint:
            if fingerprint in seen:
                item.duplicate_of = f"row {seen[fingerprint]}"
            else:
                seen[fingerprint] = offset
        parsed.append(item)

    if not parsed:
        raise ImportError_("That file has a header but no question rows.")
    return parsed


def fingerprint(body: str) -> str:
    """The comparison key used for duplicate detection, exposed for the bank check."""
    return re.sub(r"\s+", " ", (body or "").strip().casefold())


#: Handed to the UI so the download link and the parser can never drift apart.
TEMPLATE_HEADER = [
    "Question",
    "Type",
    "Difficulty",
    "Topic",
    "Marks",
    "Negative Marks",
    "Option A",
    "Option B",
    "Option C",
    "Option D",
    "Correct",
    "Model Answer",
    "Explanation",
    "Tags",
]

TEMPLATE_ROWS = [
    [
        "What is supervised learning?",
        "mcq",
        "medium",
        "Machine Learning",
        "2",
        "0.5",
        "Learning without data",
        "Learning from labelled data",
        "Removing training data",
        "Encrypting data",
        "B",
        "",
        "Labelled examples are what makes it supervised.",
        "unit-1",
    ],
    [
        "State two limitations of gradient descent.",
        "short_answer",
        "hard",
        "Optimisation",
        "5",
        "0",
        "",
        "",
        "",
        "",
        "",
        "It can stall in local minima and is sensitive to the learning rate.",
        "",
        "unit-2",
    ],
    [
        "Backpropagation computes gradients by the chain rule.",
        "true_false",
        "easy",
        "Neural Networks",
        "1",
        "0",
        "",
        "",
        "",
        "",
        "TRUE",
        "",
        "",
        "",
    ],
]


def template_csv() -> str:
    """A filled-in example file, so the first import is not a guessing game."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(TEMPLATE_HEADER)
    writer.writerows(TEMPLATE_ROWS)
    return buffer.getvalue()
