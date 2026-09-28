"""Import the four hand-authored Kannada question banks into the real bank.

The source files in ``app/data/kannada_question_bank/*.sql`` are written for an
unrelated schema (a table named ``ಪ್ರಶ್ನಾ_ಭಂಡಾರ`` with Kannada column names) and are
never executed as SQL - they are read-only reference data. Each row is parsed by hand
and inserted as a standalone ``Question`` row with ``language="kn"``: this is not a
translation of an existing English question, it is its own Kannada-authored content,
scoped to its own subject (``KA-*``) so a Kannada exam's pool never mixes in English or
Hindi material for the same subject (mirrors how every other ``language`` value already
behaves, per ``ix_questions_language_subject``).

Bypasses the question API entirely and inserts via the ORM directly, the same way
``app.seed_question_bank_bulk`` does - the API's ``QuestionBase`` schema hard-rejects any
``language`` other than ``"en"`` by design (English-authoring-only guardrail for the
composer), and that guardrail is correct to keep; it just is not this script's path.

Run with: ``uv run python -m app.seed_kannada_question_bank``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.models import (
    Difficulty,
    Question,
    QuestionCategory,
    QuestionOption,
    QuestionSource,
    QuestionStatus,
    QuestionType,
    Subject,
    User,
    UserRole,
)
from app.db.session import SessionLocal

logger = get_logger("seed_kannada")

LANGUAGE = "kn"
DATA_DIR = Path(__file__).parent / "data" / "kannada_question_bank"

#: File -> target subject. Deliberately not read from the SQL's own ``ವಿಷಯ`` (subject)
#: column - the AI file's value is in Kannada script while the other three use the
#: literal requested English name, so trusting the column would give one file an
#: inconsistent subject name. The filename is authoritative instead.
#: The name is the plain subject name, with no language prefix - the code already
#: carries the "KA-" marker, and the UI concatenates ``code + " — " + name``, so
#: prefixing the name too would show it twice ("KA-AI — KA-Artificial Intelligence").
SUBJECT_BY_FILE: dict[str, tuple[str, str]] = {
    "KA-Artificial Intelligence.sql": ("KA-AI", "Artificial Intelligence"),
    "KA-Business Analytics.sql": ("KA-BA", "Business Analytics"),
    "KA-Environmental Science.sql": ("KA-ENVSCI", "Environmental Science"),
    "KA-Python.sql": ("KA-PY", "Python"),
}

QUESTION_TYPE_MAP: dict[str, QuestionType] = {
    "ಏಕ ಆಯ್ಕೆ": QuestionType.MCQ,
    "ಬಹು ಆಯ್ಕೆ": QuestionType.MULTI_SELECT,
    "ಸರಿ ಅಥವಾ ತಪ್ಪು": QuestionType.TRUE_FALSE,
    "ಖಾಲಿ ಜಾಗ ತುಂಬಿರಿ": QuestionType.FILL_BLANK,
    "ಸಂಕ್ಷಿಪ್ತ ಉತ್ತರ": QuestionType.SHORT_ANSWER,
    "ವಿಸ್ತೃತ ಉತ್ತರ": QuestionType.LONG_ANSWER,
}

DIFFICULTY_MAP: dict[str, Difficulty] = {
    "ಸುಲಭ": Difficulty.EASY,
    "ಮಧ್ಯಮ": Difficulty.MEDIUM,
    "ಕಠಿಣ": Difficulty.HARD,
}

#: ಅ=0, ಆ=1, ಇ=2, ಈ=3 - the letter convention some rows use for "ಸರಿಯಾದ ಉತ್ತರ" instead of
#: repeating the option's literal text.
OPTION_LETTERS = ["ಅ", "ಆ", "ಇ", "ಈ"]

_FIELD_COUNT = 12


@dataclass
class ParseReport:
    file_name: str
    subject_code: str
    parsed: int = 0
    inserted: int = 0
    duplicates: int = 0
    unmapped_type: list[str] = field(default_factory=list)
    unmapped_difficulty: list[str] = field(default_factory=list)


def _split_row(inner: str) -> list[str | None]:
    """Split the content between one row's outer parens into its raw field strings.

    Not a naive ``.split(",")`` - the Kannada text fields contain literal commas, and a
    literal quote inside a field is escaped as ``''`` (standard SQL), both of which a
    naive split would mis-tokenize.
    """
    fields: list[str | None] = []
    i = 0
    n = len(inner)
    while i < n:
        while i < n and inner[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        if inner[i] == "'":
            j = i + 1
            buf: list[str] = []
            while j < n:
                if inner[j] == "'":
                    if j + 1 < n and inner[j + 1] == "'":
                        buf.append("'")
                        j += 2
                        continue
                    j += 1
                    break
                buf.append(inner[j])
                j += 1
            fields.append("".join(buf))
            i = j
        elif inner[i : i + 4].upper() == "NULL":
            fields.append(None)
            i += 4
        else:
            # Unquoted bare token (shouldn't occur in these files beyond NULL, but don't
            # silently swallow it if it does).
            j = i
            while j < n and inner[j] != ",":
                j += 1
            token = inner[i:j].strip().strip("`")
            fields.append(token or None)
            i = j
        while i < n and inner[i] != ",":
            i += 1
        i += 1  # skip the comma
    return fields


def _extract_rows(sql_text: str) -> list[list[str | None]]:
    """Walk the whole file with a quote-aware scanner, yielding each top-level
    ``(...)`` tuple's fields. Quote-aware so a stray ``)`` inside quoted text never
    mis-splits a row."""
    rows: list[list[str | None]] = []
    i = 0
    n = len(sql_text)
    in_quote = False
    depth = 0
    start = -1
    while i < n:
        c = sql_text[i]
        if in_quote:
            if c == "'":
                if i + 1 < n and sql_text[i + 1] == "'":
                    i += 2
                    continue
                in_quote = False
            i += 1
            continue
        if c == "'":
            in_quote = True
            i += 1
            continue
        if c == "(":
            if depth == 0:
                start = i + 1
            depth += 1
            i += 1
            continue
        if c == ")":
            depth -= 1
            if depth == 0 and start != -1:
                rows.append(_split_row(sql_text[start:i]))
                start = -1
            i += 1
            continue
        i += 1
    # The first "row" captured is the column-name tuple in the INSERT header
    # (`` (`ವಿಷಯ`, `ಭಾಷೆ`, ...) ``) - drop it and anything not shaped like a data row.
    return [r for r in rows if len(r) == _FIELD_COUNT and r[0] not in (None, "ವಿಷಯ")]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() == "nan":
        return None
    return value


#: Some rows spell out the letter as "ಆಯ್ಕೆ ಅ" ("Option A") rather than bare "ಅ".
_OPTION_LETTER_PREFIX = "ಆಯ್ಕೆ"


def _match_option_index(token: str, option_texts: list[str]) -> int | None:
    token = token.strip()
    for idx, text in enumerate(option_texts):
        if text is not None and text.strip() == token:
            return idx
    letter = token
    if letter.startswith(_OPTION_LETTER_PREFIX):
        letter = letter[len(_OPTION_LETTER_PREFIX) :].strip()
    if letter in OPTION_LETTERS:
        idx = OPTION_LETTERS.index(letter)
        if idx < len(option_texts):
            return idx
    return None


def parse_file(path: Path, subject_code: str) -> tuple[list[dict], ParseReport]:
    report = ParseReport(file_name=path.name, subject_code=subject_code)
    text = path.read_text(encoding="utf-8")
    rows = _extract_rows(text)
    parsed: list[dict] = []
    for row in rows:
        (
            _subject_col,
            _language_col,
            type_col,
            difficulty_col,
            marks_col,
            body_col,
            opt_a,
            opt_b,
            opt_c,
            opt_d,
            correct_col,
            explanation_col,
        ) = row
        report.parsed += 1

        qtype = QUESTION_TYPE_MAP.get((type_col or "").strip())
        if qtype is None:
            report.unmapped_type.append((type_col or "")[:60])
            continue
        difficulty = DIFFICULTY_MAP.get((difficulty_col or "").strip())
        if difficulty is None:
            report.unmapped_difficulty.append((difficulty_col or "")[:60])
            continue

        body = _clean(body_col) or ""
        marks = float(_clean(marks_col) or "1")
        explanation = _clean(explanation_col)
        option_texts = [_clean(opt_a), _clean(opt_b), _clean(opt_c), _clean(opt_d)]
        correct_raw = _clean(correct_col) or ""

        model_answer = None
        options: list[tuple[str, bool]] = []
        if qtype in (QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.TRUE_FALSE):
            correct_indices: set[int] = set()
            # MCQ/true-false carry exactly one answer, which may itself contain a literal
            # comma (option text like "survey, interview, observation ..."), so the whole
            # string is tried first rather than blindly splitting on ",". Multi-select
            # answers are genuinely comma-joined lists of letters/option text, so that
            # split only ever applies there.
            whole_match = _match_option_index(correct_raw, option_texts)
            if whole_match is not None:
                correct_indices.add(whole_match)
            elif qtype == QuestionType.MULTI_SELECT:
                for token in correct_raw.split(","):
                    idx = _match_option_index(token, option_texts)
                    if idx is not None:
                        correct_indices.add(idx)
            for idx, opt_text in enumerate(option_texts):
                if opt_text is not None:
                    options.append((opt_text, idx in correct_indices))
        else:
            model_answer = correct_raw or None

        parsed.append(
            {
                "question_type": qtype,
                "difficulty": difficulty,
                "marks": marks,
                "body": body,
                "explanation": explanation,
                "model_answer": model_answer,
                "options": options,
            }
        )
    return parsed, report


def _get_or_create_subject(db: Session, code: str, name: str) -> Subject:
    subject = db.scalar(select(Subject).where(Subject.code == code))
    if subject is not None:
        if subject.name != name:
            # Self-healing: keeps a re-run safe even if a past run wrote a stale name
            # (e.g. an earlier version of this mapping baked the "KA-" prefix into the
            # name too, showing it twice in the UI).
            subject.name = name
        return subject
    subject = Subject(code=code, name=name)
    db.add(subject)
    db.flush()
    return subject


def _find_creator(db: Session) -> User:
    admin = db.scalar(select(User).where(User.role == UserRole.ADMIN).order_by(User.created_at))
    if admin is not None:
        return admin
    examiner = db.scalar(
        select(User).where(User.role == UserRole.EXAMINER).order_by(User.created_at)
    )
    if examiner is not None:
        return examiner
    raise RuntimeError("No admin or examiner user found to attribute imported questions to")


def import_all(db: Session) -> list[ParseReport]:
    creator = _find_creator(db)
    reports: list[ParseReport] = []

    for file_name, (subject_code, subject_name) in SUBJECT_BY_FILE.items():
        path = DATA_DIR / file_name
        if not path.exists():
            logger.warning("Missing source file, skipping: %s", path)
            continue

        subject = _get_or_create_subject(db, subject_code, subject_name)
        rows, report = parse_file(path, subject_code)

        existing_bodies = set(
            db.scalars(
                select(Question.body).where(
                    Question.subject_id == subject.id, Question.language == LANGUAGE
                )
            )
        )

        for row in rows:
            if row["body"] in existing_bodies:
                report.duplicates += 1
                continue
            question = Question(
                subject_id=subject.id,
                language=LANGUAGE,
                question_type=row["question_type"],
                category=QuestionCategory.ACADEMIC,
                topic=subject_name,
                difficulty=row["difficulty"],
                body=row["body"],
                model_answer=row["model_answer"],
                explanation=row["explanation"],
                marks=row["marks"],
                status=QuestionStatus.PUBLISHED,
                is_active=True,
                source=QuestionSource.IMPORTED,
                created_by_id=creator.id,
            )
            for index, (text, is_correct) in enumerate(row["options"]):
                question.options.append(
                    QuestionOption(text=text, is_correct=is_correct, order_index=index)
                )
            db.add(question)
            existing_bodies.add(row["body"])
            report.inserted += 1

        db.flush()
        reports.append(report)
        logger.info(
            "%s: parsed=%d inserted=%d duplicates=%d unmapped_type=%d unmapped_difficulty=%d",
            file_name, report.parsed, report.inserted, report.duplicates,
            len(report.unmapped_type), len(report.unmapped_difficulty),
        )

    return reports


def main() -> None:
    db = SessionLocal()
    try:
        reports = import_all(db)
        db.commit()
    finally:
        db.close()

    total_parsed = sum(r.parsed for r in reports)
    total_inserted = sum(r.inserted for r in reports)
    total_duplicates = sum(r.duplicates for r in reports)
    print("\n=== Kannada question bank import ===")
    for r in reports:
        print(
            f"{r.file_name} ({r.subject_code}): parsed={r.parsed} inserted={r.inserted} "
            f"duplicates={r.duplicates} unmapped_type={len(r.unmapped_type)} "
            f"unmapped_difficulty={len(r.unmapped_difficulty)}"
        )
        for t in r.unmapped_type:
            print(f"  ! unmapped question type: {t!r}")
        for d in r.unmapped_difficulty:
            print(f"  ! unmapped difficulty: {d!r}")
    print(f"TOTAL: parsed={total_parsed} inserted={total_inserted} duplicates={total_duplicates}")


if __name__ == "__main__":
    main()
