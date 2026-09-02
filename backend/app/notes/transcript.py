"""Turn a raw speech transcript into marked-up text.

Speech has no headings, no bullets and no punctuation to speak of. What it does
have is *cue phrases* -- the things lecturers say to signal structure. This
module listens for those and converts them into the same markup a person would
type, so the transcript then flows through the ordinary structurer.

It is deliberately conservative: a missed cue leaves a plain sentence, which is
fine. A false cue mangles the note, which is not.
"""

import re

FILLERS = re.compile(
    r"\b(?:um|uh|erm|ah|like|you know|i mean|sort of|kind of|basically|"
    r"right\?|okay so|so yeah|anyway)\b[,\s]*",
    re.I,
)

HEADING_CUES = re.compile(
    r"^(?:so\s+)?(?:now\s+)?(?:let'?s\s+(?:talk\s+about|look\s+at|move\s+on\s+to)|"
    r"moving\s+on\s+to|next\s+(?:up|topic|we'?ll\s+cover)|turning\s+to|"
    r"today\s+we(?:'re| are)\s+(?:discussing|covering|looking\s+at))\s+(.+)$",
    re.I,
)

DEFINITION_CUES = re.compile(
    r"^(.{2,40}?)\s+(?:is|are)\s+(?:defined\s+as|called)\s+(.+)$", re.I
)

ORDINALS = {
    "first": 1, "firstly": 1, "second": 2, "secondly": 2, "third": 3,
    "thirdly": 3, "fourth": 4, "fifth": 5, "finally": 0, "lastly": 0,
}
ORDINAL_CUE = re.compile(rf"^({'|'.join(ORDINALS)})[,\s]+(?:of\s+all[,\s]+)?(.+)$", re.I)

EXAMPLE_CUE = re.compile(r"^(?:for\s+(?:example|instance)|say|consider)[,\s]+(.+)$", re.I)
WARNING_CUE = re.compile(
    r"^(?:(?:be\s+)?careful|watch\s+out|note\s+that|remember\s+that|"
    r"(?:this\s+is\s+)?important(?:ly)?|don'?t\s+forget)[,\s]+(.+)$",
    re.I,
)
BULLET_CUE = re.compile(r"^(?:another|also|and\s+then|additionally)[,\s]+(.+)$", re.I)

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\s{2,}")


def sentences(text: str) -> list[str]:
    parts = [p.strip(" ,;") for p in SENTENCE_SPLIT.split(text)]
    return [p for p in parts if p]


def sentence_case(text: str) -> str:
    text = text.strip()
    return text[0].upper() + text[1:] if text else text


def clean_transcript(raw: str, title: str | None = None) -> str:
    """Raw speech -> the markup our structurer already understands."""
    text = FILLERS.sub("", raw)
    lines: list[str] = []
    counter = 0

    for sentence in sentences(text):
        s = sentence.strip()
        if len(s) < 2:
            continue

        m = HEADING_CUES.match(s)
        if m:
            lines += ["", f"# {sentence_case(m.group(1).rstrip('.'))}"]
            counter = 0
            continue

        m = ORDINAL_CUE.match(s)
        if m:
            word = m.group(1).lower()
            counter = counter + 1 if ORDINALS[word] == 0 else ORDINALS[word]
            lines.append(f"{counter}. {sentence_case(m.group(2))}")
            continue

        m = WARNING_CUE.match(s)
        if m:
            lines.append(f"Warning: {sentence_case(m.group(1))}")
            continue

        m = EXAMPLE_CUE.match(s)
        if m:
            lines.append(f"e.g. {sentence_case(m.group(1))}")
            continue

        m = DEFINITION_CUES.match(s)
        if m:
            lines.append(f"{sentence_case(m.group(1))}: {sentence_case(m.group(2))}")
            continue

        m = BULLET_CUE.match(s)
        if m:
            lines.append(f"- {sentence_case(m.group(1))}")
            continue

        lines.append(sentence_case(s))

    body = "\n".join(lines).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    return f"{title.strip()}\n\n{body}" if title else body
