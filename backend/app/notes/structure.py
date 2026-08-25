"""Turn raw typed or pasted text into a structured Note.

Pure rules, no model. The user marks up their own structure with conventions
they already know from chat apps and markdown:

    # Heading            -> heading, level from the number of hashes
    - item / * item      -> bullet, depth from leading indentation
    1. item              -> numbered
    > quoted text        -> quote
    Term: meaning        -> definition
    Note: / Warning:     -> callout
    e.g. something       -> example
    ---                  -> divider
    anything else        -> paragraph

Consecutive plain lines are joined into one paragraph, so hard-wrapped text
does not become a stack of one-line paragraphs.

This module has a single public function, `structure_note`. When an LLM is
added in MVP 2 it implements the same signature and this file stays as the
offline fallback.
"""

import re

from app.notes.schema import Note

BULLET = re.compile(r"^(\s*)[-*\u2022\u2023\u25cf]\s+(.*)$")
NUMBERED = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
QUOTE = re.compile(r"^>\s?(.*)$")
DIVIDER = re.compile(r"^\s*([-*_])\s*\1\s*\1[\s\-*_]*$")
LABELLED = re.compile(r"^(note|warning|important|key|tip|caution)\s*[:\-]\s*(.+)$", re.I)
EXAMPLE = re.compile(r"^(?:e\.?g\.?|example|for example)\s*[:\-]?\s+(.+)$", re.I)
DEFINITION = re.compile(r"^([A-Za-z][\w\s'/()-]{0,40}?)\s*[:\u2014-]\s+(.+)$")
TRAILING_COLON = re.compile(r"^(.{1,60}?):\s*$")

CALLOUT_VARIANT = {
    "warning": "warning",
    "caution": "warning",
    "important": "key",
    "key": "key",
    "note": "note",
    "tip": "note",
}

MATH_TOKENS = ("=", "\u2264", "\u2265", "\u2192", "O(", "\u03a3", "\u2211", "\u221a")


def looks_like_formula(line: str) -> bool:
    """Short, symbol-heavy, few words. Deliberately narrow to avoid false hits."""
    if len(line) > 45 or len(line.split()) > 8:
        return False
    return any(token in line for token in MATH_TOKENS)


def depth_of(indent: str) -> int:
    """Two spaces (or one tab) per level, capped at the schema's limit."""
    spaces = indent.replace("\t", "  ")
    return min(2, len(spaces) // 2)


MARK_PATTERN = re.compile(r"==(?:([gbpo]):)?(.+?)==")

MARK_COLORS = {"g": "green", "b": "blue", "p": "pink", "o": "orange", None: "yellow"}


def extract_marks(text: str) -> tuple[str, list[dict]]:
    """Strip ==highlight== syntax, returning clean text plus offset marks.

    ==text==     yellow (default)
    ==g:text==   green,  ==b:== blue,  ==p:== pink,  ==o:== orange

    Offsets are computed against the CLEANED string, so they stay valid after
    the delimiters are removed.
    """
    marks: list[dict] = []
    out: list[str] = []
    cursor = 0
    position = 0

    for match in MARK_PATTERN.finditer(text):
        out.append(text[cursor : match.start()])
        position += match.start() - cursor
        inner = match.group(2)
        marks.append(
            {
                "start": position,
                "end": position + len(inner),
                "kind": "highlight",
                "color": MARK_COLORS[match.group(1)],
            }
        )
        out.append(inner)
        position += len(inner)
        cursor = match.end()

    out.append(text[cursor:])
    return "".join(out), marks


class BlockBuilder:
    def __init__(self):
        self.blocks: list[dict] = []
        self.paragraph: list[str] = []
        self.counter = 0

    def next_id(self) -> str:
        self.counter += 1
        return f"b{self.counter}"

    def flush(self) -> None:
        """Emit any buffered plain lines as a single paragraph."""
        if not self.paragraph:
            return
        text = " ".join(self.paragraph).strip()
        self.paragraph = []
        if not text:
            return
        text, marks = extract_marks(text)
        block = {"id": self.next_id(), "type": "paragraph", "text": text}
        if marks:
            block["marks"] = marks
        self.blocks.append(block)

    def add(self, **block) -> None:
        self.flush()
        if "text" in block:
            block["text"], marks = extract_marks(block["text"])
            if marks:
                block["marks"] = marks
        self.blocks.append({"id": self.next_id(), **block})

    def buffer(self, line: str) -> None:
        self.paragraph.append(line)


def extract_title(lines: list[str]) -> tuple[str, list[str]]:
    """Take the first line as the title when it looks like one."""
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        stripped = line.strip()
        match = HEADING.match(stripped)
        if match:
            return match.group(2).strip(), lines[i + 1 :]
        if len(stripped) <= 70 and not stripped.endswith((".", ",", ";")):
            return stripped, lines[i + 1 :]
        return "Untitled Note", lines[i:]
    return "Untitled Note", []


def structure_note(raw_text: str) -> Note:
    """Parse raw text into a validated Note."""
    lines = raw_text.replace("\r\n", "\n").split("\n")
    title, body = extract_title(lines)
    b = BlockBuilder()
    numbered_seen = 0

    for line in body:
        stripped = line.strip()

        if not stripped:
            b.flush()
            continue

        if DIVIDER.match(stripped):
            b.add(type="divider")
            continue

        match = HEADING.match(stripped)
        if match:
            b.add(type="heading", level=len(match.group(1)), text=match.group(2).strip())
            numbered_seen = 0
            continue

        match = NUMBERED.match(line)
        if match:
            numbered_seen += 1
            b.add(
                type="numbered",
                depth=depth_of(match.group(1)),
                index=numbered_seen,
                text=match.group(3).strip(),
            )
            continue

        match = BULLET.match(line)
        if match:
            b.add(type="bullet", depth=depth_of(match.group(1)), text=match.group(2).strip())
            continue

        match = QUOTE.match(stripped)
        if match:
            b.add(type="quote", text=match.group(1).strip())
            continue

        match = LABELLED.match(stripped)
        if match:
            variant = CALLOUT_VARIANT.get(match.group(1).lower(), "note")
            b.add(type="callout", variant=variant, text=match.group(2).strip())
            continue

        match = EXAMPLE.match(stripped)
        if match:
            b.add(type="example", text=match.group(1).strip())
            continue

        # A short line ending in a colon reads as a section label, not a
        # sentence -- people write "Complexity:" as a heading all the time.
        match = TRAILING_COLON.match(stripped)
        if match:
            b.add(type="heading", level=2, text=match.group(1).strip())
            numbered_seen = 0
            continue

        if looks_like_formula(stripped):
            b.add(type="formula", text=stripped, notation="plain")
            continue

        match = DEFINITION.match(stripped)
        if match and len(match.group(1).split()) <= 4:
            b.add(type="definition", term=match.group(1).strip(), text=match.group(2).strip())
            continue

        b.buffer(stripped)

    b.flush()

    if not b.blocks:
        b.add(type="paragraph", text=raw_text.strip() or "(empty note)")

    return Note.model_validate({"schema_version": 1, "title": title, "blocks": b.blocks})
