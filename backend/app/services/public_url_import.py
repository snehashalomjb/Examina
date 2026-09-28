"""Public Google Forms/web question preview parser."""
from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.db.models.enums import Difficulty, QuestionType
from app.services.question_import import ParsedOption, ParsedRow
from app.services.validators import OptionDraft, ValidationError, validate_question

MAX_HTML_BYTES = 5 * 1024 * 1024
FETCH_TIMEOUT = 15
UA = "ExaminaQuestionImporter/1.0 (+public-question-preview)"


class UrlImportError(ValueError):
    """The URL could not be fetched or parsed."""


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: "Node | None" = None
    children: list["Node | str"] = field(default_factory=list)

    def text(self) -> str:
        value = " ".join(
            child if isinstance(child, str) else child.text()
            for child in self.children
            if not (isinstance(child, Node) and child.tag in {"script", "style"})
        )
        return re.sub(r"\s+", " ", value).strip()

    def walk(self) -> list["Node"]:
        found: list[Node] = []
        for child in self.children:
            if isinstance(child, Node):
                found.append(child)
                found.extend(child.walk())
        return found


class Dom(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag.casefold(), {k.casefold(): v or "" for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if node.tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag.casefold():
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.stack[-1].children.append(data)


def attr(node: Node, *names: str) -> str:
    return next((node.attrs[name.casefold()] for name in names if node.attrs.get(name.casefold())), "")


def classes(node: Node) -> str:
    return node.attrs.get("class", "").casefold()


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def qtype(value: str) -> QuestionType | None:
    key = re.sub(r"[\s_-]+", " ", value.casefold()).strip()
    aliases = {
        "single": QuestionType.MCQ, "single choice": QuestionType.MCQ,
        "single select": QuestionType.MCQ, "multiple": QuestionType.MULTI_SELECT,
        "multiple choice": QuestionType.MULTI_SELECT, "multiple select": QuestionType.MULTI_SELECT,
        "multi select": QuestionType.MULTI_SELECT, "checkbox": QuestionType.MULTI_SELECT,
        "true false": QuestionType.TRUE_FALSE, "true/false": QuestionType.TRUE_FALSE,
        "short answer": QuestionType.SHORT_ANSWER, "paragraph": QuestionType.LONG_ANSWER,
        "long answer": QuestionType.LONG_ANSWER, "numerical": QuestionType.NUMERICAL,
    }
    if key in aliases:
        return aliases[key]
    try:
        return QuestionType(key.replace(" ", "_"))
    except ValueError:
        return None




def validate_public_url(url: str) -> str:
    value = (url or "").strip()
    parsed = urlsplit(value)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise UrlImportError("Use a public http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise UrlImportError("URLs containing credentials are not supported.")
    host = parsed.hostname.casefold().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise UrlImportError("The URL must point to a public host.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
        raise UrlImportError("The URL must point to a public host.")
    return value


def fetch_public_html(url: str) -> str:
    safe = validate_public_url(url)
    request = Request(safe, headers={"User-Agent": UA, "Accept": "text/html"})
    response = None
    try:
        response = urlopen(request, timeout=FETCH_TIMEOUT)  # noqa: S310
        validate_public_url(getattr(response, "url", safe))
        headers = response.headers
        if headers.get("Content-Length") and int(headers["Content-Length"]) > MAX_HTML_BYTES:
            raise UrlImportError("That page is larger than the 5 MB import limit.")
        if headers.get_content_type().casefold() not in {"text/html", "application/xhtml+xml", "text/plain", ""}:
            raise UrlImportError("The URL did not return an HTML page.")
        data = response.read(MAX_HTML_BYTES + 1)
    except UrlImportError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise UrlImportError("That public page could not be fetched.") from exc
    finally:
        if response is not None:
            response.close()
    if len(data) > MAX_HTML_BYTES:
        raise UrlImportError("That page is larger than the 5 MB import limit.")
    return data.decode("utf-8", errors="replace")


def _ancestor(node: Node, parent: Node) -> bool:
    current = node.parent
    while current is not None:
        if current is parent:
            return True
        current = current.parent
    return False


def _roots(root: Node) -> list[Node]:
    candidates = [
        node for node in root.walk()
        if any(token in classes(node) for token in (
            "questionbaseroot", "question-container", "question-item", "quiz-question"
        )) or attr(node, "data-question-id", "data-question-number")
    ]
    return [node for node in candidates if not any(
        parent is not node and _ancestor(node, parent) for parent in candidates
    )]


def _title(node: Node) -> str:
    for child in node.walk():
        if any(token in classes(child) for token in (
            "questionbasetitle", "question-title", "quiz-question-title"
        )) or child.tag in {"h1", "h2", "h3", "h4"}:
            value = clean(child.text())
            if value:
                return value
    return clean(attr(node, "aria-label", "data-question"))


def _options(node: Node) -> list[Node]:
    return [
        child for child in node.walk()
        if attr(child, "role").casefold() in {"radio", "checkbox", "option"}
        or child.tag == "option"
        or any(token in classes(child) for token in (
            "choice", "answer-option", "multiple-choice-option", "checkbox-option"
        ))
    ]


def _option_text(node: Node) -> str:
    value = attr(node, "aria-label", "value", "data-value") or clean(node.text())
    return clean(re.sub(r"^(?:option|choice)\s+[A-F0-9]\s*[:.)-]?\s*", "", value, flags=re.I))


def _question_type(node: Node, options: list[Node]) -> QuestionType | None:
    found = qtype(" ".join([attr(node, "data-question-type", "data-type", "aria-label"), node.text()]))
    if found:
        return found
    if any(attr(item, "role").casefold() == "checkbox" for item in options):
        return QuestionType.MULTI_SELECT
    if any(attr(item, "role").casefold() == "radio" for item in options):
        return QuestionType.MCQ
    if any(item.tag == "textarea" for item in node.walk()):
        return QuestionType.LONG_ANSWER
    if any(
        item.tag == "input" and attr(item, "type").casefold() in {"text", "email", "url"}
        for item in node.walk()
    ):
        return QuestionType.SHORT_ANSWER
    return None


def _answer_letters(node: Node, options: list[str]) -> list[str]:
    explicit = [attr(node, "data-answer", "data-correct-answer", "data-key")]
    explicit.extend(
        attr(child, "data-answer", "data-correct-answer", "data-key")
        for child in node.walk()
    )
    raw = " ".join(value for value in explicit if value)
    if not raw:
        match = re.search(
            r"(?:correct\s+answer|answer\s+key|key)\s*[:=-]\s*([A-Fa-f0-9][A-Fa-f0-9,\s]*)",
            node.text(),
            re.I,
        )
        raw = match.group(1) if match else ""
    letters = [
        match.group(1).upper()
        for match in re.finditer(r"(?:^|[\s,;:])([A-Fa-f])(?:[.):\-]|(?=\s|$))", raw)
    ]
    if letters:
        return list(dict.fromkeys(letters))
    folded = raw.casefold()
    return [
        chr(65 + index)
        for index, option in enumerate(options)
        if option and option.casefold() in folded
    ]




#: Google's internal question-type codes, reverse-engineered from every public Forms
#: viewform page - Google has never published this mapping, but it has stayed stable
#: for years across forms of every kind (quiz or not). Codes with no entry here (grid,
#: date, time, linear scale, ...) fall through to ``question_type=None``, which the
#: caller already reports as "not recognisable" exactly like an unrecognised DOM shape.
_GOOGLE_FORMS_TYPE_CODES: dict[int, QuestionType] = {
    0: QuestionType.SHORT_ANSWER,
    1: QuestionType.LONG_ANSWER,
    2: QuestionType.MCQ,  # radio buttons
    3: QuestionType.MCQ,  # dropdown - still a single choice
    4: QuestionType.MULTI_SELECT,  # checkboxes
}


def _extract_fb_public_load_data(html: str) -> Any | None:
    """Pull the ``FB_PUBLIC_LOAD_DATA_`` JSON array every Google Forms viewform page
    embeds - the form's actual question data, never expressed as scrapeable DOM markup.

    Bracket-matched rather than regex-captured: a non-greedy ``.*?\\]`` would stop at
    the first ``]`` that happens to be followed by anything resembling a statement end
    inside the deeply nested array, long before the real end of the data.
    """
    marker = "FB_PUBLIC_LOAD_DATA_"
    start = html.find(marker)
    if start == -1:
        return None
    try:
        eq = html.index("=", start) + 1
        i = eq
        while html[i] != "[":
            i += 1
        depth = 0
        j = i
        while True:
            if html[j] == "[":
                depth += 1
            elif html[j] == "]":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        return json.loads(html[i:j])
    except (ValueError, IndexError):
        return None


def _google_forms_questions(data: Any) -> list[list[Any]]:
    try:
        questions = data[1][1]
    except (TypeError, IndexError, KeyError):
        return []
    return questions if isinstance(questions, list) else []


def parse_google_forms_json(data: Any) -> list[ParsedRow]:
    """Build ``ParsedRow``s straight from the form's own JSON, one question each.

    Google never exposes a correct-answer key in this public payload - only the form
    owner sees that, via the edit link - so every MCQ/multi-select row here always
    carries the same "choose the key" problem the DOM parser raises when a page hides
    its answer key. That is an honest limitation of the public page, not a parsing gap.
    """
    rows: list[ParsedRow] = []
    for number, question in enumerate(_google_forms_questions(data), start=1):
        if not isinstance(question, list) or len(question) < 4:
            continue
        body = clean(str(question[1])) if question[1] is not None else ""
        if not body:
            continue
        type_code = question[3]
        question_type = (
            _GOOGLE_FORMS_TYPE_CODES.get(type_code) if isinstance(type_code, int) else None
        )

        options: list[ParsedOption] = []
        detail = question[4] if len(question) > 4 else None
        if isinstance(detail, list) and detail and isinstance(detail[0], list):
            option_entries = detail[0][1] if len(detail[0]) > 1 else None
            if isinstance(option_entries, list):
                for entry in option_entries:
                    if not isinstance(entry, list) or not entry:
                        continue
                    text = clean(str(entry[0])) if entry[0] is not None else ""
                    if text:
                        options.append(ParsedOption(text, False))

        row = ParsedRow(
            row_number=number,
            body=body,
            question_type=question_type,
            difficulty=None,
            marks=None,
            options=options,
        )
        if question_type is None:
            row.problems.append("The public page did not expose a recognisable question type.")
        row.problems.append("Difficulty was not available; choose one before importing.")
        row.problems.append("Points/marks were not available; choose a value before importing.")
        if question_type in {QuestionType.MCQ, QuestionType.MULTI_SELECT}:
            if len(options) < 2:
                row.problems.append("Fewer than two options were found.")
            row.problems.append(
                "Google Forms does not expose a correct answer publicly; choose the key."
            )
        elif question_type in {QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER}:
            row.problems.append("A model answer was not available; add one before importing.")
        rows.append(row)
    return rows


def parse_public_html(html: str) -> list[ParsedRow]:
    forms_data = _extract_fb_public_load_data(html)
    if forms_data is not None:
        forms_rows = parse_google_forms_json(forms_data)
        if forms_rows:
            return forms_rows

    parser = Dom()
    parser.feed(html)
    rows: list[ParsedRow] = []
    seen: set[str] = set()
    for number, node in enumerate(_roots(parser.root), start=1):
        body = _title(node)
        key = re.sub(r"\s+", " ", body.casefold()).strip()
        if not body or key in seen:
            continue
        seen.add(key)
        option_nodes = _options(node)
        options = [ParsedOption(_option_text(item), False) for item in option_nodes]
        options = [item for item in options if item.text]
        question_type = _question_type(node, option_nodes)
        text = " ".join([attr(node, "data-difficulty", "data-points", "data-marks"), node.text()])
        difficulty_match = re.search(r"\b(easy|medium|hard)\b", text, re.I)
        points_match = re.search(r"(?<!\w)(\d+(?:\.\d+)?)\s*(?:points?|marks?|score)\b", text, re.I)
        row = ParsedRow(
            row_number=number,
            body=body,
            question_type=question_type,
            difficulty=Difficulty(difficulty_match.group(1).casefold()) if difficulty_match else None,
            marks=float(points_match.group(1)) if points_match else None,
            options=options,
        )
        if question_type is None:
            row.problems.append("The public page did not expose a recognisable question type.")
        if row.difficulty is None:
            row.problems.append("Difficulty was not available; choose one before importing.")
        if row.marks is None:
            row.problems.append("Points/marks were not available; choose a value before importing.")
        if question_type in {QuestionType.MCQ, QuestionType.MULTI_SELECT, QuestionType.TRUE_FALSE}:
            letters = _answer_letters(node, [item.text for item in options])
            row.options = [ParsedOption(item.text, chr(65 + index) in letters) for index, item in enumerate(options)]
            if len(options) < 2:
                row.problems.append("Fewer than two options were found.")
            if not letters:
                row.problems.append("The public page did not expose a correct answer; choose the key.")
            if question_type is QuestionType.TRUE_FALSE and (
                len(options) != 2 or sum(item.is_correct for item in row.options) != 1
            ):
                row.problems.append("A true/false question needs two options and exactly one key.")
        elif question_type in {QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER}:
            row.model_answer = attr(node, "data-model-answer", "data-answer") or None
            if not row.model_answer:
                row.problems.append("A model answer was not available; add one before importing.")
        rows.append(row)
    if not rows:
        raise UrlImportError("No recognizable questions were found at that public URL.")
    return rows


def parse_public_url(url: str) -> list[ParsedRow]:
    return parse_public_html(fetch_public_html(url))
