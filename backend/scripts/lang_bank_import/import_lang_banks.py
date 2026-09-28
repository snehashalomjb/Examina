"""Import Tamil/Hindi/Telugu/Malayalam question banks from the raw SQL dumps in
``backend/scripts/lang_bank_import/sql/`` into the real question bank.

Structural precedent: ``app/seed_kannada_question_bank.py`` (same idea - source files
use an unrelated ad-hoc schema and are never executed as SQL, each row is hand-parsed
and inserted as a standalone ``Question`` with the target ``language``). This script
additionally runs every parsed question through ``language_purity.check_language_purity``
before insert - a question that mixes English prose into non-English content is skipped
and reported, never silently saved.

Explicitly NOT imported (per decision):
  - MAL-Artificial-Intelligence.sql: byte-identical duplicate of MAL-Aptitude.sql content.
  - MAL-Data-Science.sql: rows say subject="MAL-Natural Language Processing" and the
    content is genuinely NLP, not Data Science - held back pending a correctly labeled
    file.

Run with: ``uv run python -m scripts.lang_bank_import.import_lang_banks`` from `backend/`.
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
from app.services.language_purity import check_language_purity
from app.services.validators import ValidationError

logger = get_logger("seed_lang_banks")

DATA_DIR = Path(__file__).parent / "sql"

ENGLISH_QTYPE_MAP: dict[str, QuestionType] = {
    "Single Choice": QuestionType.MCQ,
    "Multiple Choice": QuestionType.MULTI_SELECT,
    "True/False": QuestionType.TRUE_FALSE,
    "Fill in the Blanks": QuestionType.FILL_BLANK,
    "Short Answer": QuestionType.SHORT_ANSWER,
    "Long Answer": QuestionType.LONG_ANSWER,
}
ENGLISH_DIFF_MAP: dict[str, Difficulty] = {
    "Easy": Difficulty.EASY,
    "Medium": Difficulty.MEDIUM,
    "Hard": Difficulty.HARD,
}

MAL_QTYPE_MAP: dict[str, QuestionType] = {
    "ഒറ്റ തിരഞ്ഞെടുപ്പ്": QuestionType.MCQ,
    "ബഹു തിരഞ്ഞെടുപ്പ്": QuestionType.MULTI_SELECT,
    "ശരി അല്ലെങ്കിൽ തെറ്റ്": QuestionType.TRUE_FALSE,
    "ശൂന്യസ്ഥലം പൂരിപ്പിക്കുക": QuestionType.FILL_BLANK,
    "സംക്ഷിപ്ത ഉത്തരം": QuestionType.SHORT_ANSWER,
    "വിസ്തൃത ഉത്തരം": QuestionType.LONG_ANSWER,
}
MAL_DIFF_MAP: dict[str, Difficulty] = {
    "എളുപ്പം": Difficulty.EASY,
    "മധ്യമം": Difficulty.MEDIUM,
    "കഠിനം": Difficulty.HARD,
}
#: അ=0, ആ=1, ഇ=2, ഈ=3 - the letter convention MAL-Aptitude uses for "correct_answer".
MAL_OPTION_LETTERS = ["അ", "ആ", "ഇ", "ഈ"]

#: Shape-A files (HIN-*/TAM-*/TEL-*) leave option_a..d blank for True/False rows and
#: only fill "correct_answer" with the localized word for True or False - the two
#: option texts have to be synthesised rather than read from the row.
TRUE_FALSE_LABELS: dict[str, tuple[str, str]] = {
    "hi": ("सही", "गलत"),
    "ta": ("சரி", "தவறு"),
    "te": ("సరైనది", "తప్పు"),
}

_FIELD_COUNT = 12


@dataclass
class LangConfig:
    language: str
    files: dict[str, tuple[str, str]]  # filename -> (subject_code, subject_name)
    qtype_map: dict[str, QuestionType]
    diff_map: dict[str, Difficulty]
    option_letters: list[str] | None = None
    #: "fixed12" (default): subject,language,type,difficulty,marks,question,option_a..d,
    #: correct_answer,explanation - one column per option (HIN/TAM/TEL/MAL-Aptitude).
    #: "pipe9": subject,language,type,difficulty,marks,question,options,correct_answer,
    #: explanation - all options joined in one "opt1 | opt2 | ..." column, and a
    #: multi-select correct_answer is itself "correct1 | correct2" (MAL-Cloud-Computing,
    #: MAL-Cyber-Security).
    row_format: str = "fixed12"


LANG_CONFIGS: list[LangConfig] = [
    LangConfig(
        language="ta",
        files={
            "TAM-Computer-Networks.sql": ("TAM-CN", "Computer Networks"),
            "TAM-Deep-Learning.sql": ("TAM-DL", "Deep Learning"),
            "TAM-Operating-Systems.sql": ("TAM-OS", "Operating Systems"),
        },
        qtype_map=ENGLISH_QTYPE_MAP,
        diff_map=ENGLISH_DIFF_MAP,
    ),
    LangConfig(
        language="hi",
        files={
            "HIN-Computer-Networks.sql": ("HIN-CN", "Computer Networks"),
            "HIN-Deep-Learning.sql": ("HIN-DL", "Deep Learning"),
            "HIN-Operating-Systems.sql": ("HIN-OS", "Operating Systems"),
        },
        qtype_map=ENGLISH_QTYPE_MAP,
        diff_map=ENGLISH_DIFF_MAP,
    ),
    LangConfig(
        language="te",
        files={
            "TEL-Computer-Networks.sql": ("TEL-CN", "Computer Networks"),
            "TEL-Deep-Learning.sql": ("TEL-DL", "Deep Learning"),
            "TEL-Operating-Systems.sql": ("TEL-OS", "Operating Systems"),
        },
        qtype_map=ENGLISH_QTYPE_MAP,
        diff_map=ENGLISH_DIFF_MAP,
    ),
    LangConfig(
        language="ml",
        files={
            "MAL-Aptitude.sql": ("MAL-APT", "Aptitude"),
        },
        qtype_map=MAL_QTYPE_MAP,
        diff_map=MAL_DIFF_MAP,
        option_letters=MAL_OPTION_LETTERS,
    ),
    LangConfig(
        language="ml",
        files={
            "MAL-Cloud-Computing.sql": ("MAL-CC", "Cloud Computing"),
            "MAL-Cyber-Security.sql": ("MAL-CYB", "Cyber Security"),
        },
        qtype_map=ENGLISH_QTYPE_MAP,
        diff_map=ENGLISH_DIFF_MAP,
        row_format="array9",
    ),
]


@dataclass
class ParseReport:
    file_name: str
    language: str
    subject_code: str
    parsed: int = 0
    inserted: int = 0
    duplicates: int = 0
    purity_failed: int = 0
    unmapped_type: list[str] = field(default_factory=list)
    unmapped_difficulty: list[str] = field(default_factory=list)
    purity_examples: list[str] = field(default_factory=list)


def _split_row(inner: str) -> list[str | None]:
    """Split the content between one row's outer parens into its raw field strings.

    Quote-aware: these text fields contain literal commas, and a literal quote inside a
    field is escaped as ``''`` (standard SQL) - a naive ``.split(",")`` would mis-tokenize
    both.
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
    ``(...)`` tuple's fields - handles both a single multi-row VALUES statement and many
    single-row INSERT statements, since both just produce top-level parens."""
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
    # The first "row" captured in every file is the column-name tuple in the INSERT
    # header (or the CREATE TABLE column list) - drop anything not shaped like a
    # 12-field data row, and drop the header row explicitly by its first cell.
    return [
        r
        for r in rows
        if len(r) == _FIELD_COUNT and r[0] not in (None, "subject", "விஷயம்")
    ]


_PIPE9_FIELD_COUNT = 9


def _extract_rows_pipe9(sql_text: str) -> list[list[str | None]]:
    """Same quote-aware scanner as ``_extract_rows``, but for the 9-column
    "single pipe-delimited options string" shape (MAL-Cloud-Computing,
    MAL-Cyber-Security). Also drops the bare-identifier column-list tuple that
    appears in every ``INSERT INTO question_bank (subject, language, ...)`` header,
    since the scanner captures it as a top-level paren-tuple too."""
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
    return [
        r
        for r in rows
        if len(r) == _PIPE9_FIELD_COUNT and r[0] not in (None, "subject")
    ]


def _split_pipe(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def _split_row_bracket_aware(inner: str) -> list[str | None]:
    """Like ``_split_row``, but also tracks ``[`` / ``]`` depth so a comma inside a
    literal Postgres array (``ARRAY['a','b']``) never counts as a field separator."""
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
            j = i
            bracket_depth = 0
            in_quote = False
            while j < n:
                cj = inner[j]
                if in_quote:
                    if cj == "'":
                        if j + 1 < n and inner[j + 1] == "'":
                            j += 2
                            continue
                        in_quote = False
                    j += 1
                    continue
                if cj == "'":
                    in_quote = True
                    j += 1
                    continue
                if cj == "[":
                    bracket_depth += 1
                    j += 1
                    continue
                if cj == "]":
                    bracket_depth -= 1
                    j += 1
                    continue
                if cj == "," and bracket_depth == 0:
                    break
                j += 1
            token = inner[i:j].strip().strip("`")
            fields.append(token or None)
            i = j
        while i < n and inner[i] != ",":
            i += 1
        i += 1  # skip the comma
    return fields


def _extract_rows_array9(sql_text: str) -> list[list[str | None]]:
    """Same top-level ``(...)`` tuple boundary scan as ``_extract_rows_pipe9``, but
    splits each tuple's fields with ``_split_row_bracket_aware`` so an
    ``ARRAY['a','b']`` options field is never mis-split on its internal commas."""
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
                rows.append(_split_row_bracket_aware(sql_text[start:i]))
                start = -1
            i += 1
            continue
        i += 1
    return [
        r
        for r in rows
        if len(r) == _PIPE9_FIELD_COUNT and r[0] not in (None, "subject")
    ]


def _parse_pg_array_field(raw: str | None) -> list[str]:
    """Parse a literal Postgres array field (``ARRAY['a','b']`` or
    ``ARRAY[]::text[]``) into a plain list of strings. Quote-aware so an option's own
    text may safely contain ``,``/``[``/``]``."""
    if not raw or "ARRAY[" not in raw:
        return []
    start = raw.index("ARRAY[") + len("ARRAY[")
    i = start
    n = len(raw)
    in_quote = False
    depth = 1
    items: list[str] = []
    buf: list[str] = []
    while i < n and depth > 0:
        c = raw[i]
        if in_quote:
            if c == "'":
                if i + 1 < n and raw[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_quote = False
                items.append("".join(buf))
                buf = []
                i += 1
                continue
            buf.append(c)
            i += 1
            continue
        if c == "'":
            in_quote = True
            i += 1
            continue
        if c == "[":
            depth += 1
            i += 1
            continue
        if c == "]":
            depth -= 1
            i += 1
            continue
        i += 1
    return items


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() == "nan":
        return None
    return value


def _match_option_index(
    token: str, option_texts: list[str | None], option_letters: list[str] | None
) -> int | None:
    token = token.strip()
    for idx, text in enumerate(option_texts):
        if text is not None and text.strip() == token:
            return idx
    if option_letters and token in option_letters:
        idx = option_letters.index(token)
        if idx < len(option_texts):
            return idx
    return None


def parse_file(path: Path, cfg: LangConfig, subject_code: str) -> tuple[list[dict], ParseReport]:
    report = ParseReport(file_name=path.name, language=cfg.language, subject_code=subject_code)
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

        qtype = cfg.qtype_map.get((type_col or "").strip())
        if qtype is None:
            report.unmapped_type.append((type_col or "")[:60])
            continue
        difficulty = cfg.diff_map.get((difficulty_col or "").strip())
        if difficulty is None:
            report.unmapped_difficulty.append((difficulty_col or "")[:60])
            continue

        body = _clean(body_col) or ""
        marks = float(_clean(marks_col) or "1")
        explanation = _clean(explanation_col)
        option_texts: list[str | None] = [_clean(opt_a), _clean(opt_b), _clean(opt_c), _clean(opt_d)]
        correct_raw = _clean(correct_col) or ""

        model_answer = None
        spec: dict | None = None
        options: list[tuple[str, bool]] = []

        if qtype == QuestionType.TRUE_FALSE and all(t is None for t in option_texts[:2]):
            # Shape-A True/False rows leave option_a/b blank - synthesise the pair from
            # the localized True/False labels for this language.
            true_label, false_label = TRUE_FALSE_LABELS[cfg.language]
            option_texts = [true_label, false_label]
            is_true = correct_raw.strip() == true_label
            options = [(true_label, is_true), (false_label, not is_true)]
        elif qtype in (QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.TRUE_FALSE):
            correct_indices: set[int] = set()
            whole_match = _match_option_index(correct_raw, option_texts, cfg.option_letters)
            if whole_match is not None:
                correct_indices.add(whole_match)
            elif qtype == QuestionType.MULTI_SELECT:
                for token in correct_raw.split(","):
                    idx = _match_option_index(token, option_texts, cfg.option_letters)
                    if idx is not None:
                        correct_indices.add(idx)
            for idx, opt_text in enumerate(option_texts):
                if opt_text is not None:
                    options.append((opt_text, idx in correct_indices))
        elif qtype == QuestionType.FILL_BLANK:
            model_answer = correct_raw or None
            if correct_raw:
                spec = {"accepted_answers": [correct_raw], "case_sensitive": False}
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
                "spec": spec,
                "options": options,
            }
        )
    return parsed, report


def parse_file_pipe9(path: Path, cfg: LangConfig, subject_code: str) -> tuple[list[dict], ParseReport]:
    report = ParseReport(file_name=path.name, language=cfg.language, subject_code=subject_code)
    text = path.read_text(encoding="utf-8")
    rows = _extract_rows_pipe9(text)
    parsed: list[dict] = []
    for row in rows:
        (
            _subject_col,
            _language_col,
            type_col,
            difficulty_col,
            marks_col,
            body_col,
            options_col,
            correct_col,
            explanation_col,
        ) = row
        report.parsed += 1

        qtype = cfg.qtype_map.get((type_col or "").strip())
        if qtype is None:
            report.unmapped_type.append((type_col or "")[:60])
            continue
        difficulty = cfg.diff_map.get((difficulty_col or "").strip())
        if difficulty is None:
            report.unmapped_difficulty.append((difficulty_col or "")[:60])
            continue

        body = _clean(body_col) or ""
        marks = float(_clean(marks_col) or "1")
        explanation = _clean(explanation_col)
        correct_raw = _clean(correct_col) or ""
        option_texts: list[str | None] = _split_pipe(options_col)

        model_answer = None
        spec: dict | None = None
        options: list[tuple[str, bool]] = []

        if qtype in (QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.TRUE_FALSE):
            correct_set = {c.strip() for c in _split_pipe(correct_raw)} or {correct_raw.strip()}
            for opt_text in option_texts:
                options.append((opt_text, opt_text.strip() in correct_set))
        elif qtype == QuestionType.FILL_BLANK:
            model_answer = correct_raw or None
            if correct_raw:
                spec = {"accepted_answers": [correct_raw], "case_sensitive": False}
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
                "spec": spec,
                "options": options,
            }
        )
    return parsed, report


def parse_file_array9(path: Path, cfg: LangConfig, subject_code: str) -> tuple[list[dict], ParseReport]:
    """Shape: subject,language,type,difficulty,marks,question,options,correct_answer,
    explanation - options is a literal Postgres array (``ARRAY['a','b']`` /
    ``ARRAY[]::text[]``), and a multi-select ``correct_answer`` is ``opt1; opt2``
    (semicolon-joined full option texts), not pipe-joined."""
    report = ParseReport(file_name=path.name, language=cfg.language, subject_code=subject_code)
    text = path.read_text(encoding="utf-8")
    rows = _extract_rows_array9(text)
    parsed: list[dict] = []
    for row in rows:
        (
            _subject_col,
            _language_col,
            type_col,
            difficulty_col,
            marks_col,
            body_col,
            options_col,
            correct_col,
            explanation_col,
        ) = row
        report.parsed += 1

        qtype = cfg.qtype_map.get((type_col or "").strip())
        if qtype is None:
            report.unmapped_type.append((type_col or "")[:60])
            continue
        difficulty = cfg.diff_map.get((difficulty_col or "").strip())
        if difficulty is None:
            report.unmapped_difficulty.append((difficulty_col or "")[:60])
            continue

        body = _clean(body_col) or ""
        marks = float(_clean(marks_col) or "1")
        explanation = _clean(explanation_col)
        correct_raw = _clean(correct_col) or ""
        option_texts: list[str | None] = [
            t for t in (s.strip() for s in _parse_pg_array_field(options_col)) if t
        ]

        model_answer = None
        spec: dict | None = None
        options: list[tuple[str, bool]] = []

        if qtype in (QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.TRUE_FALSE):
            correct_set = {
                c.strip() for c in correct_raw.split(";") if c.strip()
            } or {correct_raw.strip()}
            for opt_text in option_texts:
                # Multi-select options are "label: description" but correct_answer only
                # names the label - match either the whole text or just its label part.
                label = opt_text.split(":", 1)[0].strip()
                options.append((opt_text, opt_text.strip() in correct_set or label in correct_set))
        elif qtype == QuestionType.FILL_BLANK:
            model_answer = correct_raw or None
            if correct_raw:
                spec = {"accepted_answers": [correct_raw], "case_sensitive": False}
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
                "spec": spec,
                "options": options,
            }
        )
    return parsed, report


def _get_or_create_subject(db: Session, code: str, name: str) -> Subject:
    subject = db.scalar(select(Subject).where(Subject.code == code))
    if subject is not None:
        if subject.name != name:
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

    for cfg in LANG_CONFIGS:
        for file_name, (subject_code, subject_name) in cfg.files.items():
            path = DATA_DIR / file_name
            if not path.exists():
                logger.warning("Missing source file, skipping: %s", path)
                continue

            subject = _get_or_create_subject(db, subject_code, subject_name)
            if cfg.row_format == "array9":
                parser = parse_file_array9
            elif cfg.row_format == "pipe9":
                parser = parse_file_pipe9
            else:
                parser = parse_file
            rows, report = parser(path, cfg, subject_code)

            existing_bodies = set(
                db.scalars(
                    select(Question.body).where(
                        Question.subject_id == subject.id, Question.language == cfg.language
                    )
                )
            )

            for row in rows:
                if row["body"] in existing_bodies:
                    report.duplicates += 1
                    continue

                purity_fields = {
                    "question": row["body"],
                    "model answer": row["model_answer"],
                    "explanation": row["explanation"],
                    **{
                        f"option {chr(65 + i)}": text
                        for i, (text, _is_correct) in enumerate(row["options"])
                    },
                }
                try:
                    check_language_purity(language=cfg.language, fields=purity_fields)
                except ValidationError as exc:
                    report.purity_failed += 1
                    if len(report.purity_examples) < 5:
                        report.purity_examples.append(f"{row['body'][:60]!r}: {exc}")
                    continue

                question = Question(
                    subject_id=subject.id,
                    language=cfg.language,
                    question_type=row["question_type"],
                    category=QuestionCategory.ACADEMIC,
                    topic=subject_name,
                    difficulty=row["difficulty"],
                    body=row["body"],
                    model_answer=row["model_answer"],
                    explanation=row["explanation"],
                    spec=row["spec"],
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
                "%s (%s/%s): parsed=%d inserted=%d duplicates=%d purity_failed=%d "
                "unmapped_type=%d unmapped_difficulty=%d",
                file_name, cfg.language, subject_code, report.parsed, report.inserted,
                report.duplicates, report.purity_failed, len(report.unmapped_type),
                len(report.unmapped_difficulty),
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
    total_purity_failed = sum(r.purity_failed for r in reports)
    print("\n=== Language question bank import (ta/hi/te/ml) ===")
    for r in reports:
        print(
            f"{r.file_name} ({r.language}/{r.subject_code}): parsed={r.parsed} "
            f"inserted={r.inserted} duplicates={r.duplicates} "
            f"purity_failed={r.purity_failed} unmapped_type={len(r.unmapped_type)} "
            f"unmapped_difficulty={len(r.unmapped_difficulty)}"
        )
        for t in r.unmapped_type:
            print(f"  ! unmapped question type: {t!r}")
        for d in r.unmapped_difficulty:
            print(f"  ! unmapped difficulty: {d!r}")
        for p in r.purity_examples:
            print(f"  ! purity failed: {p}")
    print(
        f"TOTAL: parsed={total_parsed} inserted={total_inserted} "
        f"duplicates={total_duplicates} purity_failed={total_purity_failed}"
    )


if __name__ == "__main__":
    main()
