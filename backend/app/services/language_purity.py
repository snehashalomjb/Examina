"""Language purity: a question stored under a non-English language must be written
entirely in that language - no stray English prose mixed into the question, an
option, the model answer or the explanation.

This is deliberately separate from ``Question.language`` (which bank a question
belongs to) and from the translation tables (a different, unrelated mechanism). It
exists because a bank filtered correctly by language is still wrong if the content
inside it is half-English - "IPv6 addresses ____ bits ఉంటాయి" is not a Telugu
question just because it is filed under ``language="te"``.

Genuine technical acronyms, protocol/product names and code syntax are exempt - they
are proper nouns or literal code, not translatable prose (see ``ALLOWED_TERMS``).
Everything else, in non-English content, must be written in that language's own
script.
"""

from __future__ import annotations

import re

from app.services.validators import ValidationError

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+#.]*")
_QUOTED_RE = re.compile(r"\"[^\"]*\"|'[^']*'")

#: Acronyms, proper technical/product names, and Python syntax - exempt from the
#: purity check in any language. Extend this list rather than loosening the check.
ALLOWED_TERMS: frozenset[str] = frozenset(
    term.lower()
    for term in [
        # networking acronyms / proper protocol names
        "OSI", "TCP", "UDP", "IP", "IPv4", "IPv6", "HTTP", "HTTPS", "FTP", "SFTP",
        "SMTP", "DNS", "DHCP", "ARP", "MAC", "SSH", "Telnet", "SNMP", "NAT", "TTL",
        "STP", "BGP", "OSPF", "VLAN", "LAN", "WAN", "WWW", "URL", "URI", "IS-IS",
        "RIP", "IPSec", "VPN", "QoS", "ISP",
        # database acronyms
        "SQL", "DML", "DDL", "DCL", "TCL", "ACID", "NF", "1NF", "2NF", "3NF", "4NF",
        "BCNF",
        # languages/platforms/products treated as proper nouns
        "Python", "Java", "JavaScript", "C", "C++", "Linux", "Unix", "Windows",
        # Python syntax and identifiers - literal code, never translatable prose
        "def", "print", "len", "int", "float", "str", "bool", "list", "dict", "set",
        "tuple", "None", "True", "False", "is", "for", "while", "break", "try",
        "except", "finally", "venv", "append", "staticmethod", "classmethod",
        "threading", "argv", "asyncio", "multiprocessing", "itertools", "gc", "GIL",
        "CPython", "__str__", "__init__", "__len__", "__main__", "lambda", "range",
        # deep-learning / ML terminology - technical terms, not translatable prose
        "CPU", "GPU", "RAM", "ROM", "ReLU", "Dropout", "Gradient", "Descent",
        "CNN", "RNN", "LSTM", "GRU", "AI", "NLP", "Ethernet",
    ]
)


def find_impure_terms(text: str | None) -> list[str]:
    """Latin-script tokens in ``text`` that are not an allowed acronym/identifier.

    Quoted spans (``"hello"``, ``'x'``) are skipped before tokenising - a quoted
    string is literal code/data (e.g. ``len("hello")``), not translatable prose.
    """
    if not text:
        return []
    text = _QUOTED_RE.sub(" ", text)
    found: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0)
        if len(token) < 2 or token.lower() in ALLOWED_TERMS:
            continue
        if token.isupper() and len(token) <= 5:
            # A short, all-caps token reads as an acronym even when it is not on the
            # allowlist yet - e.g. a protocol name the list has not caught up with.
            continue
        found.append(token)
    return found


def check_language_purity(*, language: str, fields: dict[str, str | None]) -> None:
    """Raise ``ValidationError`` if any field mixes English prose into non-English content.

    ``fields`` maps a human label (used in the error message) to the text to check -
    e.g. ``{"question": body, "option A": "...", "explanation": ...}``. English
    content is never checked; there is nothing to violate.
    """
    if language == "en":
        return
    problems: dict[str, list[str]] = {}
    for label, text in fields.items():
        bad = find_impure_terms(text)
        if bad:
            problems[label] = bad
    if not problems:
        return
    detail = "; ".join(f"{label}: {', '.join(tokens)}" for label, tokens in problems.items())
    raise ValidationError(
        f"Language validation failed - this is a {language} question, but it mixes in "
        f"English word(s) ({detail}). Only genuine technical acronyms or code identifiers "
        "may stay in Latin script; everything else must be written in the question's own "
        "language."
    )
